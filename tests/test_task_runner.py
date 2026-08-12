from __future__ import annotations

import time
from pathlib import Path
from threading import Event

from tools.init_project import init_project
from tools.task_runner import PersistentTaskRunner, TaskContext
from tools.task_store import TaskStore


def _wait_for(store: TaskStore, task_id: str, status: str, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task = store.load(task_id)
        if task is None:
            time.sleep(0.01)
            continue
        if task.get("status") == status:
            return task
        if task.get("status") in {"failed", "cancelled", "interrupted"}:
            error = task.get("error") or {}
            raise AssertionError(
                f"task {task_id} reached {task.get('status')} before {status}: "
                f"{error.get('code')} {error.get('message')}"
            )
        time.sleep(0.01)
    raise AssertionError(f"task {task_id} did not reach {status}")


def test_task_store_externalizes_large_input_and_redacts_credentials(tmp_path: Path):
    init_project(tmp_path, "demo")
    store = TaskStore(tmp_path, "demo")
    content = ("长文本\r\n" * 1800) + "没有末尾换行"

    task = store.create(
        "source_extract",
        {"content": content, "api_key": "private", "nested": {"secret": "hidden"}},
    )

    assert task["input"]["api_key"] == "[redacted]"
    assert task["input"]["nested"]["secret"] == "[redacted]"
    assert task["input"]["content"]["$artifact"].startswith("inputs/")
    assert store.materialize_input(task)["content"] == content
    assert store.events(task["task_id"])[0]["event"] == "task_created"
    assert store.index_path.is_file()


def test_persistent_task_runner_records_real_phases_and_result(tmp_path: Path):
    init_project(tmp_path, "demo")

    def handler(payload: dict, context: TaskContext) -> dict:
        context.phase("preparing", "assembling packet")
        context.phase("model", "calling model")
        context.phase("validating", "checking output")
        context.checkpoint()
        context.phase("committing", "writing result")
        return {"chapter_id": payload["chapter_id"], "path": "data/result.md"}

    runner = PersistentTaskRunner(tmp_path, "demo", handlers={"chapter_write": handler})
    try:
        task = runner.submit(
            "chapter_write",
            {"chapter_id": "ch_001"},
            chapter_id="ch_001",
            input_summary="写 ch_001",
        )
        completed = _wait_for(runner.store, task["task_id"], "completed")

        assert completed["phase"] == "complete"
        assert completed["result"]["chapter_id"] == "ch_001"
        phases = [event["phase"] for event in runner.store.events(task["task_id"])]
        assert phases == [
            "queued",
            "reading",
            "preparing",
            "model",
            "validating",
            "committing",
            "complete",
        ]
    finally:
        runner.shutdown(wait=True)


def test_terminal_event_is_durable_before_completed_snapshot(tmp_path: Path, monkeypatch):
    init_project(tmp_path, "demo")
    store = TaskStore(tmp_path, "demo")
    task = store.create("chapter_review", {"chapter_id": "ch_001"})
    original_save = store._save_unlocked
    observed: dict[str, bool] = {}

    def checking_save(record: dict) -> None:
        if record.get("status") == "completed":
            events = store.events(record["task_id"])
            observed["completion_event_exists"] = bool(
                events and events[-1]["event"] == "task_completed"
            )
            observed["watermark_matches"] = bool(
                events and record.get("last_event_id") == events[-1]["event_id"]
            )
        original_save(record)

    monkeypatch.setattr(store, "_save_unlocked", checking_save)
    completed = store.transition(
        task["task_id"],
        status="completed",
        phase="complete",
        updates={"result": {"score": 90}},
        event="task_completed",
    )

    assert observed == {
        "completion_event_exists": True,
        "watermark_matches": True,
    }
    assert completed["last_event_id"] == store.events(task["task_id"])[-1]["event_id"]


def test_pending_and_running_tasks_can_be_cancelled_without_result(tmp_path: Path):
    init_project(tmp_path, "demo")
    started = Event()
    release = Event()

    def handler(payload: dict, context: TaskContext) -> dict:
        del payload
        context.phase("model", "waiting")
        started.set()
        while not release.wait(0.01):
            context.checkpoint()
        context.checkpoint()
        return {"unexpected": True}

    runner = PersistentTaskRunner(tmp_path, "demo", handlers={"revision_generate": handler})
    try:
        running = runner.submit("revision_generate", {"chapter_id": "ch_001"})
        assert started.wait(1)
        pending = runner.submit("revision_generate", {"chapter_id": "ch_002"})

        runner.cancel(pending["task_id"])
        cancelled_pending = _wait_for(
            runner.store, pending["task_id"], "cancelled"
        )
        assert cancelled_pending["result"] == {}

        runner.cancel(running["task_id"])
        cancelled_running = _wait_for(
            runner.store, running["task_id"], "cancelled"
        )
        assert cancelled_running["result"] == {}
    finally:
        release.set()
        runner.shutdown(wait=True)


def test_startup_marks_orphaned_running_tasks_interrupted_and_retryable(tmp_path: Path):
    init_project(tmp_path, "demo")
    store = TaskStore(tmp_path, "demo")
    original = store.create("chapter_review", {"chapter_id": "ch_001"})
    store.transition(
        original["task_id"],
        status="running",
        phase="model",
        event="task_started",
    )

    runner = PersistentTaskRunner(
        tmp_path,
        "demo",
        handlers={
            "chapter_review": lambda payload, context: {
                "chapter_id": payload["chapter_id"],
                "score": 90,
            }
        },
    )
    try:
        interrupted = runner.store.load(original["task_id"])
        assert interrupted is not None and interrupted["status"] == "interrupted"
        assert interrupted["error"]["code"] == "PROCESS_INTERRUPTED"

        retried = runner.retry(original["task_id"])
        completed = _wait_for(runner.store, retried["task_id"], "completed")
        assert completed["retry_of"] == original["task_id"]
        assert completed["attempt"] == 2
        assert completed["result"]["score"] == 90
    finally:
        runner.shutdown(wait=True)


def test_retry_preserves_persisted_continuous_write_progress(tmp_path: Path):
    init_project(tmp_path, "demo")
    store = TaskStore(tmp_path, "demo")
    original = store.create("continuous_write", {"max_chapters": 2})
    store.transition(
        original["task_id"],
        status="running",
        phase="committing",
        updates={
            "result": {
                "completed_chapters": [{"chapter_id": "ch_001"}],
                "usage": {"total_tokens": 120},
            }
        },
        event="task_progress_saved",
    )
    observed: dict = {}

    def handler(payload: dict, context: TaskContext) -> dict:
        del context
        observed.update(payload)
        return {"completed_chapters": payload["_already_completed"]}

    runner = PersistentTaskRunner(
        tmp_path,
        "demo",
        handlers={"continuous_write": handler},
    )
    try:
        retried = runner.retry(original["task_id"])
        completed = _wait_for(runner.store, retried["task_id"], "completed")
        assert observed["_already_completed"] == [{"chapter_id": "ch_001"}]
        assert observed["_already_used"] == {"total_tokens": 120}
        assert completed["result"]["completed_chapters"] == [
            {"chapter_id": "ch_001"}
        ]
    finally:
        runner.shutdown(wait=True)


def test_watchdog_interrupts_stuck_task_and_discards_stale_result(
    tmp_path: Path, monkeypatch
):
    """看门狗：卡死任务先协作取消，宽限超时后强制中断；handler 后到完成不覆盖。"""
    init_project(tmp_path, "demo")
    # 收缩阈值：任何 running 任务都视为卡死（避免真实等待 10 分钟）
    monkeypatch.setattr("tools.task_runner.STUCK_AFTER_SECONDS", 0)
    monkeypatch.setattr("tools.task_runner.STUCK_GRACE_SECONDS", 0)
    block = Event()

    def handler(payload: dict, context: TaskContext) -> dict:
        del payload
        context.phase("model", "working")
        block.wait(30)  # 模拟长时间 LLM 调用，期间无心跳
        return {"late_result": True}

    runner = PersistentTaskRunner(tmp_path, "demo", handlers={"chapter_review": handler})
    try:
        task = runner.submit("chapter_review", {"chapter_id": "ch_001"})
        running = _wait_for(runner.store, task["task_id"], "running")

        # 第一次 tick：无取消标记 → 协作请求取消，任务仍 running
        runner._watchdog_tick()
        after_first = runner.store.load(task["task_id"])
        assert after_first["cancel_requested"] is True
        assert after_first["status"] == "running"

        # 第二次 tick：取消已请求且宽限超时 → 强制中断
        runner._watchdog_tick()
        interrupted = _wait_for(runner.store, task["task_id"], "interrupted")
        assert interrupted["error"]["code"] == "STUCK_TIMEOUT"

        # handler 最终返回：结果被丢弃，中断状态不被覆盖
        block.set()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            current = runner.store.load(task["task_id"])
            if current is not None and current.get("result", {}).get("late_result"):
                break
            time.sleep(0.01)
        final = runner.store.load(task["task_id"])
        assert final["status"] == "interrupted"
        assert final["error"]["code"] == "STUCK_TIMEOUT"
        assert final["result"].get("late_result") is True  # 结果只挂载、不改状态
    finally:
        block.set()
        runner.shutdown(wait=True)


def test_watchdog_leaves_healthy_running_task_untouched(tmp_path: Path):
    """看门狗：有心跳的正常 running 任务不受影响。"""
    init_project(tmp_path, "demo")
    release = Event()

    def handler(payload: dict, context: TaskContext) -> dict:
        del payload
        context.phase("model", "working")
        release.wait(10)
        return {"ok": True}

    runner = PersistentTaskRunner(tmp_path, "demo", handlers={"chapter_review": handler})
    try:
        task = runner.submit("chapter_review", {"chapter_id": "ch_001"})
        running = _wait_for(runner.store, task["task_id"], "running")
        runner._watchdog_tick()  # 默认阈值 600s，刚启动的任务远未卡死
        after = runner.store.load(task["task_id"])
        assert after["status"] == "running"
        assert after.get("cancel_requested") is False
    finally:
        release.set()
        runner.shutdown(wait=True)

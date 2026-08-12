"""Single-novel persistent task runner with cooperative cancellation."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from tools.task_store import TASK_PHASES, TaskStore, TaskStoreError

log = logging.getLogger(__name__)

# 看门狗：任务超过该秒数无任何心跳（updated_at 未变化）即视为卡死。
# 先协作请求取消（给 handler 检查点机会），宽限期内仍无进展则强制中断。
STUCK_AFTER_SECONDS = 600  # 10 分钟
STUCK_GRACE_SECONDS = 120  # 协作取消后再给 2 分钟
WATCHDOG_TICK_SECONDS = 60


class TaskCancelled(RuntimeError):
    pass


class TaskAwaitingConfirmation(RuntimeError):
    def __init__(self, result: dict[str, Any]):
        super().__init__("任务等待用户确认")
        self.result = result


TaskHandler = Callable[[dict[str, Any], "TaskContext"], dict[str, Any]]


class TaskContext:
    def __init__(self, store: TaskStore, task_id: str):
        self.store = store
        self.task_id = task_id
        self.phase_name = "queued"

    def phase(self, phase: str, note: str = "") -> None:
        if phase not in TASK_PHASES:
            raise TaskStoreError(f"Invalid task phase: {phase}")
        self.phase_name = phase
        self.store.transition(
            self.task_id,
            phase=phase,
            event="task_phase_changed",
            details={"note": note},
        )

    def cancellation_requested(self) -> bool:
        task = self.store.load(self.task_id)
        return bool(task and task.get("cancel_requested"))

    def checkpoint(self) -> None:
        if self.phase_name != "committing" and self.cancellation_requested():
            raise TaskCancelled("任务已取消")

    def progress_callback(self, phase: str, note: str = "") -> None:
        self.phase(phase, note)

    def persist_progress(self, result: dict[str, Any]) -> None:
        self.store.transition(
            self.task_id,
            updates={"result": result},
            event="task_progress_saved",
            details={"completed": len(result.get("completed_chapters") or [])},
        )

    def await_confirmation(self, result: dict[str, Any]) -> None:
        raise TaskAwaitingConfirmation(result)


class PersistentTaskRunner:
    """Run one task at a time for one novel and persist every state change."""

    def __init__(
        self,
        project_root: Path,
        novel_id: str,
        *,
        handlers: dict[str, TaskHandler] | None = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.novel_id = str(novel_id)
        self.store = TaskStore(self.project_root, self.novel_id)
        self.handlers = dict(handlers or {})
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"openwrite-{self.novel_id}-task",
        )
        self._futures: dict[str, Future[Any]] = {}
        self._lock = Lock()
        self.recovered = self.store.recover_interrupted()
        self._watchdog_stop = threading.Event()
        self._watchdog = threading.Thread(
            target=self._watchdog_loop,
            name=f"openwrite-{self.novel_id}-watchdog",
            daemon=True,
        )
        self._watchdog.start()

    def register(self, task_type: str, handler: TaskHandler) -> None:
        self.handlers[task_type] = handler

    def submit(
        self,
        task_type: str,
        payload: dict[str, Any],
        *,
        chapter_id: str = "",
        input_summary: str = "",
        retryable: bool = True,
        retry_of: str = "",
        attempt: int = 1,
    ) -> dict[str, Any]:
        if task_type not in self.handlers:
            raise TaskStoreError(f"No handler registered for task type: {task_type}")
        task = self.store.create(
            task_type,
            payload,
            chapter_id=chapter_id,
            input_summary=input_summary,
            retryable=retryable,
            retry_of=retry_of,
            attempt=attempt,
        )
        self._schedule(str(task["task_id"]))
        return task

    def retry(self, task_id: str) -> dict[str, Any]:
        previous = self.store.load(task_id)
        if previous is None:
            raise TaskStoreError("Task not found")
        if not previous.get("retryable"):
            raise TaskStoreError("Task is not retryable")
        if previous.get("status") not in {"failed", "cancelled", "interrupted"}:
            raise TaskStoreError("Only failed, cancelled or interrupted tasks can be retried")
        payload = self.store.materialize_input(previous)
        result = self.store.materialize_result(previous)
        if result.get("completed_chapters"):
            payload["_already_completed"] = list(result["completed_chapters"])
        if result.get("usage"):
            payload["_already_used"] = dict(result["usage"])
        return self.submit(
            str(previous["type"]),
            payload,
            chapter_id=str(previous.get("chapter_id") or ""),
            input_summary=str(previous.get("input_summary") or ""),
            retryable=True,
            retry_of=task_id,
            attempt=int(previous.get("attempt") or 1) + 1,
        )

    def cancel(self, task_id: str) -> dict[str, Any]:
        task = self.store.request_cancel(task_id)
        if task.get("status") == "cancelled":
            with self._lock:
                future = self._futures.get(task_id)
            if future is not None:
                future.cancel()
        return task

    def confirm(self, task_id: str) -> dict[str, Any]:
        previous = self.store.load(task_id)
        if previous is None:
            raise TaskStoreError("Task not found")
        if previous.get("status") != "awaiting_confirmation":
            raise TaskStoreError("Task is not awaiting confirmation")
        payload = self.store.materialize_input(previous)
        result = self.store.materialize_result(previous)
        payload["_already_completed"] = list(result.get("completed_chapters") or [])
        if result.get("usage"):
            payload["_already_used"] = dict(result["usage"])
        return self.submit(
            str(previous["type"]),
            payload,
            chapter_id=str(previous.get("chapter_id") or ""),
            input_summary=str(previous.get("input_summary") or ""),
            retryable=bool(previous.get("retryable")),
            retry_of=task_id,
            attempt=int(previous.get("attempt") or 1) + 1,
        )

    def shutdown(self, *, wait: bool = False) -> None:
        self._watchdog_stop.set()
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _watchdog_loop(self) -> None:
        """周期扫描 running 任务：超时无心跳 → 协作取消 → 宽限后强制中断。"""
        while not self._watchdog_stop.wait(WATCHDOG_TICK_SECONDS):
            try:
                self._watchdog_tick()
            except Exception:
                log.exception("watchdog tick failed")

    def _watchdog_tick(self) -> None:
        now = datetime.now(timezone.utc)
        for task in self.store.list(statuses={"running"}, limit=500):
            task_id = str(task.get("task_id") or "")
            if not task_id:
                continue
            updated_raw = task.get("updated_at")
            if not updated_raw:
                continue
            try:
                updated = datetime.fromisoformat(str(updated_raw))
            except ValueError:
                continue
            age = (now - updated).total_seconds()
            if age <= STUCK_AFTER_SECONDS:
                continue
            if task.get("cancel_requested"):
                if age > STUCK_AFTER_SECONDS + STUCK_GRACE_SECONDS:
                    self.store.transition(
                        task_id,
                        status="interrupted",
                        updates={
                            "error": {
                                "code": "STUCK_TIMEOUT",
                                "message": (
                                    f"任务超过 {STUCK_AFTER_SECONDS}s 无心跳，"
                                    f"协作取消后宽限 {STUCK_GRACE_SECONDS}s 仍无进展，"
                                    "已自动中断；可从持久化阶段恢复重试"
                                ),
                                "recoverable": True,
                            }
                        },
                        event="task_stuck_interrupted",
                        details={
                            "stuck_seconds": int(age),
                            "phase": str(task.get("phase") or ""),
                        },
                    )
                    log.warning(
                        "task %s stuck (%ds) -> interrupted", task_id, int(age)
                    )
            else:
                self.store.request_cancel(task_id)
                log.warning("task %s stuck (%ds) -> cancel requested", task_id, int(age))

    def _schedule(self, task_id: str) -> None:
        future = self._executor.submit(self._run, task_id)
        with self._lock:
            self._futures[task_id] = future
        future.add_done_callback(lambda completed: self._forget(task_id, completed))

    def _forget(self, task_id: str, future: Future[Any]) -> None:
        del future
        with self._lock:
            self._futures.pop(task_id, None)

    def _run(self, task_id: str) -> None:
        task = self.store.load(task_id)
        if task is None or task.get("status") != "pending":
            return
        handler = self.handlers.get(str(task.get("type") or ""))
        if handler is None:
            self.store.transition(
                task_id,
                status="failed",
                updates={
                    "error": {
                        "code": "TASK_HANDLER_MISSING",
                        "message": "任务处理器不存在",
                        "recoverable": False,
                    }
                },
                event="task_failed",
            )
            return
        context = TaskContext(self.store, task_id)
        try:
            self.store.transition(
                task_id,
                status="running",
                phase="reading",
                event="task_started",
            )
            context.phase_name = "reading"
            context.checkpoint()
            payload = self.store.materialize_input(task)
            result = handler(payload, context)
            current = self.store.load(task_id)
            if current is not None and current.get("status") in {
                "interrupted",
                "cancelled",
            }:
                # 看门狗/用户已在执行期间终止任务：丢弃本次结果，保留终止状态，
                # 避免后到完成的 handler 覆盖中断标记（结果不可信）。
                self.store.transition(
                    task_id,
                    updates={"result": result},
                    event="task_stale_result_discarded",
                )
                return
            context.checkpoint()
            self.store.transition(
                task_id,
                status="completed",
                phase="complete",
                updates={"result": result, "error": None},
                event="task_completed",
            )
        except TaskAwaitingConfirmation as exc:
            self.store.transition(
                task_id,
                status="awaiting_confirmation",
                updates={"result": exc.result, "error": None},
                event="task_awaiting_confirmation",
            )
        except TaskCancelled as exc:
            self.store.transition(
                task_id,
                status="cancelled",
                updates={
                    "error": {
                        "code": "TASK_CANCELLED",
                        "message": str(exc),
                        "recoverable": True,
                    }
                },
                event="task_cancelled",
            )
        except Exception as exc:
            self.store.transition(
                task_id,
                status="failed",
                updates={
                    "error": {
                        "code": str(getattr(exc, "code", "TASK_FAILED")),
                        "message": str(exc),
                        "recoverable": bool(task.get("retryable")),
                    }
                },
                event="task_failed",
            )

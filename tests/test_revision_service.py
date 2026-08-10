from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.cli import _save_chapter
from tools.init_project import init_project
from tools.review_store import ReviewStore
from tools.revision_service import RevisionError, RevisionService
from tools.revision_store import RevisionStore


def _project(tmp_path: Path) -> tuple[Path, Path]:
    init_project(tmp_path, "demo")
    chapter = _save_chapter(
        tmp_path,
        "demo",
        "ch_001",
        "第一章：雨夜",
        "林舟推开钟楼的门。\n\n门后没有人，只有一只停摆的钟。",
    )
    return tmp_path, chapter


def test_revision_store_persists_proposals_outside_canonical_source(tmp_path: Path):
    root, _ = _project(tmp_path)
    store = RevisionStore(root, "demo")
    proposal = {
        "proposal_id": store.create_id(),
        "chapter_id": "ch_001",
        "kind": "selection_rewrite",
        "status": "proposed",
        "source_revision": "sha256:test",
        "selection": {"start": 0, "end": 1, "original_text": "林"},
        "request": {},
        "review_issue_ids": [],
        "replacement_text": "他",
        "rationale": "",
        "risk_flags": [],
        "created_at": "2026-08-02T00:00:00+00:00",
        "applied_at": None,
    }

    path = store.save(proposal)

    assert path.is_file()
    assert "data/revisions/ch_001" in path.as_posix()
    assert store.load(proposal["proposal_id"]) == proposal


def test_selection_revision_is_previewed_then_atomically_applied(tmp_path: Path):
    root, chapter = _project(tmp_path)
    original = chapter.read_text(encoding="utf-8")
    selected = "门后没有人"
    start = original.index(selected)

    service = RevisionService(
        root,
        "demo",
        generator=lambda payload: {
            "replacement_text": "门后仍然没有人",
            "rationale": "保留事件结果，只增加迟疑感。",
            "risk_flags": ["节奏轻微放慢"],
        },
    )
    proposal = service.create_selection(
        chapter_id="ch_001",
        start=start,
        end=start + len(selected),
        original_text=selected,
        action="rewrite",
        instruction="让判断更迟疑",
    )

    assert chapter.read_text(encoding="utf-8") == original
    assert proposal["status"] == "proposed"
    assert proposal["diff"]["hunks"]

    applied = service.apply(proposal["proposal_id"])

    assert applied["status"] == "applied"
    assert "门后仍然没有人" in chapter.read_text(encoding="utf-8")
    backup = root / "data" / "novels" / "demo" / applied["backup_path"]
    assert backup.read_text(encoding="utf-8") == original


def test_revision_apply_accepts_reviewed_subset_and_records_hunks(tmp_path: Path):
    root, chapter = _project(tmp_path)
    original = chapter.read_text(encoding="utf-8")
    selected = "林舟推开钟楼的门。\n\n门后没有人，只有一只停摆的钟。"
    start = original.index(selected)
    service = RevisionService(
        root,
        "demo",
        generator=lambda payload: "林舟缓缓推开钟楼的门。\n\n门后仍然没有人，只有一只停摆的钟。",
    )
    proposal = service.create_selection(
        chapter_id="ch_001",
        start=start,
        end=start + len(selected),
        original_text=selected,
    )

    assert len(proposal["diff"]["hunks"]) == 2
    accepted = "林舟缓缓推开钟楼的门。\n\n门后没有人，只有一只停摆的钟。"
    applied = service.apply(
        proposal["proposal_id"],
        replacement_text=accepted,
        selected_hunk_ids=["hunk_0"],
    )

    assert accepted in chapter.read_text(encoding="utf-8")
    assert applied["accepted_replacement_text"] == accepted
    assert applied["selected_hunk_ids"] == ["hunk_0"]


def test_revision_apply_marks_proposal_stale_when_source_changed(tmp_path: Path):
    root, chapter = _project(tmp_path)
    original = chapter.read_text(encoding="utf-8")
    selected = "停摆的钟"
    start = original.index(selected)
    service = RevisionService(root, "demo", generator=lambda payload: "生锈的钟")
    proposal = service.create_selection(
        chapter_id="ch_001",
        start=start,
        end=start + len(selected),
        original_text=selected,
    )
    chapter.write_text(original + "\n\n窗外传来脚步声。", encoding="utf-8")

    with pytest.raises(RevisionError) as conflict:
        service.apply(proposal["proposal_id"])

    assert conflict.value.code == "DOCUMENT_CONFLICT"
    assert conflict.value.recoverable is True
    assert service.get(proposal["proposal_id"])["status"] == "stale"


def test_review_issue_revision_uses_quote_anchor_and_invalidates_review(tmp_path: Path):
    root, chapter = _project(tmp_path)
    content = chapter.read_text(encoding="utf-8")
    quote = "门后没有人"
    start = content.index(quote)
    ReviewStore(root, "demo").save(
        "ch_001",
        {
            "ok": True,
            "score": 76,
            "passed": False,
            "issues": 1,
            "issue_details": [
                {
                    "id": "issue_door",
                    "dimension": "pacing.opening",
                    "severity": "high",
                    "summary": "判断落得过快",
                    "evidence": {"quote": quote},
                    "anchor": {"start_hint": start, "end_hint": start + len(quote)},
                    "suggestion": "保留一瞬迟疑",
                    "auto_fixable": True,
                }
            ],
        },
    )
    captured: dict = {}

    def generator(payload: dict) -> dict:
        captured.update(payload)
        return {
            "replacement_text": "门后看起来没有人",
            "rationale": "把绝对判断改成现场观察。",
            "risk_flags": [],
        }

    service = RevisionService(root, "demo", generator=generator)
    proposal = service.create_from_review(
        chapter_id="ch_001",
        issue_ids=["issue_door"],
    )
    applied = service.apply(proposal["proposal_id"])

    assert captured["review_issues"][0]["dimension"] == "pacing.opening"
    assert "门后看起来没有人" in chapter.read_text(encoding="utf-8")
    review = ReviewStore(root, "demo").load("ch_001")
    assert review is not None and review["stale"] is True
    assert review["revision_history"][0]["proposal_id"] == applied["proposal_id"]


def test_revision_validation_failure_keeps_document_and_proposal_unapplied(tmp_path: Path):
    root, chapter = _project(tmp_path)
    original = chapter.read_text(encoding="utf-8")
    selected = "门后没有人"
    start = original.index(selected)
    service = RevisionService(
        root,
        "demo",
        generator=lambda payload: "不是没人，而是所有人都藏了起来",
    )
    proposal = service.create_selection(
        chapter_id="ch_001",
        start=start,
        end=start + len(selected),
        original_text=selected,
    )

    with pytest.raises(RevisionError) as invalid:
        service.apply(proposal["proposal_id"])

    assert invalid.value.code == "REVISION_VALIDATION_FAILED"
    assert chapter.read_text(encoding="utf-8") == original
    stored = json.loads(
        RevisionStore(root, "demo")
        .path_for(proposal["proposal_id"], chapter_id="ch_001")
        .read_text(encoding="utf-8")
    )
    assert stored["status"] == "proposed"


def _save_issue(root: Path, chapter_id: str, *issues: dict) -> None:
    ReviewStore(root, "demo").save(
        chapter_id,
        {
            "ok": True,
            "score": 76,
            "passed": False,
            "issues": len(issues),
            "issue_details": list(issues),
        },
    )


def _revision_with(root: Path, generator) -> RevisionService:
    return RevisionService(root, "demo", generator=generator)


def test_review_issue_whitespace_drift_anchors_via_fuzzy_match(tmp_path: Path):
    root, chapter = _project(tmp_path)
    content = chapter.read_text(encoding="utf-8")
    quote = "门后没有人，只有一只  停摆的钟"  # 引文多了一个空格，精确匹配失效
    _save_issue(
        root,
        "ch_001",
        {"id": "issue_space", "dimension": "pacing", "severity": "high",
         "summary": "停顿感不足", "evidence": {"quote": quote}, "suggestion": "增加迟疑"},
    )
    captured: dict = {}

    def generator(payload: dict) -> dict:
        captured.update(payload)
        return {"replacement_text": "门后没有人，只有一只停摆的钟。", "rationale": "", "risk_flags": []}

    proposal = _revision_with(root, generator).create_from_review(
        chapter_id="ch_001", issue_ids=["issue_space"]
    )

    assert captured["selection"] == "门后没有人，只有一只停摆的钟"
    assert proposal["request"]["anchor_degraded"] == []


def test_review_issue_repeated_quote_disambiguated_by_context(tmp_path: Path):
    root, _ = _project(tmp_path)
    body = "林舟先去了东街。门后没有人。\n\n他又去了西街。门后没有人。"
    _save_chapter(root, "demo", "ch_001", "第二章：两条街", body)
    _save_issue(
        root,
        "ch_001",
        {"id": "issue_repeat", "dimension": "pacing", "severity": "high",
         "summary": "重复判断", "evidence": {"quote": "门后没有人", "context_before": "西街"},
         "suggestion": "只保留一处"},
    )
    captured: dict = {}

    def generator(payload: dict) -> dict:
        captured.update(payload)
        return {"replacement_text": "门后没有人", "rationale": "", "risk_flags": []}

    proposal = _revision_with(root, generator).create_from_review(
        chapter_id="ch_001", issue_ids=["issue_repeat"]
    )

    # 引文出现两次，context_before「西街」应把锚定到第二处（前文以「西街」收尾）
    assert captured["selection"] == "门后没有人"
    assert captured["context_before"].endswith("他又去了西街。")
    assert proposal["request"]["anchor_degraded"] == []


def test_review_issue_missing_quote_falls_back_to_chapter_scope(tmp_path: Path):
    root, chapter = _project(tmp_path)
    content = chapter.read_text(encoding="utf-8")
    _save_issue(
        root,
        "ch_001",
        {"id": "issue_ghost", "dimension": "pacing", "severity": "high",
         "summary": "叙述节奏过慢", "evidence": {"quote": "不存在于本章的引文"},
         "suggestion": "加快节奏"},
    )
    captured: dict = {}

    def generator(payload: dict) -> dict:
        captured.update(payload)
        return {"replacement_text": content, "rationale": "", "risk_flags": []}

    proposal = _revision_with(root, generator).create_from_review(
        chapter_id="ch_001", issue_ids=["issue_ghost"]
    )

    assert proposal["request"]["anchor_degraded"] == ["issue_ghost"]
    assert proposal["selection"]["start"] == 0
    assert proposal["selection"]["end"] == len(content)
    assert "[定位提示]" in proposal["request"]["instruction"]
    assert "issue_ghost" in proposal["request"]["instruction"]


def test_review_issue_missing_quote_anchors_via_summary_terms(tmp_path: Path):
    root, chapter = _project(tmp_path)
    content = chapter.read_text(encoding="utf-8")
    # 引文完全失效，但 summary 词项「停摆」能定位到第二段
    _save_issue(
        root,
        "ch_001",
        {"id": "issue_terms", "dimension": "pacing", "severity": "high",
         "summary": "停摆的钟需要修理", "evidence": {"quote": "幽灵引文"},
         "suggestion": "交代钟的来由"},
    )
    captured: dict = {}

    def generator(payload: dict) -> dict:
        captured.update(payload)
        return {"replacement_text": "门后没有人，只有一只停摆的钟。", "rationale": "", "risk_flags": []}

    proposal = _revision_with(root, generator).create_from_review(
        chapter_id="ch_001", issue_ids=["issue_terms"]
    )

    # 锚定到含标题全文的第 5 行（正文第二段），而不是整章
    assert proposal["selection"]["start"] == 21
    assert proposal["selection"]["end"] == 21 + len("门后没有人，只有一只停摆的钟。")
    assert proposal["request"]["anchor_degraded"] == []


def test_review_issue_partial_anchor_failure_expands_union_to_chapter(tmp_path: Path):
    root, chapter = _project(tmp_path)
    content = chapter.read_text(encoding="utf-8")
    _save_issue(
        root,
        "ch_001",
        {"id": "issue_ok", "dimension": "pacing", "severity": "high",
         "summary": "停摆的钟", "evidence": {"quote": "停摆的钟"}, "suggestion": "修钟"},
        {"id": "issue_ghost", "dimension": "pacing", "severity": "high",
         "summary": "叙述节奏过慢", "evidence": {"quote": "幽灵引文"}, "suggestion": "加快"},
    )
    captured: dict = {}

    def generator(payload: dict) -> dict:
        captured.update(payload)
        return {"replacement_text": content, "rationale": "", "risk_flags": []}

    proposal = _revision_with(root, generator).create_from_review(
        chapter_id="ch_001", issue_ids=["issue_ok", "issue_ghost"]
    )

    # 一个锚定成功、一个失败 → 失败者扩到整章，union 覆盖全章
    assert proposal["request"]["anchor_degraded"] == ["issue_ghost"]
    assert proposal["selection"]["start"] == 0
    assert proposal["selection"]["end"] == len(content)

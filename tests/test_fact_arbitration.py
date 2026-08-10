"""写章后事实仲裁：正则交叉校验 LLM delta。"""

from pathlib import Path

from tools.fact_arbitration import arbitrate_chapter, arbitrate_facts
from tools.init_project import init_project
from tools.truth_manager import TruthFilesManager


def test_arbitrate_facts_flags_facts_missing_from_delta():
    content = "林琛获得了青铜怀表，支付了 300 金币。新角色：红衣女子。"

    issues = arbitrate_facts(content, chapter_number=1, state_delta=None, legacy_updates={})

    descriptions = "\n".join(issue["description"] for issue in issues)
    assert "青铜怀表" in descriptions
    assert "300" in descriptions
    assert "红衣女子" in descriptions
    assert all(issue["severity"] == "warning" for issue in issues)
    assert all(issue["category"] == "continuity_fact" for issue in issues)


def test_arbitrate_facts_is_silent_when_delta_covers_facts():
    content = "林琛获得了青铜怀表。新角色：红衣女子。"
    delta = {
        "operations": [
            {"op": "append", "collection": "ledger", "value": "获得青铜怀表"},
            {"op": "create", "collection": "characters", "value": {"name": "红衣女子"}},
        ]
    }

    assert arbitrate_facts(content, 1, state_delta=delta, legacy_updates={}) == []


def test_arbitrate_facts_uses_legacy_updates_as_coverage():
    content = "林琛失去了家传玉佩。"
    updates = {"current_state": "林琛失去了家传玉佩，前往钟楼。"}

    assert arbitrate_facts(content, 1, state_delta=None, legacy_updates=updates) == []


def test_arbitrate_facts_empty_content_or_covered_returns_no_issues():
    assert arbitrate_facts("", 1) == []
    assert arbitrate_facts("钟楼在雨中静立。", 1) == []


def test_arbitrate_chapter_adds_truth_structure_drift_issues(tmp_path: Path):
    init_project(tmp_path, "demo", "仲裁结构校验")
    novel_root = tmp_path / "data" / "novels" / "demo"
    world = novel_root / "data" / "world"
    world.mkdir(parents=True, exist_ok=True)
    (world / "current_state.md").write_text(
        "+++\nid = \"wrong_id\"\ntype = \"drifted\"\n+++\n\n正文。\n",
        encoding="utf-8",
    )
    (world / "ledger.md").write_text("纯 Markdown，无 front matter", encoding="utf-8")

    issues = arbitrate_chapter(
        tmp_path, "demo", "ch_001", "正文", state_delta=None, legacy_updates={}
    )

    descriptions = "\n".join(issue["description"] for issue in issues)
    assert "current_state" in descriptions and "id" in descriptions
    assert "wrong_id" in descriptions
    assert "ledger" in descriptions and "front matter" in descriptions


def test_validate_truth_structure_detects_each_drift_class(tmp_path: Path):
    init_project(tmp_path, "demo", "结构校验")
    manager = TruthFilesManager(tmp_path, "demo")
    assert manager.validate_truth_structure() == []

    world = tmp_path / "data" / "novels" / "demo" / "data" / "world"
    (world / "current_state.md").write_text(
        "+++\nid = \"current_state\"\ntype = \"runtime_truth\"\n+++\n\nOK。\n",
        encoding="utf-8",
    )
    assert manager.validate_truth_structure() == []

    (world / "current_state.md").write_text(
        "+++\nid = \"other\"\ntype = \"runtime_truth\"\n+++\n\n正文。\n",
        encoding="utf-8",
    )
    findings = manager.validate_truth_structure()
    assert any(f["attr"] == "current_state" and f["field"] == "id" for f in findings)

    (world / "ledger.md").unlink(missing_ok=True)
    assert not any(f["attr"] == "ledger" for f in manager.validate_truth_structure())

    (world / "relationships.md").write_text("+++\nid = \"relationships\"\n类型坏了\n+++", encoding="utf-8")
    assert any(
        f["attr"] == "relationships" and f["field"] == "frontmatter"
        for f in manager.validate_truth_structure()
    )

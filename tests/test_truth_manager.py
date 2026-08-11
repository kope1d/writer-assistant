import json
from pathlib import Path

import pytest

from tools.runtime_state import RuntimeStateError, legacy_updates_to_delta
from tools.truth_manager import TruthFiles, TruthFilesManager


def test_save_truth_files_writes_frontmatter_and_load_returns_body(tmp_path: Path):
    manager = TruthFilesManager(tmp_path, "demo")
    truth = TruthFiles(
        current_state="# 当前状态\n\n正文A",
        ledger="# 账本\n\n正文B",
        relationships="# 关系\n\n正文C",
    )

    manager.save_truth_files(truth)

    current_state_text = (manager.world_dir / "current_state.md").read_text(encoding="utf-8")
    assert current_state_text.startswith("+++\n")
    assert 'id = "current_state"' in current_state_text
    assert 'type = "runtime_truth"' in current_state_text

    loaded = manager.load_truth_files()
    assert loaded.current_state == "# 当前状态\n\n正文A"
    assert loaded.ledger == "# 账本\n\n正文B"
    assert loaded.relationships == "# 关系\n\n正文C"
    assert loaded.metadata["current_state"]["id"] == "current_state"


def test_load_truth_files_parses_existing_frontmatter(tmp_path: Path):
    manager = TruthFilesManager(tmp_path, "demo")
    manager.world_dir.mkdir(parents=True, exist_ok=True)
    (manager.world_dir / "current_state.md").write_text(
        """+++
id = "current_state"
type = "runtime_truth"
summary = "当前局势摘要。"
detail_refs = ["scene", "actors"]
+++

# 当前状态

正文内容。
""",
        encoding="utf-8",
    )

    loaded = manager.load_truth_files()

    assert loaded.current_state == "# 当前状态\n\n正文内容。\n"
    assert loaded.metadata["current_state"]["summary"] == "当前局势摘要。"


def _manager_with_truth(tmp_path: Path) -> TruthFilesManager:
    manager = TruthFilesManager(tmp_path, "demo")
    manager.save_truth_files(
        TruthFiles(
            current_state="# 当前状态\n\n钟楼仍在运行。",
            ledger="# 账本\n\n负债 500 金币。",
            relationships="# 关系\n\n林琛与老钟匠是师徒。",
        )
    )
    return manager


# ── update_truth_files ─────────────────────────────────────────────


def test_update_truth_files_replaces_only_named_fields(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)

    manager.update_truth_files(
        manager.load_truth_files(), {"current_state": "# 当前状态\n\n钟楼停摆。"}
    )

    loaded = manager.load_truth_files()
    assert loaded.current_state == "# 当前状态\n\n钟楼停摆。"
    assert loaded.ledger == "# 账本\n\n负债 500 金币。"  # 未更新的文件原样保留


def test_update_truth_files_ignores_unknown_field_names(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)

    manager.update_truth_files(manager.load_truth_files(), {"nonexistent": "x"})

    assert manager.load_truth_files().current_state == "# 当前状态\n\n钟楼仍在运行。"


# ── 快照生命周期 ───────────────────────────────────────────────────


def test_snapshot_create_list_and_restore_round_trip(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)
    manager.apply_runtime_delta(
        legacy_updates_to_delta(
            {"current_state": "钟楼被雷击停工。", "ledger": "赔偿 1200 金币。"},
            chapter_id="ch_002",
        )
    )
    changed = manager.load_truth_files()
    assert "雷击" in changed.current_state

    snapshot_id = manager.create_snapshot(2)
    listed = manager.list_snapshots()
    assert len(listed) == 1
    assert listed[0]["id"] == snapshot_id
    assert listed[0]["chapter_number"] == 2

    # 再改一次，然后回滚到快照
    manager.update_truth_files(
        manager.load_truth_files(), {"current_state": "# 当前状态\n\n全部推倒重来。"}
    )
    assert manager.restore_snapshot(snapshot_id)
    restored = manager.load_truth_files()
    assert "雷击" in restored.current_state
    assert "赔偿 1200 金币" in restored.ledger


def test_snapshot_restore_missing_or_corrupt_returns_false(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)

    assert not manager.restore_snapshot("snapshot_999_missing")

    bad = manager.snapshots_dir / "snapshot_1_00000000.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not valid json", encoding="utf-8")
    assert not manager.restore_snapshot("snapshot_1_00000000")
    assert manager.load_truth_files().current_state == "# 当前状态\n\n钟楼仍在运行。"


def test_load_snapshot_before_targets_previous_chapter(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)
    before = manager.create_snapshot(1)

    manager.apply_runtime_delta(
        legacy_updates_to_delta({"current_state": "第二章发生地陷。"}, chapter_id="ch_002")
    )
    manager.create_snapshot(2)

    # ch_003 写前应取 ch_002 的快照；ch_002 写前取 ch_001 的
    assert manager.load_snapshot_before(3) is not None
    assert "地陷" in manager.load_snapshot_before(3).current_state
    pre_second = manager.load_snapshot_before(2)
    assert pre_second is not None and pre_second.current_state.startswith("# 当前状态")
    # ch_001 写前无更早快照（target = max(0, 0) 无文件）→ None
    assert manager.load_snapshot_before(1) is None
    assert manager.load_snapshot_before(0) is None


def test_load_snapshot_before_reads_legacy_field_names(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)
    manager.snapshots_dir.mkdir(parents=True, exist_ok=True)
    (manager.snapshots_dir / "snapshot_3_20200101_000000.json").write_text(
        json.dumps(
            {
                "id": "snapshot_3_20200101_000000",
                "chapter_number": 3,
                "files": {
                    "current_state": "旧格式正文",
                    "particle_ledger": "旧账本",
                    "character_matrix": "旧关系",
                },
            }
        ),
        encoding="utf-8",
    )

    snapshot = manager.load_snapshot_before(4)
    assert snapshot is not None
    assert snapshot.current_state == "旧格式正文"
    assert snapshot.ledger == "旧账本"
    assert snapshot.relationships == "旧关系"


# ── apply_runtime_delta ────────────────────────────────────────────


def test_apply_runtime_delta_appends_and_projects_to_truth_files(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)
    delta = legacy_updates_to_delta(
        {"current_state": "钟楼塔尖出现裂纹。", "relationships": "林琛与老钟匠决裂。"},
        chapter_id="ch_003",
    )

    updated = manager.apply_runtime_delta(delta)

    assert updated.revision == 1
    assert updated.source_chapter == "ch_003"
    # 投影写回真相文件，保持人机同读
    loaded = manager.load_truth_files()
    assert "塔尖出现裂纹" in loaded.current_state
    assert "决裂" in loaded.relationships


def test_apply_runtime_delta_rejects_stale_source_revision(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)
    manager.apply_runtime_delta(
        legacy_updates_to_delta({"current_state": "第一版。"}, chapter_id="ch_001")
    )

    with pytest.raises(RuntimeStateError, match="状态版本冲突"):
        manager.apply_runtime_delta(
            legacy_updates_to_delta(
                {"current_state": "旧快照的修改。"}, chapter_id="ch_002", source_revision=0
            )
        )
    # 被拒绝的 delta 不落地
    assert "第一版" in manager.load_truth_files().current_state


# ── 格式漂移与降级 ─────────────────────────────────────────────────


def test_load_truth_files_survives_corrupt_front_matter(tmp_path: Path):
    manager = TruthFilesManager(tmp_path, "demo")
    manager.world_dir.mkdir(parents=True, exist_ok=True)
    (manager.world_dir / "current_state.md").write_text(
        "+++\nid = \"current_state\"\ntype = \"runtime_truth\"\n+++  ← 未闭合的 TOML 块\n正文仍可读。",
        encoding="utf-8",
    )

    loaded = manager.load_truth_files()

    # 解析失败时降级为默认 metadata + 原始正文，不中断写作链
    assert "正文仍可读" in loaded.current_state
    assert loaded.metadata["current_state"]["type"] == "runtime_truth"


# ── 事实抽取（低保真正则兜底） ─────────────────────────────────────


def test_extract_facts_from_chapter_captures_regex_facts():
    manager = TruthFilesManager(Path("unused"), "demo")
    content = (
        "林琛获得了青铜怀表，失去了家传玉佩。"
        "他支付了 300 金币。新角色：红衣女子。"
        "两人关系对彼此变成了敌人。"
    )

    facts = manager.extract_facts_from_chapter(content, chapter_number=1)

    assert facts.get("items_gained") == ["青铜怀表"]
    assert facts.get("items_lost") == ["家传玉佩"]
    assert facts.get("money_changes") == [300]
    assert facts.get("new_characters") == ["红衣女子"]
    assert any("敌人" in item for item in facts.get("relationship_changes", []))


def test_extract_facts_from_chapter_empty_content_yields_no_facts():
    manager = TruthFilesManager(Path("unused"), "demo")

    assert manager.extract_facts_from_chapter("", chapter_number=1) == {}


# ── POV 伏笔过滤 ───────────────────────────────────────────────────


def test_filter_hooks_by_pov_keeps_known_and_drops_unknown():
    manager = TruthFilesManager(Path("unused"), "demo")
    hooks = "钟楼的秘密只有林琛知道\n老钟匠藏着青铜怀表\n城主的计划未公开"

    filtered = manager.filter_hooks_by_pov(hooks, pov_character="林琛", chapter_summaries="")

    assert "林琛" in filtered
    assert "城主" not in filtered


def test_filter_hooks_by_pov_without_pov_returns_all(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)
    hooks = "任意伏笔\n另一条伏笔"

    assert manager.filter_hooks_by_pov(hooks, pov_character="", chapter_summaries="") == hooks


# ── 结构校验（事实仲裁的地基） ─────────────────────────────────────


def test_validate_truth_structure_clean_after_init(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)

    assert manager.validate_truth_structure() == []


def test_validate_truth_structure_flags_each_drift_class(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)
    world = manager.world_dir

    (world / "current_state.md").write_text(
        "+++\nid = \"other\"\ntype = \"runtime_truth\"\n+++\n\n正文。\n",
        encoding="utf-8",
    )
    (world / "ledger.md").write_text("纯 Markdown 无 front matter", encoding="utf-8")
    (world / "relationships.md").unlink()

    findings = manager.validate_truth_structure()
    by = {(item["attr"], item["field"]): item for item in findings}
    assert by[("current_state", "id")]["actual"] == "other"
    assert by[("ledger", "frontmatter")]["actual"] == "缺失（legacy 纯 Markdown）"
    # 文件缺失是合法的初始状态，不算漂移
    assert ("relationships", "file") not in by

    (world / "current_state.md").write_text(
        "+++\nid = \"current_state\"\n类型坏了\n+++",
        encoding="utf-8",
    )
    assert any(
        item["attr"] == "current_state" and item["field"] == "frontmatter"
        for item in manager.validate_truth_structure()
    )


# ── TruthFiles 别名兼容 ──────────────────────────────────────────────


def test_truthfiles_legacy_alias_getter():
    t = TruthFiles(current_state="A", ledger="B", relationships="C")

    assert t.particle_ledger == "B"
    assert t.character_matrix == "C"


def test_truthfiles_legacy_alias_setter():
    t = TruthFiles(current_state="A", ledger="B", relationships="C")

    t.particle_ledger = "新账本"
    t.character_matrix = "新关系"

    assert t.ledger == "新账本"
    assert t.relationships == "新关系"


def test_truthfiles_dir_excludes_metadata():
    t = TruthFiles(current_state="A", ledger="B", relationships="C")

    assert "metadata" not in dir(t)
    assert "current_state" in dir(t)


def test_truthfiles_unknown_attr_raises():
    t = TruthFiles()

    with pytest.raises(AttributeError):
        _ = t.nonexistent


# ── 默认元数据与摘要 ─────────────────────────────────────────────────


def test_default_metadata_produces_expected_keys(tmp_path: Path):
    manager = TruthFilesManager(tmp_path, "demo")

    meta_state = manager._default_metadata("current_state", "")
    assert meta_state["id"] == "current_state"
    assert meta_state["type"] == "runtime_truth"
    assert "scene" in meta_state["detail_refs"]

    meta_ledger = manager._default_metadata("ledger", "")
    assert "resources" in meta_ledger["detail_refs"]

    meta_rel = manager._default_metadata("relationships", "")
    assert "bonds" in meta_rel["detail_refs"]


def test_summarize_truth_content_extracts_first_meaningful_line():
    manager = TruthFilesManager(Path("unused"), "demo")

    # 跳过标题和表格行，剥掉键前缀
    assert "钟楼已修复" in manager._summarize_truth_content(
        "# 世界状态\n\n钟楼已修复，城市恢复平静。"
    )
    assert "钟楼仍在运行" in manager._summarize_truth_content(
        "| 物品 | 状态 |\n|------|------|\n关键事实：钟楼仍在运行。"
    )
    # 空内容
    assert manager._summarize_truth_content("") == ""


# ── list_snapshots ────────────────────────────────────────────────────


def test_list_snapshots_empty(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)

    assert manager.list_snapshots() == []


def test_list_snapshots_corrupt_file_skipped(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)
    manager.snapshots_dir.mkdir(parents=True, exist_ok=True)
    (manager.snapshots_dir / "snapshot_1_good.json").write_text(
        '{"id": "s1", "chapter_number": 1, "created_at": "2024-01-01T00:00:00"}',
        encoding="utf-8",
    )
    (manager.snapshots_dir / "snapshot_2_bad.json").write_text(
        "{not valid",
        encoding="utf-8",
    )

    listed = manager.list_snapshots()
    assert len(listed) == 1
    assert listed[0]["id"] == "s1"


# ── POV 伏笔过滤（章摘要辅助路径）─────────────────────────────────────


def test_filter_hooks_by_pov_keeps_mentioned_in_summaries(tmp_path: Path):
    manager = _manager_with_truth(tmp_path)
    hooks = "钟楼的秘密\n城主的计划\n老钟匠的往事"

    filtered = manager.filter_hooks_by_pov(
        hooks,
        pov_character="城主",
        chapter_summaries="城主在第一章出现在钟楼，与林琛交谈。",
    )

    # "城主" 出现在 hooks 里 → 直接保留
    assert "城主的计划" in filtered
    # "林琛" 未出现在 hooks 的该行里；但 summaries 提到"城主"场景
    # 当前启发式：只要 summaries 里任一角色出现，全保留
    assert len(filtered.split("\n")) == 3


# ── 首次运行（目录不存在）─────────────────────────────────────────────


def test_load_truth_files_first_run_no_dirs(tmp_path: Path):
    manager = TruthFilesManager(tmp_path, "fresh_novel")

    truth = manager.load_truth_files()

    # 首次运行不应出错，返回默认空 TruthFiles
    assert truth.current_state == ""
    assert truth.ledger == ""
    assert truth.relationships == ""
    assert truth.metadata["current_state"]["id"] == "current_state"

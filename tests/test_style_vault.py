from __future__ import annotations

import pytest
import yaml

from tools.style_vault import (
    current_style_id,
    list_style_profiles,
    set_current_style_id,
)


def test_list_style_profiles_marks_ready_sources(tmp_path):
    sources = tmp_path / "data" / "novels" / "demo" / "data" / "sources"
    ready = sources / "lu_xun" / "style"
    ready.mkdir(parents=True)
    (ready / "summary.md").write_text(
        'description: "冷峻白描"\n\n正文内容。\n',
        encoding="utf-8",
    )
    pending = sources / "pending"
    pending.mkdir(parents=True)

    profiles = list_style_profiles(tmp_path, "demo")
    by_id = {profile["id"]: profile for profile in profiles}

    assert by_id["lu_xun"]["ready"] is True
    assert by_id["lu_xun"]["description"] == "冷峻白描"
    assert by_id["pending"]["ready"] is False
    assert by_id["pending"]["description"] == ""


def test_current_style_id_reads_config():
    assert current_style_id({"style_id": "  lu_xun  "}) == "lu_xun"
    assert current_style_id({}) == ""


def test_set_current_style_id_persists_selection(tmp_path):
    sources = tmp_path / "data" / "novels" / "demo" / "data" / "sources"
    style_dir = sources / "lu_xun" / "style"
    style_dir.mkdir(parents=True)
    (style_dir / "summary.md").write_text("# 冷峻白描\n", encoding="utf-8")
    config_path = tmp_path / "novel_config.yaml"
    config_path.write_text("novel_id: demo\nstyle_id: demo\n", encoding="utf-8")

    set_current_style_id(tmp_path, "demo", "lu_xun")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["style_id"] == "lu_xun"
    assert config["novel_id"] == "demo"


def test_set_current_style_id_rejects_unknown_profile(tmp_path):
    config_path = tmp_path / "novel_config.yaml"
    config_path.write_text("novel_id: demo\n", encoding="utf-8")

    with pytest.raises(ValueError, match="文风档案不存在"):
        set_current_style_id(tmp_path, "demo", "missing")

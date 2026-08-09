from __future__ import annotations

from tools.style_vault import current_style_id, list_style_profiles


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

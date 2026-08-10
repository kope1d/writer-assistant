"""诊断包：内容、脱敏与路径语义。"""

import json
import zipfile
from pathlib import Path

from tools.diagnostic_bundle import (
    _collect_logs,
    _redact,
    build_diagnostic_bundle,
)
from tools.init_project import init_project
from tools.version import __version__


def _project_with_logs(tmp_path: Path) -> tuple[Path, str]:
    init_project(tmp_path, "demo", "诊断包测试")
    log_file = tmp_path / ".openwrite" / "logs" / "events.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(
        '{"ts": "2026-08-10T00:00:00+00:00", "level": "INFO", "logger": "tools.demo", "message": "ok"}\n'
        '{"ts": "2026-08-10T00:00:01+00:00", "level": "ERROR", "logger": "tools.demo", "message": "boom"}\n',
        encoding="utf-8",
    )
    return tmp_path, "demo"


def _read_zip_member(path: Path, member: str) -> str:
    with zipfile.ZipFile(path) as bundle:
        return bundle.read(member).decode("utf-8")


def test_bundle_contains_manifest_logs_and_diagnose(tmp_path: Path):
    root, novel_id = _project_with_logs(tmp_path)
    bundle = build_diagnostic_bundle(root, novel_id)
    assert bundle.is_file()
    assert bundle.name.startswith(f"writer-diagnostic-{novel_id}-")

    manifest = json.loads(_read_zip_member(bundle, "manifest.json"))
    assert manifest["version"] == __version__
    assert manifest["novel_id"] == novel_id

    logs = _read_zip_member(bundle, "logs/events.jsonl")
    assert '"boom"' in logs and '"ok"' in logs

    diagnose = json.loads(_read_zip_member(bundle, "diagnose.json"))
    assert isinstance(diagnose, dict)


def test_bundle_redacts_api_keys_in_config_and_environment(tmp_path: Path, monkeypatch):
    root, novel_id = _project_with_logs(tmp_path)
    config_path = root / "novel_config.yaml"
    config_path.write_text(
        "novel_id: demo\nmodel:\n  api_key: sk-test-123456\n  base_url: https://example.com/v1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_API_KEY", "sk-env-789")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")

    bundle = build_diagnostic_bundle(root, novel_id)

    config = json.loads(_read_zip_member(bundle, "config.json"))
    assert config["novel_config"]["model"]["api_key"] == "***"
    assert config["novel_config"]["model"]["base_url"] == "https://example.com/v1"
    environment = json.loads(_read_zip_member(bundle, "environment.json"))
    assert environment["LLM_API_KEY"] == "***"
    assert environment["LLM_MODEL"] == "gpt-4o-mini"
    # 明文 key 不得出现在包内任何文件
    for member in ["config.json", "environment.json", "logs/events.jsonl"]:
        assert "sk-test-123456" not in _read_zip_member(bundle, member)
        assert "sk-env-789" not in _read_zip_member(bundle, member)


def test_redact_recurses_nested_structures():
    payload = {
        "profile": {"name": "main", "api_key": "abc", "embedding_api_key": "def"},
        "list": [{"token": "ghi", "model": "x"}],
        "safe": "kept",
        "empty_key": {"api_key": ""},
    }
    redacted = _redact(payload)
    assert redacted["profile"]["api_key"] == "***"
    assert redacted["profile"]["embedding_api_key"] == "***"
    assert redacted["profile"]["name"] == "main"
    assert redacted["list"][0]["token"] == "***"
    assert redacted["list"][0]["model"] == "x"
    assert redacted["safe"] == "kept"
    assert redacted["empty_key"]["api_key"] == ""


def test_bundle_respects_out_path(tmp_path: Path):
    root, novel_id = _project_with_logs(tmp_path)
    target = tmp_path / "custom" / "bundle.zip"
    bundle = build_diagnostic_bundle(root, novel_id, out_path=target)
    assert bundle == target.resolve()
    assert bundle.is_file()


def test_bundle_without_logs_still_builds(tmp_path: Path):
    init_project(tmp_path, "demo", "无日志项目")
    bundle = build_diagnostic_bundle(tmp_path, "demo")
    assert _read_zip_member(bundle, "logs/events.jsonl") == ""


def test_collect_logs_takes_tail_across_rotated_files(tmp_path: Path):
    log_dir = tmp_path / ".openwrite" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "events.jsonl.1").write_text("old\n", encoding="utf-8")
    (log_dir / "events.jsonl").write_text("new\n", encoding="utf-8")

    logs = _collect_logs(tmp_path)
    assert logs.index("old") < logs.index("new")

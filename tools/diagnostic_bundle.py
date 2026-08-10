"""诊断包：一键导出日志 + 脱敏配置 + 环境信息，提 issue 拖包即诊。

CLI（``writer diagnose --export``）与 Studio（``GET /api/diagnostics``）
共用 ``build_diagnostic_bundle``。所有配置/环境字段经 ``_redact`` 递归
掩码后入包，绝不携带明文凭据。
"""

from __future__ import annotations

import json
import os
import platform
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.version import __version__

_SENSITIVE_KEY = re.compile(r"(api[_-]?key|token|secret|password|credential)", re.IGNORECASE)
_REDACTED = "***"
_MAX_LOG_LINES = 5000


def _redact(value: Any, key: str = "") -> Any:
    """递归掩码敏感字段：key 命中敏感词且值是标量时整体掩码。"""
    if isinstance(value, dict):
        return {k: _redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item, key) for item in value]
    if _SENSITIVE_KEY.search(key) and value not in ("", None):
        return _REDACTED
    return value


def collect_environment() -> dict[str, str]:
    """收集与写作链相关的环境变量（模型/检索/研究配置），已脱敏。"""
    picked = {
        k: v
        for k, v in os.environ.items()
        if k.startswith(("LLM_", "OPENWRITE_", "LIGHTRAG_"))
    }
    return _redact(picked)  # type: ignore[return-value]


def collect_project_config(project_root: Path) -> dict[str, Any]:
    """项目 novel_config.yaml + 模型档案（用户级），已脱敏。"""
    payload: dict[str, Any] = {"novel_config": {}}
    config_path = Path(project_root) / "novel_config.yaml"
    if config_path.is_file():
        try:
            import yaml

            with config_path.open(encoding="utf-8") as handle:
                payload["novel_config"] = yaml.safe_load(handle) or {}
        except Exception as exc:
            payload["novel_config_error"] = str(exc)
    try:
        from tools.model_profiles import ModelProfileStore

        payload["model_profiles"] = ModelProfileStore().load()
    except Exception as exc:
        payload["model_profiles_error"] = str(exc)
    return _redact(payload)  # type: ignore[return-value]


def _collect_logs(project_root: Path) -> str:
    """合并滚动日志（最旧 → 最新）取最后 ``_MAX_LOG_LINES`` 行。"""
    log_dir = Path(project_root) / ".openwrite" / "logs"
    if not log_dir.is_dir():
        return ""
    # RotatingFileHandler：events.jsonl 最新，.1/.2/.3 依次更旧
    files = sorted(
        (path for path in log_dir.glob("events.jsonl*") if path.is_file()),
        key=lambda path: (path.name != "events.jsonl", path.name),
        reverse=True,
    )
    lines: list[str] = []
    for path in files:
        try:
            lines.extend(path.read_text(encoding="utf-8").splitlines())
        except OSError:
            continue
        if len(lines) >= _MAX_LOG_LINES:
            lines = lines[-_MAX_LOG_LINES:]
            break
    return "\n".join(lines[-_MAX_LOG_LINES:]) + ("\n" if lines else "")


def _collect_diagnose(project_root: Path, novel_id: str) -> dict[str, Any]:
    """复用运行时诊断报告；诊断失败不阻塞打包。"""
    try:
        from tools.runtime_diagnostics import RuntimeDiagnosticsService

        report = RuntimeDiagnosticsService(Path(project_root), novel_id).run()
        return report.model_dump(mode="json")
    except Exception as exc:
        return {"error": str(exc)}


def build_diagnostic_bundle(
    project_root: Path,
    novel_id: str,
    *,
    out_path: Path | None = None,
) -> Path:
    """构建诊断包 zip，返回包路径。"""
    root = Path(project_root).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = (out_path or root / f"writer-diagnostic-{novel_id}-{stamp}.zip").resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "format": "writer-diagnostic-bundle",
        "version": __version__,
        "novel_id": novel_id,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
    }
    entries = {
        "manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2),
        "logs/events.jsonl": _collect_logs(root),
        "config.json": json.dumps(collect_project_config(root), ensure_ascii=False, indent=2),
        "environment.json": json.dumps(collect_environment(), ensure_ascii=False, indent=2),
        "diagnose.json": json.dumps(_collect_diagnose(root, novel_id), ensure_ascii=False, indent=2),
    }
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, content in entries.items():
            bundle.writestr(name, content)
    return target

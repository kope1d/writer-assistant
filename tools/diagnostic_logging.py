"""统一 JSONL 日志：所有入口通道落同一份结构化日志文件。

CLI 与 Studio（含桌面端）共用 ``setup_logging``；日志落在项目根的
``.openwrite/logs/events.jsonl``，滚动保留最近 4 份。诊断包直接从这份
文件取末 N 行，提 issue 时拖包即诊。

原则：日志通道是配角——写失败必须静默降级为控制台输出，绝不让日志
本身打断写作链。
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_NAME = "events.jsonl"
_MAX_BYTES = 1024 * 1024
_BACKUP_COUNT = 3

# log_dir -> handler：同目录幂等，不同项目目录可并存（CLI → Studio 同进程）
_installed: dict[Path, RotatingFileHandler] = {}


class JsonlFormatter(logging.Formatter):
    """把 LogRecord 序列化为单行 JSON。序列化失败时回退字符串，绝不抛。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        try:
            return json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError):
            payload["message"] = str(payload["message"])
            return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(project_root: Path | None = None) -> Path | None:
    """幂等挂载 JSONL 文件日志到 root logger。

    返回日志文件路径；``project_root`` 缺失或目录不可写时返回 None，
    日志通道降级为控制台（不中断调用方）。
    """
    if project_root is None:
        return None
    log_dir = Path(project_root).resolve() / ".openwrite" / "logs"
    existing = _installed.get(log_dir)
    if existing is not None:
        return Path(existing.baseFilename)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / _LOG_NAME,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        return None
    handler.setFormatter(JsonlFormatter())
    handler.setLevel(logging.INFO)
    root = logging.getLogger()
    # 诊断通道需要 INFO 级事件；root 默认 WARNING 或调用方调低过都必须提到 INFO
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    _installed[log_dir] = handler
    return Path(handler.baseFilename)

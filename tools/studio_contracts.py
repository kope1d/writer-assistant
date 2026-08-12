"""Shared HTTP and error contracts for Writer Assistant Studio."""

from __future__ import annotations

import logging
import os
import secrets
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

STATIC_ROOT = Path(__file__).parent / "studio_assets"
REQUIRED_STATIC_ASSETS = (
    "index.html",
    "styles.css",
    "app.js",
    "js/application.js",
    "js/core.js",
    "js/markdown-editor.js",
)
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_ASSET_PACKAGE_REQUEST_BYTES = 35 * 1024 * 1024
MAX_TASK_REQUEST_BYTES = 64 * 1024 * 1024
WRITE_HEADER = "X-OpenWrite-Studio"
WRITE_TOKEN_HEADER = "X-OpenWrite-Token"
_WRITE_TOKEN_CACHE: str | None = None


def write_token() -> str:
    """写操作随机凭证（会话级稳定）。

    优先读环境变量 OPENWRITE_STUDIO_TOKEN（Electron 壳启动 backend 时注入，
    每次启动重新生成）；未设置时生成会话级随机值——此时前端无法通过写校验，
    仅适用于带 token 的脚本/CLI 场景。
    """
    global _WRITE_TOKEN_CACHE
    if _WRITE_TOKEN_CACHE is None:
        token = os.environ.get("OPENWRITE_STUDIO_TOKEN", "").strip()
        if not token:
            token = secrets.token_hex(32)
            _log.warning(
                "OPENWRITE_STUDIO_TOKEN 未设置：已生成会话级写凭证，"
                "前端写操作将无法通过校验（桌面端会自动注入，可忽略）"
            )
        _WRITE_TOKEN_CACHE = token
    return _WRITE_TOKEN_CACHE


def missing_required_static_assets(root: Path = STATIC_ROOT) -> list[str]:
    """Return shell assets whose absence prevents Studio from reporting errors."""
    return [relative for relative in REQUIRED_STATIC_ASSETS if not (root / relative).is_file()]


class StudioError(Exception):
    """Expected Studio failure with a stable machine-readable contract."""

    def __init__(
        self,
        message: str,
        status: int = HTTPStatus.BAD_REQUEST,
        *,
        code: str = "STUDIO_ERROR",
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.recoverable = recoverable
        self.details = details or {}


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


def studio_success_payload(data: Any, request_id: str) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "error": None,
        "request_id": request_id,
    }


def studio_error_payload(error: StudioError, request_id: str) -> dict[str, Any]:
    """Preserve the legacy error string while exposing the new error contract."""
    return {
        "error": str(error),
        "code": error.code,
        "recoverable": error.recoverable,
        "details": error.details,
        "request_id": request_id,
    }


def internal_error_payload(
    request_id: str,
    *,
    exception: Exception | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if exception is not None:
        from tools.llm.response import redact_sensitive_text

        details["exception"] = exception.__class__.__name__
        details["message"] = redact_sensitive_text(str(exception) or "")[:300]
    return {
        "error": "Studio 内部错误",
        "code": "INTERNAL_ERROR",
        "recoverable": False,
        "details": details,
        "request_id": request_id,
    }

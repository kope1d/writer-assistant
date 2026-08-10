"""统一 JSONL 日志：格式、幂等与降级。"""

import json
import logging
from pathlib import Path

from tools.diagnostic_logging import JsonlFormatter, _installed, setup_logging


def _cleanup(log_dir: Path) -> None:
    handler = _installed.pop(Path(log_dir).resolve(), None)
    if handler is not None:
        logging.getLogger().removeHandler(handler)
        handler.close()


def test_setup_logging_writes_jsonl_lines(tmp_path: Path):
    log_file = setup_logging(tmp_path)
    assert log_file is not None and log_file.is_file()

    logging.getLogger("tools.demo").info("hello world")
    logging.getLogger("tools.demo").warning("warning msg")

    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["level"] == "INFO"
    assert first["logger"] == "tools.demo"
    assert first["message"] == "hello world"
    assert "ts" in first
    _cleanup(tmp_path)


def test_setup_logging_is_idempotent_per_directory(tmp_path: Path):
    first = setup_logging(tmp_path)
    again = setup_logging(tmp_path)
    assert first == again

    logging.getLogger("tools.demo").info("once")
    assert len(first.read_text(encoding="utf-8").splitlines()) == 1
    _cleanup(tmp_path)


def test_setup_logging_without_project_root_returns_none():
    assert setup_logging(None) is None


def test_setup_logging_records_exc_info(tmp_path: Path):
    log_file = setup_logging(tmp_path)

    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("tools.demo").exception("failed")

    line = json.loads(log_file.read_text(encoding="utf-8").splitlines()[0])
    assert "ValueError" in line["exc"]
    assert "boom" in line["exc"]
    _cleanup(tmp_path)


def test_setup_logging_unwritable_dir_degrades_silently(tmp_path: Path, monkeypatch):
    import os

    # pathlib.mkdir(parents=True) 在 3.11 逐级调用 os.mkdir
    monkeypatch.setattr(
        os, "mkdir", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("denied"))
    )
    assert setup_logging(tmp_path) is None


def test_jsonl_formatter_falls_back_for_non_serializable_message():
    record = logging.LogRecord(
        name="tools.demo",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg={"bad": object()},  # dict 内嵌不可序列化值，json.dumps 必失败
        args=(),
        exc_info=None,
    )
    line = JsonlFormatter().format(record)
    assert isinstance(json.loads(line)["message"], str)

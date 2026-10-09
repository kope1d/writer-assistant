"""Studio 进程关停留痕。

打包版曾两次在没有任何错误日志的情况下以 exit code 0 退出（用户日志里只留下
一条 `backend_exited`），排查时无从下手：`serve_forever()` 只有两种返回方式
——被其它线程 `shutdown()`，或主线程收到 `KeyboardInterrupt`。这里盯住
`run_studio` 是否把原因、pid、存活时长写进日志。
"""

import logging
from pathlib import Path

from tools import studio_application as sa


class _FakeApp:
    debug_enabled = False
    debug_log_path = None


def _fake_server(behaviour):
    class _Server:
        server_port = 4599
        app = _FakeApp()
        closed = False

        def serve_forever(self):
            behaviour()

        def server_close(self):
            type(self).closed = True

    return _Server()


def _install(monkeypatch, server):
    monkeypatch.setattr(sa, "create_server", lambda *a, **k: server)
    monkeypatch.setattr(sa, "ProjectRegistry", lambda *a, **k: None)


def _shutdown_records(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if "Studio 退出" in record.getMessage()
    ]


def test_run_studio_logs_keyboard_interrupt(monkeypatch, caplog, tmp_path: Path):
    def behaviour():
        raise KeyboardInterrupt

    _install(monkeypatch, _fake_server(behaviour))

    with caplog.at_level(logging.WARNING, logger="tools.studio"):
        rc = sa.run_studio(tmp_path, open_browser=False)

    assert rc == 0
    records = _shutdown_records(caplog)
    assert len(records) == 1
    assert "reason=keyboard_interrupt" in records[0]
    assert "port=4599" in records[0]


def test_run_studio_logs_unexpected_normal_return(monkeypatch, caplog, tmp_path: Path):
    """serve_forever() 正常返回 = 有别的线程调了 shutdown()，同样要留痕。"""

    _install(monkeypatch, _fake_server(lambda: None))

    with caplog.at_level(logging.WARNING, logger="tools.studio"):
        rc = sa.run_studio(tmp_path, open_browser=False)

    assert rc == 0
    records = _shutdown_records(caplog)
    assert len(records) == 1
    assert "reason=serve_forever_returned" in records[0]

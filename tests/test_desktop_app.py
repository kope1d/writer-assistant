from __future__ import annotations

import builtins
import sys
from pathlib import Path

from tools import desktop_app


class _FakeServer:
    def __init__(self) -> None:
        self.server_port = 4567
        self.started = False
        self.shutdown_called = False
        self.close_called = False

    def serve_forever(self) -> None:
        self.started = True

    def shutdown(self) -> None:
        self.shutdown_called = True

    def server_close(self) -> None:
        self.close_called = True


class _FakeWebView:
    def __init__(self) -> None:
        self.windows: list[dict] = []
        self.started = False

    def create_window(self, title: str, url: str, **kwargs) -> object:
        self.windows.append({"title": title, "url": url, **kwargs})
        return object()

    def start(self) -> None:
        self.started = True


def test_run_desktop_opens_native_window_and_shuts_down_server(monkeypatch):
    server = _FakeServer()
    webview = _FakeWebView()
    monkeypatch.setattr(desktop_app, "create_server", lambda root, **kw: server)
    monkeypatch.setitem(sys.modules, "webview", webview)
    monkeypatch.setattr(desktop_app.webbrowser, "open", lambda url: None)

    rc = desktop_app.run_desktop(Path("."), port=0)

    assert rc == 0
    assert webview.started is True
    assert len(webview.windows) == 1
    window = webview.windows[0]
    assert window["title"] == "Writer Assistant"
    assert window["url"] == "http://127.0.0.1:4567/"
    assert window["min_size"] == (1024, 700)
    assert server.started is True
    assert server.shutdown_called is True
    assert server.close_called is True


def test_run_desktop_falls_back_to_browser_without_webview(monkeypatch):
    server = _FakeServer()
    opened: list[str] = []
    monkeypatch.setattr(desktop_app, "create_server", lambda root, **kw: server)
    monkeypatch.setattr(desktop_app.webbrowser, "open", opened.append)

    real_import = builtins.__import__

    def raise_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "webview":
            raise ImportError("no webview")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", raise_import)

    rc = desktop_app.run_desktop(Path("."), port=0)

    assert rc == 0
    assert opened == ["http://127.0.0.1:4567/"]
    assert server.started is True

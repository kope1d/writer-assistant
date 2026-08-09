"""Standalone desktop window for Writer Assistant Studio.

Uses the OS-native WebView (WebView2 on Windows, WebKit on macOS) to render
the local Studio UI in a dedicated application window instead of a browser tab.
"""

from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from tools.project_registry import ProjectRegistry
from tools.studio import StudioError, create_server

WINDOW_TITLE = "Writer Assistant"
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900
MIN_WIDTH = 1024
MIN_HEIGHT = 700


def run_desktop(
    project_root: Path,
    *,
    port: int = 4567,
    debug: bool = False,
) -> int:
    """Start the local Studio and show it in a native desktop window."""
    server = create_server(
        Path(project_root),
        port=port,
        debug=debug,
        project_registry=ProjectRegistry(),
    )
    url = f"http://127.0.0.1:{server.server_port}/"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Writer Assistant Desktop: {url}")
    try:
        import webview
    except Exception as exc:
        print(f"桌面窗口组件不可用（{exc}），改用浏览器打开。")
        webbrowser.open(url)
        try:
            thread.join()
        except KeyboardInterrupt:
            pass
        return 0

    webview.create_window(
        WINDOW_TITLE,
        url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(MIN_WIDTH, MIN_HEIGHT),
    )
    try:
        webview.start()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return 0


__all__ = [
    "MIN_HEIGHT",
    "MIN_WIDTH",
    "WINDOW_HEIGHT",
    "WINDOW_TITLE",
    "WINDOW_WIDTH",
    "run_desktop",
]

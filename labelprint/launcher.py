#!/usr/bin/env python3
"""Launch the label printer web UI in a pywebview window."""

from __future__ import annotations

import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_PORT = 8765
WINDOW_TITLE = "Label Printer BP730"


class DesktopApi:
    """Bridge for native save dialog (pywebview js_api)."""

    def download_preview(self, token: str) -> dict:
        import webview

        from labelprint.web.app import get_preview_asset

        asset = get_preview_asset(token)
        if asset is None:
            return {
                "ok": False,
                "error": "Preview not available. Update the preview first.",
            }

        window = webview.active_window()
        if window is None:
            return {"ok": False, "error": "Window not available."}

        save_path = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=asset.filename,
        )
        if not save_path:
            return {"ok": False, "cancelled": True}

        dest = Path(save_path[0] if isinstance(save_path, (tuple, list)) else save_path)
        shutil.copy2(asset.path, dest)
        return {"ok": True, "path": str(dest)}


def _find_free_port(start: int = DEFAULT_PORT) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found on 127.0.0.1")


def _wait_for_server(url: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.1)
    raise RuntimeError(f"Server did not start within {timeout}s")


def _run_flask(app, port: int) -> None:
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def main() -> int:
    from labelprint.web.app import create_app

    try:
        import webview
    except ImportError:
        print("pywebview is required. Run: uv sync", file=sys.stderr)
        return 1

    port = _find_free_port()
    url = f"http://127.0.0.1:{port}/"
    app = create_app()

    thread = threading.Thread(target=_run_flask, args=(app, port), daemon=True)
    thread.start()

    try:
        _wait_for_server(url)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    webview.create_window(
        WINDOW_TITLE,
        url,
        width=1280,
        height=900,
        min_size=(1000, 700),
        js_api=DesktopApi(),
    )
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Check GitHub main for a newer pyproject.toml version and apply updates."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
from pathlib import Path

from labelprint.paths import is_installed, repo_root


def _macos_install():
    root = repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import macos_install

    return macos_install


def local_version() -> str:
    return _macos_install().local_version()


def check_update() -> dict:
    mi = _macos_install()
    current = mi.local_version()
    try:
        latest = mi.fetch_remote_version()
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not reach GitHub. Check the network and try again.") from exc
    except (ValueError, KeyError, OSError) as exc:
        raise RuntimeError(str(exc)) from exc
    return {
        "current": current,
        "latest": latest,
        "update_available": mi.version_tuple(latest) > mi.version_tuple(current),
        "installed": is_installed(),
    }


def apply_update() -> dict:
    if not is_installed():
        raise RuntimeError(
            "Automatic updates only work in the installed app. "
            "Run Install Label Printer Software.command first."
        )

    mi = _macos_install()
    dest = Path(tempfile.mkdtemp(prefix="labelprint-update-", dir="/tmp"))
    try:
        source = mi.download_main_zip(dest)
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not download the update from GitHub.") from exc
    setup = source / "office_setup.py"
    if not setup.is_file():
        raise RuntimeError("Downloaded update is missing office_setup.py.")
    python3 = shutil.which("python3") or "/usr/bin/python3"
    log_path = dest / "update.log"
    log_file = log_path.open("w", encoding="utf-8")
    subprocess.Popen(
        [
            python3,
            str(setup),
            "--source",
            str(source),
            "--wait-pid",
            str(os.getpid()),
            "--relaunch",
            "--no-dialog",
        ],
        cwd=str(source),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    log_file.close()
    request_app_quit()
    return {"ok": True, "restarting": True}


def request_app_quit() -> None:
    def _quit() -> None:
        time.sleep(1.0)
        try:
            import webview

            for window in list(webview.windows):
                window.destroy()
        except Exception:
            pass
        os._exit(0)

    threading.Thread(target=_quit, daemon=True).start()

"""Resolve app vs user-data directories.

When launched from the installed .app, LABELPRINT_DATA_DIR points at
Application Support user data (designs and output). Without that env var
(dev / Start Labels.command) paths stay next to the repo.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_APP_DIR = "LABELPRINT_APP_DIR"
ENV_DATA_DIR = "LABELPRINT_DATA_DIR"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def is_installed() -> bool:
    return bool(os.environ.get(ENV_DATA_DIR, "").strip())


def app_dir() -> Path:
    raw = os.environ.get(ENV_APP_DIR, "").strip()
    if raw:
        return Path(raw)
    return repo_root()


def data_dir() -> Path:
    raw = os.environ.get(ENV_DATA_DIR, "").strip()
    if raw:
        return Path(raw)
    return repo_root()


def designs_dir() -> Path:
    if is_installed():
        return data_dir() / "designs"
    return repo_root() / "designs"


def output_dir() -> Path:
    if is_installed():
        return data_dir() / "output"
    return repo_root() / "output"

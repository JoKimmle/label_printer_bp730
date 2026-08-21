#!/usr/bin/env python3
"""Install Label Printer BP730 into Applications (office Macs).

Run from Terminal (works even if .command files have broken line endings):

    python3 office_setup.py

Or double-click "Install Label Printer Software.command".
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from macos_install import main as install_main  # noqa: E402


def main() -> int:
    argv = list(sys.argv[1:])
    if "--source" not in argv:
        argv = ["--source", str(ROOT), *argv]
    return install_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

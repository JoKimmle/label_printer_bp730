#!/usr/bin/env python3
"""One-time setup after copying this folder to a new Mac.

Run from Terminal (works even if .command files have broken line endings):

    python3 office_setup.py

Or double-click "Setup Office.command" after fixing it once with the command above.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def fix_crlf(path: Path) -> bool:
    data = path.read_bytes()
    if b"\r" not in data:
        return False
    path.write_bytes(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    return True


def main() -> int:
    print("Label Printer BP730 — office setup\n")

    fixed: list[str] = []
    for pattern in ("*.command", "*.sh"):
        for path in ROOT.glob(pattern):
            if fix_crlf(path):
                fixed.append(path.name)
            path.chmod(path.stat().st_mode | 0o111)

    if fixed:
        print("Fixed Windows line endings in:", ", ".join(fixed))
    else:
        print("Line endings OK on launcher scripts.")

    uv = shutil.which("uv")
    if uv is None:
        for candidate in (
            Path.home() / ".local/bin/uv",
            Path("/opt/homebrew/bin/uv"),
            Path("/usr/local/bin/uv"),
        ):
            if candidate.is_file():
                uv = str(candidate)
                break

    if uv is None:
        print(
            "\nERROR: 'uv' not found.\n"
            "Install it first: https://docs.astral.sh/uv/\n"
            "  curl -LsSf https://astral.sh/uv/install.sh | sh\n"
            "Then run this script again.",
            file=sys.stderr,
        )
        return 1

    print(f"Using uv: {uv}")
    print("Installing dependencies (uv sync)…")
    result = subprocess.run([uv, "sync"], cwd=ROOT)
    if result.returncode != 0:
        print("uv sync failed.", file=sys.stderr)
        return result.returncode

    print("\nSetup complete.")
    print("You can now double-click: Start Labels.command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

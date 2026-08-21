#!/usr/bin/env python3
"""Install or update Label Printer BP730 on macOS. Stdlib only (no Pillow)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

APP_NAME = "Label Printer BP730"
BUNDLE_ID = "de.chargeiq.labelprinter"
GITHUB_REPO = "JoKimmle/label_printer_bp730"
GITHUB_BRANCH = "main"
USER_AGENT = "LabelPrinterBP730"
UV_INSTALL_SH = "https://astral.sh/uv/install.sh"

ICON_PNG_NAME = "label-printer-app-icon.png"
COPY_SKIP_NAMES = {
    ".venv",
    "output",
    ".git",
    "__pycache__",
    "data",
    ".DS_Store",
}

ICON_SIZES = (
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
)


def support_root() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


def installed_app_dir() -> Path:
    return support_root() / "app"


def installed_data_dir() -> Path:
    return support_root() / "data"


def _extend_path() -> None:
    extras = [
        Path.home() / ".local" / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ]
    parts = os.environ.get("PATH", "").split(":")
    for extra in extras:
        value = str(extra)
        if extra.is_dir() and value not in parts:
            parts.insert(0, value)
    os.environ["PATH"] = ":".join(parts)


def find_uv() -> str | None:
    _extend_path()
    found = shutil.which("uv")
    if found:
        return found
    for candidate in (
        Path.home() / ".local" / "bin" / "uv",
        Path("/opt/homebrew/bin/uv"),
        Path("/usr/local/bin/uv"),
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def ensure_uv() -> str:
    uv = find_uv()
    if uv:
        return uv
    print("Installing uv…")
    result = subprocess.run(
        ["sh", "-c", f"curl -LsSf {UV_INSTALL_SH} | sh"],
    )
    if result.returncode != 0:
        raise RuntimeError("Failed to install uv.")
    uv = find_uv()
    if uv is None:
        raise RuntimeError("uv installed but not found on PATH.")
    return uv


def read_version_from_text(text: str) -> str:
    data = tomllib.loads(text)
    version = data.get("project", {}).get("version")
    if not version:
        raise ValueError("No project.version in pyproject.toml")
    return str(version)


def read_version(pyproject: Path) -> str:
    return read_version_from_text(pyproject.read_text(encoding="utf-8"))


def version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in version.strip().split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts) if parts else (0,)


def local_pyproject_path() -> Path:
    env_app = os.environ.get("LABELPRINT_APP_DIR", "").strip()
    if env_app:
        return Path(env_app) / "pyproject.toml"
    return Path(__file__).resolve().parent / "pyproject.toml"


def local_version() -> str:
    return read_version(local_pyproject_path())


def _http_get(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def remote_pyproject_url() -> str:
    return (
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/"
        f"{GITHUB_BRANCH}/pyproject.toml?t={int(time.time())}"
    )


def remote_zip_url() -> str:
    return f"https://github.com/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"


def fetch_remote_version() -> str:
    text = _http_get(remote_pyproject_url()).decode("utf-8")
    return read_version_from_text(text)


def project_root_from(source: Path) -> Path:
    if (source / "office_setup.py").is_file() and (source / "pyproject.toml").is_file():
        return source
    for child in sorted(source.iterdir()):
        if (
            child.is_dir()
            and (child / "office_setup.py").is_file()
            and (child / "pyproject.toml").is_file()
        ):
            return child
    raise RuntimeError(f"Could not find project files in {source}")


def download_main_zip(dest_parent: Path) -> Path:
    dest_parent.mkdir(parents=True, exist_ok=True)
    archive = dest_parent / "main.zip"
    archive.write_bytes(_http_get(remote_zip_url(), timeout=120))
    extract_dir = dest_parent / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(str(archive), str(extract_dir))
    return project_root_from(extract_dir)


def fix_crlf(path: Path) -> bool:
    data = path.read_bytes()
    if b"\r" not in data:
        return False
    path.write_bytes(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    return True


def fix_scripts(root: Path) -> list[str]:
    fixed: list[str] = []
    for pattern in ("*.command", "*.sh"):
        for path in root.glob(pattern):
            if fix_crlf(path):
                fixed.append(path.name)
            path.chmod(path.stat().st_mode | 0o111)
    return fixed


def _copy_ignore(_directory: str, contents: list[str]) -> list[str]:
    skipped: list[str] = []
    for name in contents:
        if name in COPY_SKIP_NAMES or name.endswith(".pyc"):
            skipped.append(name)
    return skipped


def replace_app_files(source: Path, app_dir: Path) -> None:
    app_dir.mkdir(parents=True, exist_ok=True)
    for child in list(app_dir.iterdir()):
        if child.name == ".venv":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in source.iterdir():
        if child.name in COPY_SKIP_NAMES:
            continue
        dest = app_dir / child.name
        if child.is_dir():
            shutil.copytree(child, dest, ignore=_copy_ignore)
        else:
            shutil.copy2(child, dest)


def seed_designs(source: Path, data_dir: Path) -> int:
    src = source / "designs"
    dest = data_dir / "designs"
    dest.mkdir(parents=True, exist_ok=True)
    (data_dir / "output").mkdir(parents=True, exist_ok=True)
    if not src.is_dir():
        return 0
    added = 0
    for path in src.glob("*.json"):
        target = dest / path.name
        if not target.exists():
            shutil.copy2(path, target)
            added += 1
    return added


def wait_for_pid(pid: int, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.25)
    raise RuntimeError(f"Process {pid} did not exit in time.")


def quit_running_app() -> None:
    subprocess.run(
        ["osascript", "-e", f'tell application "{APP_NAME}" to quit'],
        capture_output=True,
        check=False,
    )
    time.sleep(0.8)


def _applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def show_dialog(title: str, message: str) -> None:
    script = (
        f"display dialog {_applescript_string(message)} with title "
        f"{_applescript_string(title)} buttons {{\"OK\"}} default button \"OK\""
    )
    subprocess.run(["osascript", "-e", script], check=False)


def applications_app_path() -> Path:
    system = Path("/Applications") / f"{APP_NAME}.app"
    home = Path.home() / "Applications" / f"{APP_NAME}.app"
    if home.exists() and not system.exists():
        return home
    return system


def _write_info_plist(path: Path, version: str) -> None:
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>{APP_NAME}</string>
  <key>CFBundleExecutable</key>
  <string>launcher</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>{BUNDLE_ID}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>{APP_NAME}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>{version}</string>
  <key>CFBundleVersion</key>
  <string>{version}</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
""",
        encoding="utf-8",
    )


def _write_launcher_script(path: Path) -> None:
    support = support_root()
    path.write_text(
        f"""#!/bin/bash
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
APP_SUPPORT="{support}"
export LABELPRINT_APP_DIR="$APP_SUPPORT/app"
export LABELPRINT_DATA_DIR="$APP_SUPPORT/data"
cd "$LABELPRINT_APP_DIR" || {{
  osascript -e 'display dialog "Label Printer is not installed. Double-click Install Label Printer Software.command in the project folder." buttons {{"OK"}} default button "OK" with icon caution with title "{APP_NAME}"'
  exit 1
}}
if [[ ! -x "$LABELPRINT_APP_DIR/.venv/bin/python" ]]; then
  osascript -e 'display dialog "Dependencies are missing. Double-click Install Label Printer Software.command in the project folder." buttons {{"OK"}} default button "OK" with icon caution with title "{APP_NAME}"'
  exit 1
fi
exec "$LABELPRINT_APP_DIR/.venv/bin/python" -m labelprint.launcher
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | 0o111)


def build_icns(png: Path, dest_icns: Path) -> None:
    if not png.is_file():
        raise FileNotFoundError(f"App icon PNG not found: {png}")
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "AppIcon.iconset"
        iconset.mkdir()
        for size, name in ICON_SIZES:
            out = iconset / name
            result = subprocess.run(
                [
                    "sips",
                    "-s",
                    "format",
                    "png",
                    "-z",
                    str(size),
                    str(size),
                    str(png),
                    "--out",
                    str(out),
                ],
                capture_output=True,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode() or "sips failed")
        dest_icns.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(dest_icns)],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode() or "iconutil failed")


def write_app_bundle(app_dir: Path, bundle: Path) -> None:
    version = read_version(app_dir / "pyproject.toml")
    macos = bundle / "Contents" / "MacOS"
    resources = bundle / "Contents" / "Resources"
    macos.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)
    _write_info_plist(bundle / "Contents" / "Info.plist", version)
    _write_launcher_script(macos / "launcher")
    png = app_dir / "assets" / ICON_PNG_NAME
    try:
        build_icns(png, resources / "AppIcon.icns")
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        print(f"Warning: could not build app icon: {exc}", file=sys.stderr)
    subprocess.run(
        ["xattr", "-d", "com.apple.quarantine", str(bundle)],
        capture_output=True,
        check=False,
    )
    subprocess.run(["touch", str(bundle)], check=False)


def resolve_bundle_path() -> Path:
    preferred = Path("/Applications") / f"{APP_NAME}.app"
    fallback = Path.home() / "Applications" / f"{APP_NAME}.app"
    existing = applications_app_path()
    if existing.exists():
        return existing
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        test = preferred.parent / f".{APP_NAME}.write-test"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        return preferred
    except OSError:
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


def install(
    source: Path,
    *,
    wait_pid: int | None = None,
    relaunch: bool = False,
    dialog: bool = True,
) -> Path:
    source = project_root_from(source)
    if wait_pid:
        wait_for_pid(wait_pid)
    else:
        quit_running_app()

    fixed = fix_scripts(source)
    if fixed:
        print("Fixed Windows line endings in:", ", ".join(fixed))

    uv = ensure_uv()
    app_dir = installed_app_dir()
    data_dir = installed_data_dir()
    was_installed = (app_dir / "pyproject.toml").is_file()

    print(f"Installing app files to {app_dir}")
    replace_app_files(source, app_dir)
    added = seed_designs(source, data_dir)
    if added:
        print(f"Added {added} new design(s) (existing designs were kept).")
    else:
        print("Designs kept (no new stock templates).")

    print(f"Using uv: {uv}")
    print("Installing dependencies (uv sync)…")
    result = subprocess.run([uv, "sync"], cwd=app_dir)
    if result.returncode != 0:
        raise RuntimeError("uv sync failed.")

    bundle = resolve_bundle_path()
    if bundle.exists():
        shutil.rmtree(bundle)
    print(f"Writing {bundle}")
    write_app_bundle(app_dir, bundle)

    version = read_version(app_dir / "pyproject.toml")
    if relaunch:
        subprocess.Popen(["open", str(bundle)], start_new_session=True)

    if dialog:
        action = "Updated" if was_installed else "Installed"
        show_dialog(
            APP_NAME,
            f"{action} to {version}.\n\n"
            "Open it from Applications.\n"
            "Your label designs were kept.",
        )
    print(f"Setup complete ({version}). Open: {bundle}")
    return bundle


def parse_args(argv: list[str] | None = None):
    import argparse

    parser = argparse.ArgumentParser(description=f"Install {APP_NAME} on this Mac")
    parser.add_argument(
        "--source",
        type=Path,
        help="Project folder to install from (default: this file's directory)",
    )
    parser.add_argument(
        "--wait-pid",
        type=int,
        metavar="PID",
        help="Wait for this process to exit before replacing files",
    )
    parser.add_argument(
        "--relaunch",
        action="store_true",
        help="Open the installed .app when finished",
    )
    parser.add_argument(
        "--no-dialog",
        action="store_true",
        help="Skip the success dialog",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source or Path(__file__).resolve().parent
    try:
        install(
            source,
            wait_pid=args.wait_pid,
            relaunch=args.relaunch,
            dialog=not args.no_dialog,
        )
    except (OSError, RuntimeError, ValueError, urllib.error.URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if not args.no_dialog:
            show_dialog(APP_NAME, f"Install failed:\n{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

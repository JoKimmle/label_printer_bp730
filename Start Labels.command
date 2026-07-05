#!/usr/bin/env bash
# Label Printer BP730 — double-click on Mac.
# If this fails with "bad interpreter … ^M", run once in Terminal:
#   cd /path/to/label_printer_bp730 && python3 office_setup.py

set -e
cd "$(dirname "$0")"

export PATH="/opt/homebrew/bin:/usr/local/bin:${HOME}/.local/bin:${PATH}"

if ! command -v uv >/dev/null 2>&1; then
  osascript -e 'display dialog "uv is not installed.\n\nOpen Terminal in this folder and run:\npython3 office_setup.py" buttons {"OK"} default button "OK" with icon caution with title "Label Printer BP730"'
  exit 1
fi

if [[ ! -d .venv ]]; then
  osascript -e 'display dialog "Dependencies not installed yet.\n\nOpen Terminal in this folder and run:\npython3 office_setup.py" buttons {"OK"} default button "OK" with icon caution with title "Label Printer BP730"'
  exit 1
fi

exec uv run python -m labelprint.launcher

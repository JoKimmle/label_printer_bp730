# Label Printing with Godex BP730 made simple

**Ditch the driver and printer tool drama for printing with Godex BP730.** Print JSON label designs directly to your Godex BP730; zero fuss required.

*Full disclosure: Built with vibe-coding-tools.*

## Why this exists

Godex BP730 labels are usually designed in **GoLabel** — Windows-only, proprietary `.ezpx` files, no variables. Batch printing means open label, change text, print, repeat.

On Mac there is no sane end-to-end workflow (design → variables → preview → print). Godex offers a **CUPS driver** (`rastertoezpl` `.pkg`): right-click Open on the pkg, Gatekeeper prompts, manual `.ppd` selection from `/usr/local/share/ppd/godex`, sometimes **GoTools** + `^XSET,USBSPEED,0` for USB. Result: a CUPS queue and the system print dialog (raster → EZPL filter). No designer, no variables. GoLabel stays Windows-only.

This repo skips drivers and CUPS — render label to bitmap, wrap in EZPL, send raw over USB:

- **JSON templates** in `designs/` with named variables
- **Web UI + designer** — template, fields, live preview, print
- **Direct USB** via pyusb (no `.pkg`, no PPD)
- **CLI** for scripting

Preview and print share the same raster path.

## Setup

```bash
uv sync
```

## Office app (recommended) - tested on mac only

Double-click **Start Labels.command** on the Mac (or run `uv run python -m labelprint.launcher`).

A window opens with:

1. Pick a **design** from the dropdown
2. Fill in the **variables** on the right (depends on the design)
3. Preview updates automatically while typing
4. Click **Print label** when ready

Connect the BP730 via USB before printing. If the label prints upside down, open **Advanced options** and set rotation to 180°.

### First-time setup

Copy the whole folder to the Mac, then **run setup once in Terminal**:

```bash
cd /path/to/label_printer_bp730
python3 office_setup.py
```

This fixes Windows line endings (the `bad interpreter: /bin/bash^M` error), installs dependencies, and prepares the launchers.

Then double-click **Start Labels.command**.

If **Start Labels.command** still fails immediately after copying (before setup), the copy method may have broken line endings — always run `python3 office_setup.py` first. Do not copy only the `.command` file to the Desktop; keep the whole project folder together.

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+ on the office Mac:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Label designer

Open **Label designer** from the app (or go to `/designer`) to create and edit label layouts.

Designs are saved as JSON files in `designs/` and appear in the print dropdown automatically.

Supported elements:

- **Static text** — fixed copy on the label
- **Dynamic text** — bound to a design variable
- **QR code** — bound to a design variable
- **Image** — upload a logo or icon
- **Box** — outline or filled rectangle

Use the **Variables** panel (left sidebar) to create and manage fields: name, label, default sample value, and optional computed formula (e.g. `{base_url}/{id}`). Dynamic text and QR elements pick from these variables. **Preview values** (right sidebar) set sample data for the live preview.

## CLI - general use

```bash
# List available designs
uv run python label.py --list

# Preview only
uv run python label.py \
  --template my_label \
  --evse-id "ABC-123" \
  --preview --open

# Print via USB
uv run python label.py \
  --template my_label \
  --evse-id "ABC-123" \
  --print
```

Design names are the `.json` filename without extension. Output goes to `output/<design>_<id>.png` and `.ezpl`.

## Architecture

| Path | Role |
|------|------|
| `Start Labels.command` | Double-click launcher for office users |
| `labelprint/launcher.py` | pywebview window + Flask server |
| `labelprint/web/` | Flask + HTMX UI |
| `label.py` | CLI entry point |
| `labelprint/core.py` | Shared label job logic |
| `designs/` | JSON label designs |
| `label_design.py` | JSON design format and renderer |
| `label_setup.py` | Label dimensions and mm/dot helpers |
| `raster_ezpl.py` | Wrap PNG in EZPL for printing |

## Printing notes

- Use direct USB (the app and `--print` flag). Do not install the Godex CUPS driver for this workflow — it is not needed, and sending raw EZPL through CUPS garbles output on this model.
- Preview PNG matches what the printer receives (same raster → EZPL path).

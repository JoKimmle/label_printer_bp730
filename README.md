# Label printer BP730

This Mac app is used to operate the Labelident BP730 thermo direct label printer. It includes a reverse-engineered print pipeline, print menu, and label template designer.

## Why this exists - the problem

Officially the BP730 is run with GoLabel. It is Windows-only. The template designer is clumsy. Labels are proprietary `.ezpx` files with no variables. There is no batch printing. No macOS or Linux app.

## What this is - the solution

A Mac tool that skips that stack.

- Fast, because it never talks to GoLabel or a vendor driver
- No Godex driver, no CUPS, no leftover 3rd-party USB stack from a CD
- A simple label designer in the app
- One JSON template with named variables. Fill values, print, change values, print again. That is the batch workflow GoLabel does not have.

Two ways in: a UI (template designer + print menu) and a CLI for scripted runs. Same printer path.

## How it prints

We reverse-engineered enough of the BP730 print path to throw the official stack away. The label is rendered to a 1-bit bitmap, wrapped as Godex BMP inside EZPL, and sent raw over USB.

Preview PNG and print share that raster, so the PNG-preview is what the printer gets.

## Install

Download the projects zip of `main` [Label printer BP730](https://github.com/JoKimmle/label_printer_bp730/archive/refs/heads/main.zip), unpack it, and double-click `Install Label Printer Software.command` inside that folder.

The installer:

- copies the app into `~/Library/Application Support/Label Printer BP730/app/`
- seeds stock designs into `…/data/designs/` without overwriting labels you already saved
- runs `uv sync`
- puts **Label Printer BP730** in Applications

Open it from Applications, Spotlight, or the Dock. Plug in the BP730 over USB before you print.

Needs Python 3.11+. The installer fetches [uv](https://docs.astral.sh/uv/) if it is missing.

### Updates

The header shows the version from `pyproject.toml`. **Check for updates** compares that to GitHub `main`. If `main` is newer, the button becomes **Update to X.Y.Z**, downloads the zip, installs it, and restarts.


## Print

Pick a design, fill in the variables on the right, watch the preview catch up as you type, hit **Print label**. Portrait designs rotate to landscape so they fit one physical label. The preview matches that orientation.

## Design

Open **Label designer** from the app. Designs save as JSON and show up in the print dropdown. Installed app stores them under Application Support.

Elements you can drop on a label:

- Static text, fixed copy
- Dynamic text, bound to a variable
- QR code, bound to a variable
- Image, a logo or icon you upload
- Box, outline or filled rectangle

The **Variables** panel (left sidebar) is where fields live: name, label, default sample value, optional formula such as `{base_url}/{id}`. Dynamic text and QR elements pick from that list. **Preview values** (right sidebar) is sample data for the live preview, not what gets printed unless you type the same thing on the print screen.

## CLI

Same printer path as the UI. Script it when clicking Print forty times would be the joke.

```bash
uv run python label.py --list

uv run python label.py \
  --template my_label \
  --evse-id "ABC-123" \
  --preview --open

uv run python label.py \
  --template my_label \
  --evse-id "ABC-123" \
  --print
```

Design names are the `.json` filename without the extension. Output lands in `output/<design>_<id>.png` and `.ezpl`.

## Develop from this folder

```bash
uv sync
uv run python -m labelprint.launcher
```

Or double-click `Start Labels.command`. Designs and output stay here (`designs/`, `output/`).

## Troubleshooting

If `Install Label Printer Software.command` dies with `bad interpreter: /bin/bash^M`, the copy turned Unix line endings into Windows ones. Run `python3 office_setup.py` once from Terminal. Keep the whole project folder together. Do not copy only the `.command` file.

## Where things live

| Path | What it is |
|------|------------|
| `Install Label Printer Software.command` / `office_setup.py` | Install into Application Support + Applications |
| `macos_install.py` | Copy app files, seed designs, `uv sync`, write the `.app` |
| `assets/label-printer-app-icon.png` | macOS app icon source |
| `Start Labels.command` | Double-click launcher for development in this folder |
| `labelprint/launcher.py` | pywebview window + Flask server |
| `labelprint/web/` | Flask + HTMX UI |
| `labelprint/paths.py` | App vs user-data directories |
| `label.py` | CLI entry point |
| `labelprint/core.py` | Shared label job logic |
| `designs/` | Stock JSON designs (seeded on install) |
| `label_design.py` | JSON design format and renderer |
| `label_setup.py` | Label dimensions and mm/dot helpers |
| `raster_ezpl.py` | Wrap PNG in EZPL for printing |

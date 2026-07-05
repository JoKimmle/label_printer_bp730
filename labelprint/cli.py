#!/usr/bin/env python3
"""CLI for chargeIQ label printing."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from labelprint.core import (
    DEFAULT_DESIGNS_DIR,
    LabelJob,
    list_designs,
    resolve_design,
    run_job,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="label",
        description="Print chargeIQ QR labels: pick a design, set EVSE-ID, preview and/or print.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list
  %(prog)s --template GLS_QR_new --evse-id "DE*CIQ*ABC*1" --preview
  %(prog)s --template GLS_QR_new --evse-id "DE*CIQ*ABC*1" --preview --print
  %(prog)s --template chargeIQ_QR --evse-id "DE*CIQ*ABC*1" --print --rotate 180
        """.strip(),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available designs in designs/",
    )
    parser.add_argument(
        "-t",
        "--template",
        metavar="NAME",
        help="Design name (e.g. GLS_QR_new) or path to .json file",
    )
    parser.add_argument(
        "-e",
        "--evse-id",
        help="EVSE identifier (used for QR URL and EVSE-ID text on label)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Save PNG preview to output/ (default when neither --preview nor --print is given)",
    )
    parser.add_argument(
        "--print",
        dest="do_print",
        action="store_true",
        help="Send label to BP730 via direct USB",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open preview PNG after rendering (macOS)",
    )
    parser.add_argument(
        "--rotate",
        type=int,
        choices=(0, 90, 180, 270),
        default=0,
        help="Rotate label if print orientation is wrong",
    )
    parser.add_argument(
        "--designs-dir",
        type=Path,
        default=DEFAULT_DESIGNS_DIR,
        help=f"Directory containing JSON designs (default: {DEFAULT_DESIGNS_DIR})",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated PNG and EZPL files",
    )
    return parser


def _print_design_list(designs_dir: Path) -> None:
    designs = list_designs(designs_dir)
    if not designs:
        print(f"No designs found in {designs_dir}")
        return
    print("Designs:\n")
    for item in designs:
        print(f"  {item.name}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list:
        _print_design_list(args.designs_dir)
        return 0

    if not args.template or not args.evse_id:
        parser.error("--template and --evse-id are required (or use --list)")

    preview = args.preview or not args.do_print

    try:
        design_path = resolve_design(args.template, args.designs_dir)
        result = run_job(
            LabelJob(
                template=design_path,
                evse_id=args.evse_id,
                rotate=args.rotate,
            ),
            preview=preview,
            print_usb=args.do_print,
            output_dir=args.output_dir,
        )
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Design:   {result.template.name}")
    print(f"EVSE-ID:  {result.evse_id}")
    print(f"QR URL:   {result.qr_url}")
    print(f"EZPL:     {result.ezpl_path} ({result.ezpl_path.stat().st_size} bytes)")
    if result.preview_path:
        print(f"Preview:  {result.preview_path}")
    if result.printed:
        print("Sent to printer via direct USB")

    if args.open and result.preview_path:
        subprocess.run(["open", str(result.preview_path)], check=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

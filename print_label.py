#!/usr/bin/env python3
"""Send EZPL to a Godex BP730 label printer.

Prefer direct USB for EZPL — the Godex CUPS driver expects raster and will garble raw EZPL.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
from pathlib import Path

# Godex BP730 USB identifiers (from ioreg)
GODEX_VID = 0x195F
GODEX_BP730_PID = 0x0001
DEFAULT_SERIAL = "1648001A"


def send_network(host: str, port: int, data: bytes) -> None:
    with socket.create_connection((host, port), timeout=10) as sock:
        sock.sendall(data)
    print(f"Sent {len(data)} bytes to {host}:{port}")


def send_usb_direct(
    data: bytes,
    *,
    serial: str | None = DEFAULT_SERIAL,
    vendor_id: int = GODEX_VID,
    product_id: int = GODEX_BP730_PID,
) -> None:
    """Send raw EZPL straight to the printer over USB (bypasses CUPS)."""
    try:
        import usb.core
        import usb.util
    except ImportError as exc:
        raise RuntimeError(
            "Direct USB requires pyusb. Run: uv sync"
        ) from exc

    # Use bundled libusb on macOS/Windows when brew libusb is not installed.
    try:
        import libusb_package

        backend = libusb_package.get_libusb1_backend()
    except ImportError:
        backend = None

    dev = usb.core.find(idVendor=vendor_id, idProduct=product_id, backend=backend)
    if dev is None:
        raise RuntimeError(
            "BP730 not found on USB. Connect the printer and ensure it is powered on."
        )

    if serial and getattr(dev, "serial_number", None) not in (None, serial):
        dev = usb.core.find(
            idVendor=vendor_id,
            idProduct=product_id,
            serial_number=serial,
            backend=backend,
        )
        if dev is None:
            raise RuntimeError(f"BP730 with serial {serial!r} not found on USB.")

    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except (usb.core.USBError, NotImplementedError):
        pass

    dev.set_configuration()
    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    ep_out = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
        == usb.util.ENDPOINT_OUT,
    )
    if ep_out is None:
        raise RuntimeError("No USB OUT endpoint on BP730.")

    offset = 0
    while offset < len(data):
        written = ep_out.write(data[offset : offset + 4096], timeout=30_000)
        if written <= 0:
            raise RuntimeError("USB write to printer failed.")
        offset += written

    print(f"Sent {len(data)} bytes to BP730 via direct USB")


def send_usb_cups(queue: str, data: bytes) -> None:
    """Send via CUPS — NOT recommended for EZPL with the Godex raster driver."""
    print(
        "Warning: CUPS Godex driver expects raster, not raw EZPL. "
        "Use --direct instead.",
        file=sys.stderr,
    )
    proc = subprocess.run(
        ["lp", "-d", queue, "-o", "document-format=application/octet-stream", "-"],
        input=data,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode() or "lp failed")
    print(f"Queued {len(data)} bytes on CUPS queue '{queue}'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Print EZPL to Godex BP730")
    parser.add_argument("ezpl_file", type=Path, help="Path to .ezpl file")
    parser.add_argument(
        "--host",
        default="192.168.1.100",
        help="Printer IP (network mode, port 9100)",
    )
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Send raw EZPL over USB directly (recommended on macOS)",
    )
    parser.add_argument(
        "--serial",
        default=DEFAULT_SERIAL,
        help=f"BP730 USB serial number (default: {DEFAULT_SERIAL})",
    )
    parser.add_argument(
        "--cups",
        metavar="QUEUE",
        help="Send via CUPS queue (not recommended for EZPL)",
    )
    args = parser.parse_args()

    data = args.ezpl_file.read_bytes()
    if args.cups:
        send_usb_cups(args.cups, data)
    elif args.direct:
        send_usb_direct(data, serial=args.serial)
    else:
        send_network(args.host, args.port, data)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

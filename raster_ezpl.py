"""Generate minimal EZPL that prints a full-label bitmap (WYSIWYG with visualizer)."""

from __future__ import annotations

import struct

from PIL import Image


def pil_to_godex_bmp(img: Image.Image) -> bytes:
    """Convert a 1-bit PIL image to Godex ~Eb BMP format."""
    if img.mode != "1":
        img = img.convert("L").point(lambda p: 0 if p < 128 else 255, mode="1")

    width, height = img.size
    row_bytes = (width + 31) // 32 * 4
    pixel_data = bytearray()
    for row in range(height - 1, -1, -1):
        row_bits = bytearray(row_bytes)
        for col in range(width):
            if img.getpixel((col, row)) == 0:
                row_bits[col // 8] |= 0x80 >> (col % 8)
        pixel_data.extend(row_bits)

    pixel_data = bytearray(b ^ 0xFF for b in pixel_data)

    file_header_size = 14
    info_header_size = 40
    offset = file_header_size + info_header_size
    file_size = offset + len(pixel_data)

    header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, offset)
    info = struct.pack(
        "<IiiHHIIiiII",
        info_header_size,
        width,
        height,
        1,
        1,
        0,
        len(pixel_data),
        0,
        0,
        0,
        0,
    )
    return header + info + bytes(pixel_data)


def wrap_bitmap_in_ezpl(
    bitmap: Image.Image,
    setup,
    *,
    image_name: str = "LABEL",
    rotate: int = 0,
) -> bytes:
    """Wrap a 1-bit label bitmap in EZPL using printer setup from a design."""
    bmp_bytes = pil_to_godex_bmp(bitmap)

    length_mm = setup.label_length_mm
    width_mm = setup.label_width_mm
    if rotate in (90, 270):
        length_mm, width_mm = width_mm, length_mm

    parts: list[bytes] = []

    def add_text(line: str) -> None:
        parts.append((line + "\r\n").encode("utf-8"))

    add_text(f"^Q{length_mm:g},{setup.gap_mm:g}")
    add_text(f"^W{width_mm:g}")
    add_text(f"^H{setup.darkness}")
    add_text(f"^S{setup.speed}")
    add_text("^AD")
    add_text("^O0")
    add_text("^R0")
    add_text("~Q0")
    add_text(f"^C{setup.copies}")
    add_text(f"~MDELG,{image_name}")
    add_text(f"~Eb,{image_name},{len(bmp_bytes)}")
    parts.append(bmp_bytes)
    parts.append(b"\r\n")
    add_text("^L")
    add_text(f"Y0,0,{image_name}")
    add_text("E")

    return b"".join(parts)

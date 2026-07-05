"""Printer label dimensions and dot/mm helpers shared by design rendering and EZPL output."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LabelSetup:
    label_length_mm: float
    label_width_mm: float
    gap_mm: float
    darkness: int
    speed: int
    copies: int
    dpi: int
    page_direction: str
    left_margin_mm: float = 0.0
    top_margin_mm: float = 0.0


def _dots_per_mm(dpi: int) -> int:
    if dpi == 300:
        return 12
    if dpi == 203:
        return 8
    return max(1, round(dpi / 25.4))


def _mm_to_dots(mm: float, dpi: int) -> int:
    return round(mm * _dots_per_mm(dpi))

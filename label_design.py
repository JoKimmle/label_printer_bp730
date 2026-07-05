"""JSON label design format — load, save, and render to PIL images."""

from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import qrcode
from PIL import Image, ImageDraw, ImageFont

from label_setup import LabelSetup, _dots_per_mm, _mm_to_dots

ANCHORS = (
    "top-left",
    "top-center",
    "top-right",
    "center-left",
    "center",
    "center-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
)

ELEMENT_TYPES = ("text", "dynamic_text", "qr", "image", "box")

TYPE_LABELS = {
    "text": "Static text",
    "dynamic_text": "Dynamic text",
    "qr": "QR code",
    "image": "Image",
    "box": "Box",
}


@dataclass
class DesignVariable:
    name: str
    label: str = ""
    default: str = ""
    computed: str = ""


@dataclass
class DesignElement:
    id: str
    type: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    anchor: str = "top-left"
    content: str = ""
    variable: str = ""
    font_size_pt: float = 10.0
    line_spacing_mm: float = 0.0
    alignment: str = "left"
    bold: bool = False
    border_width: float = 1.0
    fill: bool = False
    image_data: str = ""


@dataclass
class LabelDesign:
    name: str
    setup: LabelSetup
    variables: list[DesignVariable] = field(default_factory=list)
    elements: list[DesignElement] = field(default_factory=list)
    version: int = 1

    @property
    def width_mm(self) -> float:
        return self.setup.label_width_mm

    @property
    def height_mm(self) -> float:
        return self.setup.label_length_mm


def default_design(name: str = "Untitled") -> LabelDesign:
    return LabelDesign(
        name=name,
        setup=LabelSetup(
            label_length_mm=50.0,
            label_width_mm=75.0,
            gap_mm=2.0,
            darkness=8,
            speed=4,
            copies=1,
            dpi=203,
            page_direction="Portrait",
        ),
        variables=[
            DesignVariable(
                name="evse_id",
                label="EVSE-ID",
                default="DE*CIQ*ABC*1",
            ),
            DesignVariable(
                name="qr_base_url",
                label="QR base URL",
                default="https://qr.chargeIQ.de/",
            ),
            DesignVariable(
                name="qr_url",
                label="QR URL",
                computed="{qr_base_url}/{evse_id}",
            ),
        ],
        elements=[
            DesignElement(
                id="text_evse_label",
                type="text",
                x_mm=3.0,
                y_mm=3.0,
                width_mm=40.0,
                height_mm=5.0,
                anchor="top-left",
                content="EVSE-ID:",
                font_size_pt=9.0,
                alignment="left",
            ),
            DesignElement(
                id="text_evse_value",
                type="dynamic_text",
                x_mm=3.0,
                y_mm=9.0,
                width_mm=40.0,
                height_mm=6.0,
                anchor="top-left",
                variable="evse_id",
                font_size_pt=10.0,
                alignment="left",
                bold=True,
            ),
            DesignElement(
                id="qr_main",
                type="qr",
                x_mm=55.0,
                y_mm=10.0,
                width_mm=18.0,
                height_mm=18.0,
                anchor="top-left",
                variable="qr_url",
            ),
        ],
    )


def _anchor_offset(anchor: str, width: int, height: int) -> tuple[float, float]:
    anchors: dict[str, tuple[float, float]] = {
        "top-left": (0.0, 0.0),
        "top-center": (-width / 2, 0.0),
        "top-right": (-width, 0.0),
        "center-left": (0.0, -height / 2),
        "center": (-width / 2, -height / 2),
        "center-right": (-width, -height / 2),
        "bottom-left": (0.0, -height),
        "bottom-center": (-width / 2, -height),
        "bottom-right": (-width, -height),
    }
    return anchors.get(anchor, (0.0, 0.0))


def resolve_bbox(element: DesignElement, dpi: int) -> tuple[int, int, int, int]:
    """Return top-left x, y, width, height in dots for an element."""
    width = max(1, _mm_to_dots(element.width_mm, dpi))
    height = max(1, _mm_to_dots(element.height_mm, dpi))
    anchor_x = _mm_to_dots(element.x_mm, dpi)
    anchor_y = _mm_to_dots(element.y_mm, dpi)
    ox, oy = _anchor_offset(element.anchor, width, height)
    return int(anchor_x + ox), int(anchor_y + oy), width, height


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _substitute(text: str, variables: dict[str, str]) -> str:
    content = text
    for _ in range(5):
        updated = content
        for key, value in variables.items():
            updated = updated.replace(f"{{{key}}}", value)
        if updated == content:
            break
        content = updated
    return content


def resolve_design_variables(
    design: LabelDesign,
    values: dict[str, str] | None = None,
) -> dict[str, str]:
    """Merge defaults, user values, and computed variables."""
    resolved: dict[str, str] = {}
    for var in design.variables:
        if var.default:
            resolved[var.name] = var.default
    if values:
        for key, value in values.items():
            if value is not None:
                resolved[key] = value

    if "qr_base_url" in resolved:
        resolved["qr_base_url"] = resolved["qr_base_url"].rstrip("/")

    for var in design.variables:
        if not var.computed:
            continue
        resolved[var.name] = _substitute(var.computed, resolved)

    return resolved


def resolve_element_text(element: DesignElement, variables: dict[str, str]) -> str:
    if element.type == "dynamic_text":
        if not element.variable:
            return ""
        return variables.get(element.variable, "")
    return element.content or ""


def resolve_element_qr(element: DesignElement, variables: dict[str, str]) -> str:
    if element.variable:
        return variables.get(element.variable, element.variable)
    if element.content:
        return _substitute(element.content, variables)
    return variables.get("qr_url", "")


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split()
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if font.getlength(trial) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _text_line_spacing_dots(element: DesignElement, dpi: int, font_size: int) -> int:
    """Return line advance in dots. 0 line_spacing_mm means auto (~120% of font size)."""
    if element.line_spacing_mm > 0:
        return max(1, _mm_to_dots(element.line_spacing_mm, dpi))
    return max(8, round(font_size * 1.2))


def _draw_text_element(
    draw: ImageDraw.ImageDraw,
    element: DesignElement,
    content: str,
    dpi: int,
) -> None:
    x, y, width, height = resolve_bbox(element, dpi)
    font_size = max(8, round(element.font_size_pt * dpi / 72))
    font = _load_font(font_size, bold=element.bold)
    max_width = max(8, width - 4)
    lines = _wrap_text(content, font, max_width)
    line_h = _text_line_spacing_dots(element, dpi, font_size)
    cursor_y = y
    for line in lines:
        if not line:
            cursor_y += line_h
            continue
        line_w = font.getlength(line)
        cursor_x = x + 2
        align = element.alignment.lower()
        if align in ("center", "centre") and line_w < max_width:
            cursor_x = x + (max_width - line_w) / 2
        elif align == "right" and line_w < max_width:
            cursor_x = x + max_width - line_w
        draw.text((cursor_x, cursor_y), line, fill="black", font=font)
        cursor_y += line_h


def _draw_qr_element(img: Image.Image, element: DesignElement, data: str, dpi: int) -> None:
    x, y, width, height = resolve_bbox(element, dpi)
    factory = qrcode.QRCode(border=0, box_size=1)
    factory.add_data(data)
    factory.make(fit=True)
    qr_img = factory.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((width, height), Image.Resampling.NEAREST)
    img.paste(qr_img, (x, y))


def _decode_image_data(image_data: str) -> bytes | None:
    if not image_data:
        return None
    data = image_data.strip()
    match = re.match(r"^data:image/[^;]+;base64,(.+)$", data, re.DOTALL)
    if match:
        data = match.group(1)
    try:
        return base64.b64decode(data)
    except (ValueError, TypeError):
        return None


def _draw_image_element(img: Image.Image, element: DesignElement, dpi: int) -> None:
    raw = _decode_image_data(element.image_data)
    if not raw:
        return
    x, y, width, height = resolve_bbox(element, dpi)
    logo = Image.open(io.BytesIO(raw)).convert("RGB")
    logo = logo.resize((width, height), Image.Resampling.LANCZOS)
    img.paste(logo, (x, y))


def _draw_box_element(draw: ImageDraw.ImageDraw, element: DesignElement, dpi: int) -> None:
    x, y, width, height = resolve_bbox(element, dpi)
    border = max(1, _mm_to_dots(element.border_width, dpi))
    if element.fill:
        draw.rectangle((x, y, x + width, y + height), fill="black", outline="black", width=border)
    else:
        draw.rectangle((x, y, x + width, y + height), outline="black", width=border)


def canvas_size(design: LabelDesign) -> tuple[int, int]:
    dpi = design.setup.dpi
    dpm = _dots_per_mm(dpi)
    return round(design.setup.label_width_mm * dpm), round(design.setup.label_length_mm * dpm)


def render_design(
    design: LabelDesign,
    *,
    variables: dict[str, str] | None = None,
    mode: str = "RGB",
    rotate: int = 0,
) -> Image.Image:
    """Render a JSON label design to a PIL image."""
    resolved = resolve_design_variables(design, variables)
    dpi = design.setup.dpi
    width, height = canvas_size(design)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    for element in design.elements:
        if element.type == "image":
            _draw_image_element(img, element, dpi)
        elif element.type == "box":
            _draw_box_element(draw, element, dpi)
        elif element.type == "qr":
            data = resolve_element_qr(element, resolved)
            if data:
                _draw_qr_element(img, element, data, dpi)
        elif element.type in ("text", "dynamic_text"):
            content = resolve_element_text(element, resolved)
            if content:
                _draw_text_element(draw, element, content, dpi)

    if rotate:
        img = img.rotate(rotate, expand=True)

    if mode == "1":
        return img.convert("L").point(lambda p: 0 if p < 128 else 255, mode="1")
    return img


def _normalize_element_type(data: dict[str, Any]) -> str:
    """Map legacy/mixed text elements to static or dynamic types."""
    el_type = str(data.get("type") or "text")
    if el_type in ("text-dynamic", "text_dynamic"):
        return "dynamic_text"
    if el_type in ("qr", "image", "box"):
        return el_type

    variable = str(data.get("variable") or "").strip()
    content = str(data.get("content") or "")

    if el_type == "text" and (variable or (content.startswith("{") and content.endswith("}") and len(content) > 2)):
        return "dynamic_text"
    if el_type == "dynamic_text":
        return "dynamic_text"
    return "text"


def _element_from_dict(data: dict[str, Any]) -> DesignElement:
    el_type = _normalize_element_type(data)
    variable = str(data.get("variable") or "").strip()
    content = str(data.get("content") or "")

    if el_type == "dynamic_text" and not variable and content.startswith("{") and content.endswith("}"):
        variable = content[1:-1].strip()
        content = ""

    if el_type == "text":
        variable = ""
    elif el_type == "dynamic_text":
        content = ""

    return DesignElement(
        id=str(data.get("id") or ""),
        type=el_type,
        x_mm=float(data.get("x_mm", 0)),
        y_mm=float(data.get("y_mm", 0)),
        width_mm=float(data.get("width_mm", 10)),
        height_mm=float(data.get("height_mm", 5)),
        anchor=str(data.get("anchor") or "top-left"),
        content=content,
        variable=variable,
        font_size_pt=float(data.get("font_size_pt", 10)),
        line_spacing_mm=float(data.get("line_spacing_mm") or 0),
        alignment=str(data.get("alignment") or "left"),
        bold=bool(data.get("bold", False)),
        border_width=float(data.get("border_width", 1)),
        fill=bool(data.get("fill", False)),
        image_data=str(data.get("image_data") or ""),
    )


def _element_to_dict(element: DesignElement) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": element.id,
        "type": element.type,
        "x_mm": element.x_mm,
        "y_mm": element.y_mm,
        "width_mm": element.width_mm,
        "height_mm": element.height_mm,
        "anchor": element.anchor,
    }
    if element.type == "text":
        data.update(
            {
                "content": element.content,
                "font_size_pt": element.font_size_pt,
                "line_spacing_mm": element.line_spacing_mm,
                "alignment": element.alignment,
                "bold": element.bold,
            }
        )
    elif element.type == "dynamic_text":
        data.update(
            {
                "variable": element.variable,
                "font_size_pt": element.font_size_pt,
                "line_spacing_mm": element.line_spacing_mm,
                "alignment": element.alignment,
                "bold": element.bold,
            }
        )
    elif element.type == "qr":
        data.update({"variable": element.variable, "content": element.content})
    elif element.type == "image":
        data["image_data"] = element.image_data
    elif element.type == "box":
        data.update(
            {
                "border_width": element.border_width,
                "fill": element.fill,
            }
        )
    return data


def load_design(path: Path | str) -> LabelDesign:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return design_from_dict(raw, fallback_name=path.stem)


def save_design(design: LabelDesign, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(design_to_dict(design), indent=2), encoding="utf-8")


def design_from_dict(data: dict[str, Any], *, fallback_name: str = "Untitled") -> LabelDesign:
    setup_raw = data.get("setup") or {}
    setup = LabelSetup(
        label_length_mm=float(setup_raw.get("label_length_mm", 50)),
        label_width_mm=float(setup_raw.get("label_width_mm", 75)),
        gap_mm=float(setup_raw.get("gap_mm", 2)),
        darkness=int(setup_raw.get("darkness", 8)),
        speed=int(setup_raw.get("speed", 4)),
        copies=int(setup_raw.get("copies", 1)),
        dpi=int(setup_raw.get("dpi", 203)),
        page_direction=str(setup_raw.get("page_direction") or "Portrait"),
    )
    variables = [
        DesignVariable(
            name=str(item.get("name") or ""),
            label=str(item.get("label") or ""),
            default=str(item.get("default") or ""),
            computed=str(item.get("computed") or ""),
        )
        for item in data.get("variables") or []
        if item.get("name")
    ]
    elements = [_element_from_dict(item) for item in data.get("elements") or []]
    return LabelDesign(
        name=str(data.get("name") or fallback_name),
        version=int(data.get("version") or 1),
        setup=setup,
        variables=variables,
        elements=elements,
    )


def design_to_dict(design: LabelDesign) -> dict[str, Any]:
    return {
        "name": design.name,
        "version": design.version,
        "setup": {
            "label_length_mm": design.setup.label_length_mm,
            "label_width_mm": design.setup.label_width_mm,
            "gap_mm": design.setup.gap_mm,
            "darkness": design.setup.darkness,
            "speed": design.setup.speed,
            "copies": design.setup.copies,
            "dpi": design.setup.dpi,
            "page_direction": design.setup.page_direction,
        },
        "variables": [
            {
                "name": var.name,
                "label": var.label,
                "default": var.default,
                "computed": var.computed,
            }
            for var in design.variables
        ],
        "elements": [_element_to_dict(element) for element in design.elements],
    }

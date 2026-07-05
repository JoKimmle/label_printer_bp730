"""Core label job logic (shared by CLI and GUI)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from label_design import DesignVariable, default_design, load_design, render_design, resolve_design_variables
from raster_ezpl import wrap_bitmap_in_ezpl

DEFAULT_DESIGNS_DIR = Path(__file__).resolve().parent.parent / "designs"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
DEFAULT_QR_BASE_URL = "https://qr.chargeIQ.de/"


@dataclass(frozen=True)
class TemplateInfo:
    name: str
    path: Path


@dataclass
class LabelJob:
    template: Path
    evse_id: str
    qr_base_url: str = DEFAULT_QR_BASE_URL
    rotate: int = 0
    variable_values: dict[str, str] | None = None


@dataclass
class LabelResult:
    template: Path
    evse_id: str
    qr_url: str
    ezpl_path: Path
    preview_path: Path | None = None
    printed: bool = False


def list_designs(designs_dir: Path | None = None) -> list[TemplateInfo]:
    root = designs_dir or DEFAULT_DESIGNS_DIR
    if not root.is_dir():
        return []
    return [
        TemplateInfo(name=path.stem, path=path)
        for path in sorted(root.glob("*.json"))
    ]


def resolve_design(name_or_path: str | Path, designs_dir: Path | None = None) -> Path:
    """Resolve a JSON design by filename, stem, or path."""
    raw = Path(name_or_path)
    if raw.suffix == ".json" and raw.exists():
        return raw.resolve()

    stem = raw.stem if raw.suffix == ".json" else str(name_or_path)
    candidates = [
        DEFAULT_DESIGNS_DIR / f"{stem}.json",
        Path.cwd() / f"{stem}.json",
        Path.cwd() / "designs" / f"{stem}.json",
    ]
    if designs_dir:
        candidates.insert(0, designs_dir / f"{stem}.json")

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    available = ", ".join(t.name for t in list_designs(designs_dir)) or "(none)"
    raise FileNotFoundError(
        f"Design not found: {name_or_path!r}. Available: {available}"
    )


def get_template_variables(name_or_path: str | Path) -> list[DesignVariable]:
    """Return variable definitions for a JSON design."""
    try:
        source_path = resolve_design(name_or_path)
    except FileNotFoundError:
        return list(default_design().variables)

    design = load_design(source_path)
    return list(design.variables)


def get_input_variables(name_or_path: str | Path) -> list[DesignVariable]:
    """Return user-editable (non-computed) variables for a design."""
    return [var for var in get_template_variables(name_or_path) if not var.computed]


def _safe_evse_id(evse_id: str) -> str:
    return evse_id.replace("*", "_").replace("/", "_")


def _build_job_variables(job: LabelJob) -> dict[str, str]:
    design = load_design(job.template)
    values = dict(job.variable_values or {})
    values.setdefault("evse_id", job.evse_id)
    values.setdefault("qr_base_url", job.qr_base_url)
    return resolve_design_variables(design, values)


def run_job(
    job: LabelJob,
    *,
    preview: bool = False,
    print_usb: bool = False,
    output_dir: Path | None = None,
) -> LabelResult:
    """Render and optionally preview/print a label job."""
    if not preview and not print_usb:
        raise ValueError("Enable at least one of preview or print_usb")

    source_path = resolve_design(job.template)
    variables = _build_job_variables(
        LabelJob(
            template=source_path,
            evse_id=job.evse_id,
            qr_base_url=job.qr_base_url,
            rotate=job.rotate,
            variable_values=job.variable_values,
        ),
    )
    qr_url = variables.get("qr_url", "")

    out_dir = output_dir or DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_id = _safe_evse_id(job.evse_id)
    stem = f"{source_path.stem}_{safe_id}"
    ezpl_path = out_dir / f"{stem}.ezpl"

    design = load_design(source_path)
    bitmap = render_design(design, variables=variables, mode="1", rotate=job.rotate)
    ezpl_bytes = wrap_bitmap_in_ezpl(bitmap, design.setup, rotate=job.rotate)
    ezpl_path.write_bytes(ezpl_bytes)

    preview_path: Path | None = None
    if preview:
        preview_path = out_dir / f"{stem}.png"
        img = render_design(design, variables=variables, rotate=job.rotate or 0)
        img.save(preview_path)

    printed = False
    if print_usb:
        from print_label import send_usb_direct

        send_usb_direct(ezpl_bytes)
        printed = True

    return LabelResult(
        template=source_path,
        evse_id=job.evse_id,
        qr_url=qr_url,
        ezpl_path=ezpl_path,
        preview_path=preview_path,
        printed=printed,
    )

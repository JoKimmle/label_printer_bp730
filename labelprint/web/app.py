"""Flask app for the label printer web UI."""

from __future__ import annotations

import io
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

from label_design import (
    default_design,
    design_from_dict,
    design_to_dict,
    load_design,
    render_design,
    resolve_design_variables,
    save_design,
)
from labelprint.core import (
    DEFAULT_DESIGNS_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_QR_BASE_URL,
    LabelJob,
    get_input_variables,
    get_template_variables,
    list_designs,
    resolve_design,
    run_job,
)

# token -> preview PNG metadata (in-memory for current session)
@dataclass
class _PreviewAsset:
    path: Path
    filename: str


_preview_cache: dict[str, _PreviewAsset] = {}


def get_preview_asset(token: str) -> _PreviewAsset | None:
    asset = _preview_cache.get(token)
    if asset is None or not asset.path.is_file():
        return None
    return asset


def _safe_filename(template: str, evse_id: str) -> str:
    safe_id = evse_id.replace("*", "_").replace("/", "_")
    return f"{template}_{safe_id}.png"


def _form_values() -> tuple[str, int, dict[str, str]]:
    template = (request.form.get("template") or "").strip()
    try:
        rotate = int(request.form.get("rotate") or 0)
    except ValueError:
        rotate = 0
    if rotate not in (0, 90, 180, 270):
        rotate = 0

    values: dict[str, str] = {}
    for key, value in request.form.items():
        if key.startswith("var_"):
            values[key[4:]] = (value or "").strip()

    return template, rotate, values


def _missing_input_variable(template: str, values: dict[str, str]):
    for var in get_input_variables(template):
        if not values.get(var.name, "").strip():
            return var
    return None


def _build_job(template: str, values: dict[str, str], rotate: int) -> LabelJob:
    source_path = resolve_design(template)
    evse_id = values.get("evse_id", "")
    qr_base_url = values.get("qr_base_url") or DEFAULT_QR_BASE_URL
    return LabelJob(
        template=source_path,
        evse_id=evse_id,
        qr_base_url=qr_base_url,
        rotate=rotate,
        variable_values=values,
    )


def _design_name_from_request(name: str) -> str:
    cleaned = "".join(ch for ch in name.strip() if ch.isalnum() or ch in ("-", "_"))
    if not cleaned:
        raise ValueError("Design name is required.")
    return cleaned


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    @app.get("/")
    def index():
        templates = list_designs(DEFAULT_DESIGNS_DIR)
        default_template = templates[0].name if templates else ""
        variables = get_template_variables(default_template) if default_template else []
        input_variables = [var for var in variables if not var.computed]
        computed_variables = [var for var in variables if var.computed]
        return render_template(
            "index.html",
            templates=templates,
            default_template=default_template,
            input_variables=input_variables,
            computed_variables=computed_variables,
        )

    @app.get("/partials/variables")
    def template_variables():
        template = (request.args.get("template") or "").strip()
        if not template:
            return render_template(
                "partials/variables.html",
                input_variables=[],
                computed_variables=[],
            )
        variables = get_template_variables(template)
        return render_template(
            "partials/variables.html",
            input_variables=[var for var in variables if not var.computed],
            computed_variables=[var for var in variables if var.computed],
        )

    @app.get("/designer")
    def designer():
        designs = list_designs(DEFAULT_DESIGNS_DIR)
        return render_template(
            "designer.html",
            designs=designs,
        )

    @app.get("/designer/api/designs")
    def designer_list():
        designs = list_designs(DEFAULT_DESIGNS_DIR)
        return jsonify([{"name": item.name, "path": str(item.path)} for item in designs])

    @app.get("/designer/api/designs/<name>")
    def designer_load(name: str):
        try:
            safe_name = _design_name_from_request(name)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        path = DEFAULT_DESIGNS_DIR / f"{safe_name}.json"
        if path.is_file():
            design = load_design(path)
            return jsonify(design_to_dict(design))

        if safe_name == "new":
            return jsonify(design_to_dict(default_design()))

        return jsonify({"error": f"Design not found: {safe_name}"}), 404

    @app.post("/designer/api/designs/<name>")
    def designer_save(name: str):
        try:
            safe_name = _design_name_from_request(name)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Expected JSON body."}), 400

        try:
            design = design_from_dict(payload, fallback_name=safe_name)
            design.name = payload.get("name") or safe_name
            DEFAULT_DESIGNS_DIR.mkdir(parents=True, exist_ok=True)
            save_design(design, DEFAULT_DESIGNS_DIR / f"{safe_name}.json")
        except (TypeError, ValueError, KeyError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify({"ok": True, "name": safe_name})

    @app.post("/designer/api/preview")
    def designer_preview():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Expected JSON body."}), 400

        design_data = payload.get("design")
        if not isinstance(design_data, dict):
            return jsonify({"error": "Missing design object."}), 400

        values = payload.get("variables") or {}
        if not isinstance(values, dict):
            values = {}

        try:
            design = design_from_dict(design_data)
            resolved = resolve_design_variables(design, {str(k): str(v) for k, v in values.items()})
            img = render_design(design, variables=resolved)
        except (TypeError, ValueError, KeyError, OSError) as exc:
            return jsonify({"error": str(exc)}), 400

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")

    @app.post("/preview")
    def preview():
        template, rotate, values = _form_values()
        missing = _missing_input_variable(template, values)
        if not template or missing:
            label = missing.label if missing else "variables"
            return render_template(
                "partials/preview.html",
                placeholder=True,
                message=f"Enter {label} to see a preview.",
            )
        try:
            job = _build_job(template, values, rotate)
            result = run_job(
                job,
                preview=True,
                print_usb=False,
                output_dir=DEFAULT_OUTPUT_DIR,
            )
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
            return render_template(
                "partials/preview.html",
                error=str(exc),
            )

        filename = _safe_filename(template, values.get("evse_id", "label"))
        token = uuid.uuid4().hex
        if result.preview_path:
            _preview_cache[token] = _PreviewAsset(
                path=result.preview_path,
                filename=filename,
            )

        return render_template(
            "partials/preview.html",
            token=token,
            qr_url=result.qr_url,
            download_filename=filename,
        )

    @app.post("/print")
    def print_label():
        template, rotate, values = _form_values()
        missing = _missing_input_variable(template, values)
        if not template or missing:
            label = missing.label if missing else "all variables"
            return render_template(
                "partials/message.html",
                error=f"Select a template and enter {label}.",
            )
        try:
            job = _build_job(template, values, rotate)
            run_job(
                job,
                preview=False,
                print_usb=True,
                output_dir=DEFAULT_OUTPUT_DIR,
            )
        except RuntimeError as exc:
            msg = str(exc)
            if "not found on USB" in msg:
                msg = "Printer not found. Check USB and power."
            return render_template("partials/message.html", error=msg)
        except (FileNotFoundError, OSError, ValueError) as exc:
            return render_template("partials/message.html", error=str(exc))

        evse_id = values.get("evse_id") or template
        return render_template(
            "partials/message.html",
            success=f"Sent label for {evse_id} to printer.",
        )

    @app.get("/preview-image/<token>")
    def preview_image(token: str):
        asset = _preview_cache.get(token)
        if asset is None or not asset.path.is_file():
            abort(404)
        return send_file(asset.path, mimetype="image/png")

    @app.get("/download/<token>")
    def download_preview(token: str):
        asset = get_preview_asset(token)
        if asset is None:
            abort(404)
        return send_file(
            asset.path,
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=asset.filename,
        )

    return app

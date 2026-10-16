"""Aircraft 3D Reconstruction and Lofting API Endpoints."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import cv2
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.ai.gemini_extractor import GeminiBlueprintExtractor
from app.ai.spec import AircraftSemanticSpec
from app.core.config import get_project_root, resolve_blueprint_path
from app.cv.blueprint_processor import BlueprintProcessor
from app.geometry.dynamic_builder import build_aircraft_from_semantic_spec
from app.geometry.mesh_ops import calculate_mesh_metrics, calculate_projected_planform_area

router = APIRouter(prefix="/reconstruction", tags=["reconstruction"])


class GenerateAircraftRequest(BaseModel):
    blueprint_path: str | None = "docs/blueprint.jpg"
    wingspan_m: float | None = None
    length_m: float | None = None
    height_m: float | None = None
    num_fuselage_stations: int = 18
    vertices_per_ring: int = 16
    propeller_blades: int | None = None
    gemini_api_key: str | None = None
    top_view_path: str | None = None
    side_view_path: str | None = None
    front_view_path: str | None = None
    spec: dict | None = None


@router.post("/generate-aircraft")
async def generate_aircraft(req: GenerateAircraftRequest):
    """
    Generate dynamic 3D aircraft model strictly driven by semantic specifications.
    Uses Gemini Vision analysis or client-provided semantic spec without hardcoded templates.
    """
    if req.spec:
        spec = AircraftSemanticSpec.model_validate(req.spec)
    else:
        resolved_bp = resolve_blueprint_path(req.blueprint_path)
        resolved_top = resolve_blueprint_path(req.top_view_path) if req.top_view_path else None
        resolved_side = resolve_blueprint_path(req.side_view_path) if req.side_view_path else None
        resolved_front = resolve_blueprint_path(req.front_view_path) if req.front_view_path else None

        extractor = GeminiBlueprintExtractor(api_key=req.gemini_api_key)
        spec = extractor.analyze_views(
            top_image=resolved_top,
            side_image=resolved_side,
            front_image=resolved_front,
            unified_blueprint=resolved_bp,
            wingspan_hint_m=req.wingspan_m,
            length_hint_m=req.length_m,
            height_hint_m=req.height_m,
        )

    # Apply dimensional overrides if provided
    if req.wingspan_m and req.wingspan_m > 0:
        spec.wingspan_m = req.wingspan_m
    if req.length_m and req.length_m > 0:
        spec.length_m = req.length_m
    if req.height_m and req.height_m > 0:
        spec.height_m = req.height_m

    result = build_aircraft_from_semantic_spec(spec)
    full_srf_str = result["full_aircraft"].to_srf(short_syntax=True)

    return {
        "status": "success",
        "aircraft_name": spec.aircraft_name,
        "metrics": result["metrics"],
        "wing_area_m2": result["wing_area_m2"],
        "scale_pixels_per_meter": 50.0,
        "components": {
            k: {"vertices": len(v.get("vertices", [])), "faces": len(v.get("faces", []))}
            for k, v in result["component_meshes"].items()
        },
        "component_meshes": result["component_meshes"],
        "full_srf": full_srf_str,
        "srf_preview": full_srf_str[:1500] + "\n...",
        "spec": spec.model_dump(),
    }


@router.post("/upload-views")
async def upload_views(
    top_file: UploadFile | None = File(None),
    side_file: UploadFile | None = File(None),
    front_file: UploadFile | None = File(None),
    blueprint_file: UploadFile | None = File(None),
    aircraft_name: str | None = Form(None),
    wingspan_m: float | None = Form(None),
    length_m: float | None = Form(None),
    height_m: float | None = Form(None),
    gemini_api_key: str | None = Form(None),
):
    """
    Upload separate orthographic views (Top, Side, Front) or a unified blueprint sheet.
    Performs multimodal semantic extraction with Gemini Vision, lofts dynamic 3D geometry,
    and returns WebGL meshes + view preview URLs.
    """
    upload_dir = get_project_root() / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)

    top_bytes: bytes | None = None
    side_bytes: bytes | None = None
    front_bytes: bytes | None = None
    bp_bytes: bytes | None = None

    saved_paths: dict[str, str] = {}
    view_urls: dict[str, str] = {}

    if top_file and top_file.filename:
        top_bytes = await top_file.read()
        p = upload_dir / f"view_{ts}_top.png"
        p.write_bytes(top_bytes)
        saved_paths["top"] = str(p)
        view_urls["top"] = f"data:image/png;base64,{base64.b64encode(top_bytes).decode('utf-8')}"

    if side_file and side_file.filename:
        side_bytes = await side_file.read()
        p = upload_dir / f"view_{ts}_side.png"
        p.write_bytes(side_bytes)
        saved_paths["side"] = str(p)
        view_urls["side"] = f"data:image/png;base64,{base64.b64encode(side_bytes).decode('utf-8')}"

    if front_file and front_file.filename:
        front_bytes = await front_file.read()
        p = upload_dir / f"view_{ts}_front.png"
        p.write_bytes(front_bytes)
        saved_paths["front"] = str(p)
        view_urls["front"] = f"data:image/png;base64,{base64.b64encode(front_bytes).decode('utf-8')}"

    if blueprint_file and blueprint_file.filename:
        bp_bytes = await blueprint_file.read()
        p = upload_dir / f"bp_{ts}.jpg"
        p.write_bytes(bp_bytes)
        saved_paths["blueprint"] = str(p)

        # If separate views were not provided, decompose the blueprint sheet
        if not (top_bytes and side_bytes):
            try:
                proc = BlueprintProcessor()
                decomp = proc.decompose_file(p)
                if decomp.top_view and not top_bytes:
                    _, buf = cv2.imencode(".png", decomp.top_view.image)
                    top_bytes = buf.tobytes()
                    view_urls["top"] = f"data:image/png;base64,{base64.b64encode(top_bytes).decode('utf-8')}"
                    top_crop_path = upload_dir / f"crop_{ts}_top.png"
                    top_crop_path.write_bytes(top_bytes)
                    saved_paths["top"] = str(top_crop_path)

                if decomp.side_view and not side_bytes:
                    _, buf = cv2.imencode(".png", decomp.side_view.image)
                    side_bytes = buf.tobytes()
                    view_urls["side"] = f"data:image/png;base64,{base64.b64encode(side_bytes).decode('utf-8')}"
                    side_crop_path = upload_dir / f"crop_{ts}_side.png"
                    side_crop_path.write_bytes(side_bytes)
                    saved_paths["side"] = str(side_crop_path)

                if decomp.front_view and not front_bytes:
                    _, buf = cv2.imencode(".png", decomp.front_view.image)
                    front_bytes = buf.tobytes()
                    view_urls["front"] = f"data:image/png;base64,{base64.b64encode(front_bytes).decode('utf-8')}"
                    front_crop_path = upload_dir / f"crop_{ts}_front.png"
                    front_crop_path.write_bytes(front_bytes)
                    saved_paths["front"] = str(front_crop_path)
            except Exception:
                pass

    if not top_bytes and not side_bytes and not front_bytes and not bp_bytes:
        raise HTTPException(
            status_code=400,
            detail="Envie pelo menos uma das 3 vistas (Top/Side/Front) ou o arquivo completo da blueprint.",
        )

    extractor = GeminiBlueprintExtractor(api_key=gemini_api_key)
    spec = extractor.analyze_views(
        top_image=top_bytes,
        side_image=side_bytes,
        front_image=front_bytes,
        unified_blueprint=bp_bytes,
        wingspan_hint_m=wingspan_m,
        length_hint_m=length_m,
        height_hint_m=height_m,
        aircraft_name_hint=aircraft_name,
    )

    if aircraft_name and aircraft_name.strip():
        spec.aircraft_name = aircraft_name.strip()
    if wingspan_m and wingspan_m > 0:
        spec.wingspan_m = wingspan_m
    if length_m and length_m > 0:
        spec.length_m = length_m
    if height_m and height_m > 0:
        spec.height_m = height_m

    result = build_aircraft_from_semantic_spec(spec)
    full_srf_str = result["full_aircraft"].to_srf(short_syntax=True)

    return {
        "status": "success",
        "aircraft_name": spec.aircraft_name,
        "metrics": result["metrics"],
        "wing_area_m2": result["wing_area_m2"],
        "scale_pixels_per_meter": 50.0,
        "components": {
            k: {"vertices": len(v.get("vertices", [])), "faces": len(v.get("faces", []))}
            for k, v in result["component_meshes"].items()
        },
        "component_meshes": result["component_meshes"],
        "full_srf": full_srf_str,
        "srf_preview": full_srf_str[:1500] + "\n...",
        "spec": spec.model_dump(),
        "view_urls": view_urls,
        "saved_paths": saved_paths,
    }

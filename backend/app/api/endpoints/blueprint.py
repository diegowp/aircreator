"""Blueprint Processing and Calibration API Endpoints."""

import base64
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.config import get_project_root, resolve_blueprint_path
from app.cv import (
    AircraftDimensions,
    AxisDetector,
    BlueprintCalibrator,
    BlueprintProcessor,
)

router = APIRouter(prefix="/blueprint", tags=["blueprint"])


class CalibrationRequest(BaseModel):
    wingspan_px: float
    length_px: float
    wingspan_m: float
    length_m: float
    height_m: float | None = None
    top_centerline_px: float = 0.0
    front_centerline_px: float = 0.0
    side_thrustline_px: float = 0.0


class BBoxResponse(BaseModel):
    x: int
    y: int
    width: int
    height: int


class ViewCropResponse(BaseModel):
    view_type: str
    bbox: BBoxResponse
    image_base64: str | None = None


class DecomposeResponse(BaseModel):
    original_width: int
    original_height: int
    top_view: ViewCropResponse | None = None
    front_view: ViewCropResponse | None = None
    side_view: ViewCropResponse | None = None
    wingspan_px: float
    length_px: float
    height_px: float
    saved_path: str | None = None


@router.post("/decompose", response_model=DecomposeResponse)
async def decompose_blueprint(
    file: UploadFile = File(None),
    image_path: str = Form(None),
    include_images: bool = Form(False),
):
    """
    Decompose a 3-view blueprint into orthographic views (Top, Front, Side),
    extracting bounding boxes, centerlines, and dimensional measurements.
    """
    processor = BlueprintProcessor()
    upload_dir = get_project_root() / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = None

    if file is not None:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        target_path = upload_dir / "active_blueprint.jpg"
        target_path.write_bytes(contents)
        saved_path = str(target_path)
    elif image_path:
        path = resolve_blueprint_path(image_path)
        if not path or not path.exists():
            raise HTTPException(status_code=404, detail=f"Image path not found: {image_path}")
        img = cv2.imread(str(path))
        saved_path = str(path)
    else:
        raise HTTPException(status_code=400, detail="Provide either file upload or image_path.")

    if img is None:
        raise HTTPException(status_code=400, detail="Failed to decode image.")

    decomp = processor.decompose(img)
    detector = AxisDetector()
    axes = detector.analyze_all(decomp.top_view, decomp.front_view, decomp.side_view)

    def format_crop(crop):
        if not crop:
            return None
        b64 = None
        if include_images:
            _, buffer = cv2.imencode(".png", crop.image)
            b64 = base64.b64encode(buffer).decode("utf-8")
        return ViewCropResponse(
            view_type=crop.view_type,
            bbox=BBoxResponse(
                x=crop.bbox.x,
                y=crop.bbox.y,
                width=crop.bbox.width,
                height=crop.bbox.height,
            ),
            image_base64=b64,
        )

    return DecomposeResponse(
        original_width=decomp.original_shape[1],
        original_height=decomp.original_shape[0],
        top_view=format_crop(decomp.top_view),
        front_view=format_crop(decomp.front_view),
        side_view=format_crop(decomp.side_view),
        wingspan_px=axes.wingspan_px,
        length_px=axes.length_px,
        height_px=axes.height_px,
        saved_path=saved_path,
    )


@router.post("/calibrate")
async def calibrate_blueprint(req: CalibrationRequest):
    """Compute scale factor (pixels/meter) and origin offsets for 3D world conversion."""
    from app.cv.axis_detector import AircraftBlueprintAxes, ViewAxes

    axes = AircraftBlueprintAxes(
        top=ViewAxes(view_type="top", centerline_px=req.top_centerline_px),
        front=ViewAxes(view_type="front", centerline_px=req.front_centerline_px),
        side=ViewAxes(view_type="side", centerline_px=req.side_thrustline_px),
        wingspan_px=req.wingspan_px,
        length_px=req.length_px,
    )
    specs = AircraftDimensions(
        wingspan_m=req.wingspan_m,
        length_m=req.length_m,
        height_m=req.height_m,
    )

    calibrator = BlueprintCalibrator()
    result = calibrator.calibrate(axes, specs)

    return {
        "pixels_per_meter": result.pixels_per_meter,
        "wingspan_px": result.wingspan_px,
        "length_px": result.length_px,
        "origin_top_px": result.origin_top_px,
        "origin_front_px": result.origin_front_px,
        "origin_side_px": result.origin_side_px,
    }

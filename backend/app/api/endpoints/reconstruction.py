"""Aircraft 3D Reconstruction and Lofting API Endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.cv import (
    AircraftDimensions,
    AxisDetector,
    BlueprintCalibrator,
    BlueprintProcessor,
)
from app.geometry import (
    FuselageLofter,
    WingGenerator,
    WingParameters,
    calculate_mesh_metrics,
    calculate_projected_planform_area,
    merge_meshes,
)

router = APIRouter(prefix="/reconstruction", tags=["reconstruction"])


class GenerateAircraftRequest(BaseModel):
    blueprint_path: str = "docs/blueprint.jpg"
    wingspan_m: float = 11.14
    length_m: float = 11.38
    height_m: float = 3.97
    num_fuselage_stations: int = 18
    vertices_per_ring: int = 16


@router.post("/generate-aircraft")
async def generate_aircraft(req: GenerateAircraftRequest):
    """
    Generate complete 3D aircraft model from blueprint:
    - Decomposes blueprint into 3 views.
    - Calibrates scale and origins.
    - Lofts fuselage cross-section stations in quad rings.
    - Extrudes wings and tail empennage.
    - Merges into full aircraft mesh and computes aerodynamic metrics.
    """
    bp_path = Path(req.blueprint_path)
    if not bp_path.exists():
        raise HTTPException(status_code=404, detail=f"Blueprint not found: {req.blueprint_path}")

    # 1. Computer Vision: Decompose and Calibrate
    processor = BlueprintProcessor()
    decomp = processor.decompose_file(bp_path)
    detector = AxisDetector()
    axes = detector.analyze_all(decomp.top_view, decomp.front_view, decomp.side_view)

    specs = AircraftDimensions(
        wingspan_m=req.wingspan_m,
        length_m=req.length_m,
        height_m=req.height_m,
    )
    calibrator = BlueprintCalibrator()
    calib = calibrator.calibrate(axes, specs)

    # 2. Loft Fuselage from Blueprint Masks
    lofter = FuselageLofter(
        num_stations=req.num_fuselage_stations,
        vertices_per_ring=req.vertices_per_ring,
    )

    if decomp.top_view and decomp.side_view:
        profile = lofter.extract_profile_from_masks(
            top_mask=decomp.top_view.binary_mask,
            side_mask=decomp.side_view.binary_mask,
            pixels_per_meter=calib.pixels_per_meter,
            origin_top=calib.origin_top_px,
            origin_side=calib.origin_side_px,
        )
    else:
        profile = lofter.generate_synthetic_profile(
            length_m=req.length_m,
            nose_z=req.length_m * 0.45,
        )

    fuselage_mesh = lofter.loft_fuselage_mesh(profile, mesh_name="fuselagem")

    # 3. Generate Wings and Empennage
    wing_gen = WingGenerator()
    semi_span = req.wingspan_m / 2.0
    root_chord = req.length_m * 0.20
    tip_chord = root_chord * 0.50

    w_params = WingParameters(
        name="wing",
        semi_span_m=semi_span - 0.60,
        root_chord_m=root_chord,
        tip_chord_m=tip_chord,
        sweep_deg=4.5,
        dihedral_deg=5.0,
        root_x=0.60,
        root_y=-0.15,
        root_z=req.length_m * 0.08,
    )

    wing_r = wing_gen.generate_wing_mesh(w_params, side="right")
    wing_l = wing_gen.generate_wing_mesh(w_params, side="left")

    h_r, h_l, v_fin = wing_gen.generate_empennage(
        h_span_m=req.wingspan_m * 0.35,
        h_chord_m=req.length_m * 0.10,
        v_span_m=req.height_m * 0.50,
        v_chord_m=req.length_m * 0.13,
        tail_z=-req.length_m * 0.40,
        tail_y=0.20,
    )

    # 4. Merge into Complete Aircraft
    full_aircraft = merge_meshes(
        [fuselage_mesh, wing_r, wing_l, h_r, h_l, v_fin],
        merged_name="complete_aircraft",
    )

    metrics = calculate_mesh_metrics(full_aircraft)
    wing_area_m2 = calculate_projected_planform_area(full_aircraft)

    return {
        "status": "success",
        "aircraft_name": "Reconstructed Aircraft",
        "metrics": metrics,
        "wing_area_m2": round(wing_area_m2, 2),
        "scale_pixels_per_meter": round(calib.pixels_per_meter, 2),
        "components": {
            "fuselage": calculate_mesh_metrics(fuselage_mesh),
            "wing_right": calculate_mesh_metrics(wing_r),
            "wing_left": calculate_mesh_metrics(wing_l),
            "elevator_right": calculate_mesh_metrics(h_r),
            "elevator_left": calculate_mesh_metrics(h_l),
            "rudder": calculate_mesh_metrics(v_fin),
        },
        "srf_preview": full_aircraft.to_srf(short_syntax=True)[:1500] + "\n...",
    }

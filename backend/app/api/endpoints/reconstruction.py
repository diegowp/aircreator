"""Aircraft 3D Reconstruction and Lofting API Endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import resolve_blueprint_path
from app.cv import (
    AircraftDimensions,
    AxisDetector,
    BlueprintCalibrator,
    BlueprintProcessor,
)
from app.geometry import (
    FuselageLofter,
    KinematicsRiggingEngine,
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
    propeller_blades: int | None = None


@router.post("/generate-aircraft")
async def generate_aircraft(req: GenerateAircraftRequest):
    """
    Generate complete 3D aircraft model from blueprint:
    - Decomposes blueprint into 3 views.
    - Calibrates scale and origins.
    - Lofts fuselage cross-section stations in quad rings.
    - Extrudes wings and tail empennage.
    - Generates transparent cockpit canopy and propeller blades with spinner.
    - Slices control surfaces and rigs kinematics pivots (ailerons, elevators, rudder).
    - Returns structured component meshes for WebGL rendering and full SRF text.
    """
    resolved_bp = resolve_blueprint_path(req.blueprint_path)
    decomp = None

    if resolved_bp and resolved_bp.exists():
        try:
            processor = BlueprintProcessor()
            decomp = processor.decompose_file(resolved_bp)
            detector = AxisDetector()
            axes = detector.analyze_all(decomp.top_view, decomp.front_view, decomp.side_view)
            specs = AircraftDimensions(
                wingspan_m=req.wingspan_m,
                length_m=req.length_m,
                height_m=req.height_m,
            )
            calibrator = BlueprintCalibrator()
            calib = calibrator.calibrate(axes, specs)
        except Exception:
            decomp = None

    if decomp is None:
        # Fallback calibration if blueprint is not available
        from app.cv.axis_detector import AircraftBlueprintAxes, ViewAxes
        top_axes = ViewAxes(view_type="top", centerline_px=250.0, span_or_length_px=500.0)
        front_axes = ViewAxes(view_type="front", centerline_px=250.0, thrustline_px=100.0, span_or_length_px=500.0)
        side_axes = ViewAxes(view_type="side", centerline_px=100.0, thrustline_px=100.0, groundline_px=160.0, span_or_length_px=500.0)
        axes = AircraftBlueprintAxes(
            top=top_axes,
            front=front_axes,
            side=side_axes,
            wingspan_px=500.0,
            length_px=500.0,
            height_px=180.0,
        )
        specs = AircraftDimensions(
            wingspan_m=req.wingspan_m,
            length_m=req.length_m,
            height_m=req.height_m,
        )
        calibrator = BlueprintCalibrator()
        calib = calibrator.calibrate(axes, specs)

    # 2. Loft Fuselage from Blueprint Masks (or synthetic profile)
    lofter = FuselageLofter(
        num_stations=req.num_fuselage_stations,
        vertices_per_ring=req.vertices_per_ring,
    )

    if decomp and decomp.top_view and decomp.side_view:
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

    # 4. Generate Canopy and Propeller
    (f_min_x, f_min_y, f_min_z), (f_max_x, f_max_y, f_max_z) = fuselage_mesh.bounding_box()
    f_len = max(1.0, f_max_z - f_min_z)

    canopy_mesh = wing_gen.generate_canopy_mesh(
        cockpit_start_z=f_max_z - f_len * 0.22,
        cockpit_end_z=f_max_z - f_len * 0.56,
        base_y=0.38,
        max_height=req.height_m * 0.16,
        max_half_width=req.wingspan_m * 0.045,
    )

    num_blades = req.propeller_blades or (5 if req.wingspan_m >= 10.5 else 3)
    propeller_mesh = wing_gen.generate_propeller_mesh(
        nose_z=f_max_z,
        thrustline_y=0.0,
        spinner_length=f_len * 0.09,
        spinner_radius=f_len * 0.038,
        prop_radius=req.wingspan_m * 0.12,
        num_blades=num_blades,
    )

    # 5. Kinematics Rigging & Control Surface Slicing
    rigging_engine = KinematicsRiggingEngine()
    dnm_model = rigging_engine.rig_complete_aircraft(
        fuselage_mesh=fuselage_mesh,
        wing_r_mesh=wing_r,
        wing_l_mesh=wing_l,
        h_stab_r_mesh=h_r,
        h_stab_l_mesh=h_l,
        v_fin_mesh=v_fin,
        propeller_mesh=propeller_mesh,
        canopy_mesh=canopy_mesh,
    )
    component_meshes = rigging_engine.get_component_meshes_dict()

    # 6. Merge into Complete Aircraft
    full_aircraft = merge_meshes(
        [fuselage_mesh, canopy_mesh, wing_r, wing_l, h_r, h_l, v_fin, propeller_mesh],
        merged_name="complete_aircraft",
    )

    metrics = calculate_mesh_metrics(full_aircraft)
    wing_area_m2 = calculate_projected_planform_area(full_aircraft)
    full_srf_str = full_aircraft.to_srf(short_syntax=True)

    return {
        "status": "success",
        "aircraft_name": "Reconstructed Aircraft",
        "metrics": metrics,
        "wing_area_m2": round(wing_area_m2, 2),
        "scale_pixels_per_meter": round(calib.pixels_per_meter, 2),
        "components": {
            "fuselage": calculate_mesh_metrics(fuselage_mesh),
            "canopy": calculate_mesh_metrics(canopy_mesh),
            "wing_right": calculate_mesh_metrics(wing_r),
            "wing_left": calculate_mesh_metrics(wing_l),
            "elevator_right": calculate_mesh_metrics(h_r),
            "elevator_left": calculate_mesh_metrics(h_l),
            "rudder": calculate_mesh_metrics(v_fin),
            "propeller": calculate_mesh_metrics(propeller_mesh),
        },
        "component_meshes": component_meshes,
        "full_srf": full_srf_str,
        "srf_preview": full_srf_str[:1500] + "\n...",
    }


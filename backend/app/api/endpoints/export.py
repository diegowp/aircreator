"""Aircraft Export, Presets, and Validation REST API Endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.cv import (
    AircraftDimensions,
    AxisDetector,
    BlueprintCalibrator,
    BlueprintProcessor,
)
from app.export import (
    AircraftExportPackage,
    AircraftValidator,
    sanitize_aircraft_id,
)
from app.geometry import (
    FuselageLofter,
    KinematicsRiggingEngine,
    WingGenerator,
    WingParameters,
    merge_meshes,
)
from app.physics import (
    AIRCRAFT_PRESETS,
    AeroPhysicsCalibrator,
    CollisionMeshGenerator,
)

router = APIRouter(prefix="/export", tags=["export"])


class ExportRequest(BaseModel):
    aircraft_name: str = "EMB-314 Super Tucano"
    blueprint_path: str = "docs/blueprint.jpg"
    preset_name: str = "SUPER_TUCANO"
    wingspan_m: float = 11.14
    length_m: float = 11.38
    height_m: float = 3.97


def build_pipeline_package(req: ExportRequest) -> AircraftExportPackage:
    """Run full automated reconstruction and rigging pipeline to build an exportable package."""
    bp_path = Path(req.blueprint_path)
    if not bp_path.exists():
        raise HTTPException(status_code=404, detail=f"Blueprint not found: {req.blueprint_path}")

    # 1. CV Decompose & Calibrate
    processor = BlueprintProcessor()
    decomp = processor.decompose_file(bp_path)
    detector = AxisDetector()
    axes = detector.analyze_all(decomp.top_view, decomp.front_view, decomp.side_view)
    specs = AircraftDimensions(wingspan_m=req.wingspan_m, length_m=req.length_m, height_m=req.height_m)
    calibrator = BlueprintCalibrator()
    calib = calibrator.calibrate(axes, specs)

    # 2. Loft Fuselage
    lofter = FuselageLofter(num_stations=18, vertices_per_ring=16)
    if decomp.top_view and decomp.side_view:
        profile = lofter.extract_profile_from_masks(
            top_mask=decomp.top_view.binary_mask,
            side_mask=decomp.side_view.binary_mask,
            pixels_per_meter=calib.pixels_per_meter,
            origin_top=calib.origin_top_px,
            origin_side=calib.origin_side_px,
        )
    else:
        profile = lofter.generate_synthetic_profile(length_m=req.length_m)
    fuselage_mesh = lofter.loft_fuselage_mesh(profile, mesh_name="fuselagem")

    # 3. Wings & Empennage
    wing_gen = WingGenerator()
    semi_span = req.wingspan_m / 2.0
    w_params = WingParameters(
        name="wing",
        semi_span_m=semi_span - 0.60,
        root_chord_m=req.length_m * 0.20,
        tip_chord_m=req.length_m * 0.10,
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
    )

    full_visual_mesh = merge_meshes([fuselage_mesh, wing_r, wing_l, h_r, h_l, v_fin])

    # 4. Kinematic Scene Graph (.DNM)
    rigging_engine = KinematicsRiggingEngine()
    dnm_model = rigging_engine.rig_complete_aircraft(
        fuselage_mesh=fuselage_mesh,
        wing_r_mesh=wing_r,
        wing_l_mesh=wing_l,
        h_stab_r_mesh=h_r,
        h_stab_l_mesh=h_l,
        v_fin_mesh=v_fin,
    )

    # 5. Flight Dynamics (.DAT) & Collision Mesh
    phys_calibrator = AeroPhysicsCalibrator()
    dat_model = phys_calibrator.generate_flight_model(
        aircraft_mesh=full_visual_mesh,
        identify=req.aircraft_name,
        preset_name=req.preset_name,
    )

    coll_gen = CollisionMeshGenerator()
    collision_mesh = coll_gen.generate_collision_mesh(full_visual_mesh)

    aid = sanitize_aircraft_id(req.aircraft_name)

    return AircraftExportPackage(
        aircraft_id=aid,
        display_name=req.aircraft_name,
        dat_model=dat_model,
        dnm_model=dnm_model,
        collision_mesh=collision_mesh,
        visual_mesh=full_visual_mesh,
    )


@router.get("/presets")
async def get_aircraft_presets():
    """List available aeronautical configuration presets."""
    return [
        {
            "id": key,
            "category": p.category_name,
            "propulsion": p.propulsion_type,
            "default_hp": p.default_hp,
            "default_thrust_kg": p.default_thrust_kg,
            "has_afterburner": p.has_afterburner,
        }
        for key, p in AIRCRAFT_PRESETS.items()
    ]


@router.post("/validate")
async def validate_aircraft(req: ExportRequest):
    """Run full YSFlight engineering standards validation checklist."""
    package = build_pipeline_package(req)
    validator = AircraftValidator()
    report = validator.validate_package(package)

    return {
        "is_valid": report.is_valid,
        "total_checks": report.total_checks,
        "passed_checks": report.passed_checks,
        "errors": report.errors,
        "warnings": report.warnings,
        "aircraft_id": package.aircraft_id,
        "mtow_ton": package.dat_model.mtow_ton,
        "wing_area_m2": package.dat_model.wingarea,
    }


@router.post("/ysflight-zip")
async def export_ysflight_zip(req: ExportRequest):
    """Generate and download complete YSFlight aircraft ZIP package."""
    package = build_pipeline_package(req)
    zip_bytes = package.generate_ysflight_zip()

    filename = f"{package.aircraft_id}_ysflight.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/obj")
async def export_obj(req: ExportRequest):
    """Generate Wavefront OBJ text."""
    package = build_pipeline_package(req)
    obj_text, mtl_text = package.generate_obj_with_mtl()

    return {
        "aircraft_id": package.aircraft_id,
        "obj": obj_text,
        "mtl": mtl_text,
    }

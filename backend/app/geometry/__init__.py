"""Geometry package for aircraft lofting, wing generation, and kinematics rigging."""

from app.geometry.fuselage_lofter import (
    FuselageLofter,
    FuselageStation,
    LoftingProfileData,
)
from app.geometry.kinematics_rigging import (
    AircraftRiggingComponents,
    KinematicsRiggingEngine,
    degrees_to_angle16,
)
from app.geometry.mesh_ops import (
    calculate_mesh_metrics,
    calculate_projected_planform_area,
    merge_meshes,
    mirror_mesh_x,
)
from app.geometry.part_slicer import (
    PartSlicer,
    SlicedControlSurfaceResult,
)
from app.geometry.wing_generator import (
    WingGenerator,
    WingParameters,
)

__all__ = [
    "FuselageStation",
    "LoftingProfileData",
    "FuselageLofter",
    "WingParameters",
    "WingGenerator",
    "mirror_mesh_x",
    "merge_meshes",
    "calculate_projected_planform_area",
    "calculate_mesh_metrics",
    "PartSlicer",
    "SlicedControlSurfaceResult",
    "degrees_to_angle16",
    "AircraftRiggingComponents",
    "KinematicsRiggingEngine",
]

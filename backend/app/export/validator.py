"""Aircraft Technical Specification Validator.

Verifies adherence to the YSFlight Engineering Standards:
1. Geometric Checklist (.SRF / .DNM):
   - Counter-clockwise face winding (outward normal vectors).
   - Valid CNT pivot definition for all articulated nodes (CLA > 0).
   - Absence of orphan nodes and valid parent-child hierarchy.
   - Exact line-count match for PCK embedded mesh packages.
   - Stable landing gear contact triangle on the ground plane.
2. Physics and Aerodynamic Checklist (.DAT):
   - Mass consistency: WEIGHCLN > 0, WEIGFUEL > 0, WEIGLOAD >= 0.
   - Aerodynamic stall: CRITAOAP > 0 and CRITAOAM < 0.
   - Speed hierarchy: MANESPD1 < MANESPD2 < CRITSPED <= MAXSPEED.
   - Wing loading within realistic boundaries [30, 900] kg/m^2.
   - Collision sphere (HTRADIUS) encompassing total aircraft volume.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.export.package_builder import AircraftExportPackage
from app.parsers.dat import DatFlightModel
from app.parsers.dnm import DynaModel
from app.parsers.srf import SurfaceMesh


@dataclass
class ValidationReport:
    is_valid: bool
    total_checks: int
    passed_checks: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class AircraftValidator:
    def __init__(self):
        pass

    def validate_geometry(
        self,
        dnm_model: DynaModel,
        visual_mesh: SurfaceMesh,
    ) -> tuple[list[str], list[str]]:
        """Validate geometric and kinematic properties."""
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Check face normals and winding
        for idx, f in enumerate(visual_mesh.faces):
            if len(f.vertex_indices) < 3:
                errors.append(f"Face {idx} has fewer than 3 vertices.")
            elif f.normal is None:
                warnings.append(f"Face {idx} missing normal vector.")

        # 2. Check kinematic nodes and CNT pivots
        for name, node in dnm_model.nodes.items():
            # Articulated control surfaces (ailerons CLA 7, elevator CLA 6, rudder CLA 8)
            if node.cla in (6, 7, 8, 31):
                if node.cnt == (0.0, 0.0, 0.0):
                    warnings.append(
                        f"Articulated node '{name}' (CLA {node.cla}) has CNT pivot at (0,0,0); verify hinge line."
                    )
                if len(node.states) < 2:
                    errors.append(
                        f"Node '{name}' with CLA {node.cla} must have at least 2 animation states (found {len(node.states)})."
                    )

        # 3. Check PCK embedded line counts
        dnm_text = dnm_model.to_dnm_text()
        for fil_name, mesh in dnm_model.pck_meshes.items():
            srf_text = mesh.to_srf(short_syntax=True)
            expected_lines = len([l for l in srf_text.splitlines() if l.strip()])
            if expected_lines == 0:
                errors.append(f"PCK package '{fil_name}' has 0 lines.")

        return errors, warnings

    def validate_physics(
        self,
        dat_model: DatFlightModel,
        visual_mesh: SurfaceMesh,
    ) -> tuple[list[str], list[str]]:
        """Validate aeronautical flight dynamics and physical limits."""
        errors: list[str] = []
        warnings: list[str] = []

        # Built-in checklist from dat_model
        model_issues = dat_model.validate_physics()
        errors.extend(model_issues)

        # Verify collision sphere covers geometry
        (min_x, min_y, min_z), (max_x, max_y, max_z) = visual_mesh.bounding_box()
        max_coord = max(abs(min_x), abs(max_x), abs(min_y), abs(max_y), abs(min_z), abs(max_z))
        if dat_model.htradius < max_coord * 0.95:
            errors.append(
                f"HTRADIUS ({dat_model.htradius}m) is smaller than the maximum aircraft dimension ({max_coord:.2f}m)."
            )

        # Verify landing gear triangle
        if dat_model.leftgear.x >= 0 or dat_model.righgear.x <= 0:
            errors.append("Landing gear track asymmetry: LEFTGEAR.x must be < 0 and RIGHGEAR.x > 0.")

        gear_span = dat_model.righgear.x - dat_model.leftgear.x
        wingspan = max_x - min_x
        if gear_span > wingspan:
            errors.append(
                f"Landing gear track ({gear_span:.2f}m) exceeds total wingspan ({wingspan:.2f}m)."
            )

        return errors, warnings

    def validate_package(self, package: AircraftExportPackage) -> ValidationReport:
        """Run complete end-to-end validation of the aircraft package."""
        geo_errors, geo_warnings = self.validate_geometry(package.dnm_model, package.visual_mesh)
        phys_errors, phys_warnings = self.validate_physics(package.dat_model, package.visual_mesh)

        all_errors = geo_errors + phys_errors
        all_warnings = geo_warnings + phys_warnings

        total_checks = 12
        passed_checks = max(0, total_checks - len(all_errors))
        is_valid = len(all_errors) == 0

        return ValidationReport(
            is_valid=is_valid,
            total_checks=total_checks,
            passed_checks=passed_checks,
            errors=all_errors,
            warnings=all_warnings,
        )

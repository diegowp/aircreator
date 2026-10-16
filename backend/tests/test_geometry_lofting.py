"""Unit tests for parametric fuselage lofting, wing generation, and mesh operations."""

import unittest
from pathlib import Path

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
    mirror_mesh_x,
)


class TestGeometryLofting(unittest.TestCase):
    def test_fuselage_synthetic_lofting(self):
        lofter = FuselageLofter(num_stations=16, vertices_per_ring=12)
        profile = lofter.generate_synthetic_profile(
            length_m=10.0,
            max_width_m=1.2,
            max_height_m=1.5,
            nose_z=4.0,
        )

        mesh = lofter.loft_fuselage_mesh(profile, mesh_name="synthetic_fuselage")

        # 1 apex nose + 16*12 stations + 1 apex tail = 194 vertices
        self.assertEqual(len(mesh.vertices), 194)

        # 12 nose triangles + 15*12 quads + 12 tail triangles = 204 faces
        self.assertEqual(len(mesh.faces), 204)

        # Body vertices must have round shading (Round Shading 'R' flag)
        round_count = sum(1 for v in mesh.vertices if v.round_shading)
        self.assertEqual(round_count, len(mesh.vertices))

        # Check bounding box
        (min_x, min_y, min_z), (max_x, max_y, max_z) = mesh.bounding_box()
        self.assertAlmostEqual(max_z - min_z, 10.0, delta=1.5)
        self.assertAlmostEqual(max_x - min_x, 1.2, delta=0.3)

    def test_fuselage_lofting_from_blueprint(self):
        blueprint_path = Path(__file__).resolve().parent.parent.parent / "docs" / "blueprint.jpg"
        if not blueprint_path.exists():
            self.skipTest("blueprint.jpg not found")

        # Decompose & Calibrate
        processor = BlueprintProcessor()
        decomp = processor.decompose_file(blueprint_path)
        detector = AxisDetector()
        axes = detector.analyze_all(decomp.top_view, decomp.front_view, decomp.side_view)
        calibrator = BlueprintCalibrator()
        specs = AircraftDimensions(wingspan_m=11.14, length_m=11.38, height_m=3.97)
        calib = calibrator.calibrate(axes, specs)

        # Extract profile from masks
        lofter = FuselageLofter(num_stations=18, vertices_per_ring=16)
        profile = lofter.extract_profile_from_masks(
            top_mask=decomp.top_view.binary_mask,
            side_mask=decomp.side_view.binary_mask,
            pixels_per_meter=calib.pixels_per_meter,
            origin_top=calib.origin_top_px,
            origin_side=calib.origin_side_px,
        )

        mesh = lofter.loft_fuselage_mesh(profile, mesh_name="super_tucano_fuselage")
        metrics = calculate_mesh_metrics(mesh)

        self.assertGreater(metrics["num_vertices"], 200)
        self.assertGreater(metrics["num_faces"], 200)
        self.assertGreater(metrics["length_m"], 8.0)
        self.assertLess(metrics["length_m"], 14.0)

    def test_wing_generation(self):
        gen = WingGenerator()
        params = WingParameters(
            name="super_tucano_wing",
            semi_span_m=5.0,
            root_chord_m=2.2,
            tip_chord_m=1.0,
            sweep_deg=5.0,
            dihedral_deg=4.5,
            num_span_stations=6,
            num_foil_points=10,
        )

        right_wing = gen.generate_wing_mesh(params, side="right")
        left_wing = gen.generate_wing_mesh(params, side="left")

        # Check symmetry
        (r_min_x, _, _), (r_max_x, _, _) = right_wing.bounding_box()
        (l_min_x, _, _), (l_max_x, _, _) = left_wing.bounding_box()

        # Right wing is in positive X, left wing is in negative X
        self.assertGreater(r_min_x, 0.0)
        self.assertLess(l_max_x, 0.0)
        self.assertAlmostEqual(r_max_x, -l_min_x, places=2)

    def test_empennage_generation(self):
        gen = WingGenerator()
        h_r, h_l, v_fin = gen.generate_empennage(
            h_span_m=3.8,
            h_chord_m=1.1,
            v_span_m=2.0,
            v_chord_m=1.5,
            tail_z=-4.0,
            tail_y=0.2,
        )

        self.assertEqual(h_r.name, "elevator_1_right")
        self.assertEqual(h_l.name, "elevator_1_left")
        self.assertEqual(v_fin.name, "rudder_1_center")

        # Vertical fin must extend in +Y
        (_, min_y, _), (_, max_y, _) = v_fin.bounding_box()
        self.assertGreater(max_y - min_y, 1.5)

    def test_mesh_operations_merge_and_area(self):
        lofter = FuselageLofter(num_stations=12, vertices_per_ring=12)
        fuselage = lofter.loft_fuselage_mesh(
            lofter.generate_synthetic_profile(length_m=10.0),
            mesh_name="fuselage",
        )

        gen = WingGenerator()
        w_params = WingParameters(semi_span_m=4.5, root_chord_m=2.0, tip_chord_m=1.0)
        wing_r = gen.generate_wing_mesh(w_params, side="right")
        wing_l = gen.generate_wing_mesh(w_params, side="left")

        # Test mirroring
        mirrored_l = mirror_mesh_x(wing_r, new_name="mirrored_left")
        self.assertEqual(mirrored_l.name, "mirrored_left")
        self.assertAlmostEqual(wing_r.vertices[0].x, -mirrored_l.vertices[0].x)

        # Test merging full aircraft
        aircraft = merge_meshes([fuselage, wing_r, wing_l], merged_name="full_plane")
        self.assertEqual(
            len(aircraft.vertices),
            len(fuselage.vertices) + len(wing_r.vertices) + len(wing_l.vertices),
        )

        # Planform area calculation (projected XZ area)
        wing_area = calculate_projected_planform_area(aircraft)
        # Expected wing area for ~9m span with ~1.5m mean chord is ~12-16 m^2
        self.assertGreater(wing_area, 10.0)
        self.assertLess(wing_area, 25.0)


if __name__ == "__main__":
    unittest.main()

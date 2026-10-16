"""Unit tests for aerodynamic physics calibration, landing gear estimation, and collision mesh."""

import unittest

from app.geometry import (
    FuselageLofter,
    WingGenerator,
    WingParameters,
    merge_meshes,
)
from app.physics import (
    AIRCRAFT_PRESETS,
    AeroPhysicsCalibrator,
    CollisionMeshGenerator,
)


class TestPhysicsAero(unittest.TestCase):
    def setUp(self):
        # Build standard aircraft mesh for physics testing
        lofter = FuselageLofter(num_stations=12, vertices_per_ring=12)
        fuselage = lofter.loft_fuselage_mesh(
            lofter.generate_synthetic_profile(length_m=11.38),
            mesh_name="fuselagem",
        )

        wing_gen = WingGenerator()
        w_params = WingParameters(
            name="wing",
            semi_span_m=5.0,
            root_chord_m=2.2,
            tip_chord_m=1.1,
            root_x=0.6,
        )
        wing_r = wing_gen.generate_wing_mesh(w_params, side="right")
        wing_l = wing_gen.generate_wing_mesh(w_params, side="left")
        h_r, h_l, v_fin = wing_gen.generate_empennage(
            h_span_m=3.8, h_chord_m=1.0, v_span_m=2.0, v_chord_m=1.3, tail_z=-4.5
        )

        self.aircraft_mesh = merge_meshes([fuselage, wing_r, wing_l, h_r, h_l, v_fin])

    def test_aero_metrics_measurement(self):
        calibrator = AeroPhysicsCalibrator()
        aero = calibrator.calculate_aero_metrics(self.aircraft_mesh)

        # Wingspan should be ~11.2m
        self.assertAlmostEqual(aero["wingspan_m"], 11.2, delta=0.5)

        # Wing area should be around 14 - 32 m^2
        self.assertGreater(aero["wing_area_m2"], 12.0)
        self.assertLess(aero["wing_area_m2"], 35.0)

        # Aspect ratio should be around 4 - 8
        self.assertGreater(aero["aspect_ratio"], 3.5)
        self.assertLess(aero["aspect_ratio"], 10.0)

        # Collision radius HTRADIUS must be > half wingspan
        self.assertGreater(aero["htradius_m"], aero["wingspan_m"] * 0.45)

    def test_landing_gear_estimation(self):
        calibrator = AeroPhysicsCalibrator()
        left, right, nose = calibrator.estimate_landing_gears(self.aircraft_mesh)

        # Left gear negative X, right gear positive X
        self.assertLess(left.x, -1.0)
        self.assertGreater(right.x, 1.0)
        self.assertAlmostEqual(abs(left.x), right.x)

        # Nose gear on centerline X=0 and forward of main gears (Z_nose > Z_main)
        self.assertAlmostEqual(nose.x, 0.0)
        self.assertGreater(nose.z, left.z)

        # Wheels must be at the same ground level Y
        self.assertAlmostEqual(left.y, right.y)
        self.assertAlmostEqual(left.y, nose.y)

    def test_flight_model_physics_validity(self):
        calibrator = AeroPhysicsCalibrator()
        flight_model = calibrator.generate_flight_model(
            aircraft_mesh=self.aircraft_mesh,
            identify="Super Tucano Reconstructed",
            preset_name="SUPER_TUCANO",
        )

        # Weights
        self.assertGreater(flight_model.weighcln, 1.5)
        self.assertGreater(flight_model.weigfuel, 0.4)
        self.assertGreater(flight_model.mtow_ton, 2.5)

        # Speed hierarchy: MANESPD1 < MANESPD2 < CRITSPED <= MAXSPEED
        self.assertLess(flight_model.manespd1_kmh, flight_model.manespd2_kmh)
        self.assertLess(flight_model.manespd2_kmh, flight_model.critsped_kmh)
        self.assertLessEqual(flight_model.critsped_kmh, flight_model.maxspeed_kmh)

        # Validate physics against specification checklist
        issues = flight_model.validate_physics()
        self.assertEqual(len(issues), 0, f"Physics validation failed: {issues}")

    def test_collision_mesh_generation(self):
        generator = CollisionMeshGenerator()
        coll_mesh = generator.generate_collision_mesh(
            self.aircraft_mesh, mesh_name="super_tucano_coll"
        )

        # Extremely low poly count for real-time physics performance
        self.assertGreater(len(coll_mesh.faces), 20)
        self.assertLess(len(coll_mesh.faces), 150)

        # Check that it exports cleanly to .srf
        srf_text = coll_mesh.to_srf(short_syntax=True)
        self.assertIn("SURF", srf_text)
        self.assertIn("C 255 106 0", srf_text)


if __name__ == "__main__":
    unittest.main()

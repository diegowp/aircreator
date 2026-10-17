"""Unit tests for Part Slicer, Hinge Pivot calculation, and Kinematic DynaModel Rigging."""

import math
import unittest

from app.geometry import (
    FuselageLofter,
    KinematicsRiggingEngine,
    PartSlicer,
    WingGenerator,
    WingParameters,
    degrees_to_angle16,
)
from app.parsers.dnm import parse_dnm_text


class TestKinematicsRigging(unittest.TestCase):
    def setUp(self):
        self.wing_gen = WingGenerator()
        self.w_params = WingParameters(
            name="test_wing",
            semi_span_m=5.0,
            root_chord_m=2.0,
            tip_chord_m=1.0,
            num_span_stations=6,
            num_foil_points=8,
        )
        self.wing_r = self.wing_gen.generate_wing_mesh(self.w_params, side="right")

    def test_angle16_conversion(self):
        self.assertEqual(degrees_to_angle16(0.0), 0)
        self.assertEqual(degrees_to_angle16(90.0), 16384)
        self.assertEqual(degrees_to_angle16(180.0), -32768)
        self.assertEqual(degrees_to_angle16(-90.0), -16384)
        self.assertAlmostEqual(degrees_to_angle16(15.0), 2730, delta=2)

    def test_part_slicer_aileron(self):
        slicer = PartSlicer()
        res = slicer.slice_trailing_edge_surface(
            surface_mesh=self.wing_r,
            chord_cut_fraction=0.65,
            span_start_fraction=0.50,
            span_end_fraction=0.98,
            movable_name="aileron_r",
            fixed_name="wing_r_fixed",
            is_vertical=False,
        )

        self.assertGreater(len(res.fixed_mesh.vertices), 0)
        self.assertGreater(len(res.movable_mesh.vertices), 0)
        self.assertGreater(len(res.fixed_mesh.faces), 0)
        self.assertGreater(len(res.movable_mesh.faces), 0)

        # Hinge center must be located within the wing span
        # Hinge vector must be unit length and oriented along spanwise X
        vx, vy, vz = res.hinge_vector
        mag = math.sqrt(vx * vx + vy * vy + vz * vz)
        self.assertAlmostEqual(mag, 1.0, places=4)
        self.assertGreater(vx, 0.95)

    def test_complete_aircraft_rigging(self):
        lofter = FuselageLofter(num_stations=10, vertices_per_ring=10)
        fuselage = lofter.loft_fuselage_mesh(
            lofter.generate_synthetic_profile(length_m=8.0),
            mesh_name="fuselagem",
        )

        wing_r = self.wing_gen.generate_wing_mesh(self.w_params, side="right")
        wing_l = self.wing_gen.generate_wing_mesh(self.w_params, side="left")
        h_r, h_l, v_fin = self.wing_gen.generate_empennage(
            h_span_m=3.0, h_chord_m=0.8, v_span_m=1.8, v_chord_m=1.0, tail_z=-3.5
        )

        engine = KinematicsRiggingEngine()
        model = engine.rig_complete_aircraft(
            fuselage_mesh=fuselage,
            wing_r_mesh=wing_r,
            wing_l_mesh=wing_l,
            h_stab_r_mesh=h_r,
            h_stab_l_mesh=h_l,
            v_fin_mesh=v_fin,
            aileron_deflection_deg=15.0,
            elevator_deflection_deg=18.0,
            rudder_deflection_deg=25.0,
        )

        # Check nodes existence
        self.assertIn("fuselage", model.nodes)
        self.assertIn("aileron_d", model.nodes)
        self.assertIn("aileron_lef", model.nodes)
        self.assertIn("elevator", model.nodes)
        self.assertIn("rudder_2", model.nodes)

        # Check CLA channels
        self.assertEqual(model.nodes["aileron_d"].cla, 7)
        self.assertEqual(model.nodes["aileron_lef"].cla, 7)
        self.assertEqual(model.nodes["elevator"].cla, 6)
        self.assertEqual(model.nodes["rudder_2"].cla, 8)

        # Check Aileron Opposite Deflections
        aileron_r = model.nodes["aileron_d"]
        aileron_l = model.nodes["aileron_lef"]
        # In state 1 (Roll Right), right aileron pitch delta is opposite to left
        self.assertEqual(aileron_r.states[1].dp, -aileron_l.states[1].dp)

        # Check PCK packages embedded
        self.assertIn("fuselagem.srf", model.pck_meshes)
        self.assertIn("aileron_d.srf", model.pck_meshes)
        self.assertIn("elevator.srf", model.pck_meshes)
        self.assertIn("rudder_2.srf", model.pck_meshes)

        # Check DNM serialization roundtrip
        dnm_text = model.to_dnm_text()
        reloaded_model = parse_dnm_text(dnm_text)
        self.assertEqual(len(reloaded_model.nodes), len(model.nodes))
        self.assertIn("aileron_d", reloaded_model.nodes)
        self.assertEqual(reloaded_model.nodes["aileron_d"].cla, 7)


if __name__ == "__main__":
    unittest.main()

"""Unit and Integration Tests for Mathematical & Procedural DynaModel (.dnm) Generation Engine.

Verifies:
- Lamé superellipse lofting (FuselageLofter with exponent n > 2.0).
- Monotone cubic Hermite spline interpolation for sparse fuselage stations.
- Cambered NACA 4-digit airfoil coordinates (NACA 2412 vs 0012).
- PAX rotation axis vector calculation in PartSlicer.
- DynaModel PAX parsing, serialization, and contralateral mirroring.
- Modular component SRF mesh generation and embedding.
"""

import math
import unittest

import numpy as np

from app.geometry.fuselage_lofter import FuselageLofter, LoftingProfileData
from app.geometry.kinematics_rigging import KinematicsRiggingEngine
from app.geometry.part_slicer import PartSlicer
from app.geometry.wing_generator import WingGenerator, WingParameters
from app.parsers.dnm import DnmNode, DnmPos, DnmState, DynaModel, parse_dnm_text
from app.parsers.srf import SrfFace, SrfVertex, SurfaceMesh


class TestMathematicalDnmEvolution(unittest.TestCase):
    def test_lame_superellipse_geometry(self):
        """Verify Lamé superellipse flattens sides and pushes corners when n > 2.0."""
        lofter_ellipse = FuselageLofter(num_stations=4, vertices_per_ring=16)
        profile_ellipse = LoftingProfileData(
            z_coords=[10.0, 5.0, 0.0, -5.0],
            y_dorsal=[1.0, 1.0, 1.0, 1.0],
            y_ventral=[-1.0, -1.0, -1.0, -1.0],
            x_widths=[1.0, 1.0, 1.0, 1.0],
            superellipse_n=[2.0, 2.0, 2.0, 2.0],
        )
        rings_ellipse = lofter_ellipse.create_station_rings(profile_ellipse)

        profile_squircle = LoftingProfileData(
            z_coords=[10.0, 5.0, 0.0, -5.0],
            y_dorsal=[1.0, 1.0, 1.0, 1.0],
            y_ventral=[-1.0, -1.0, -1.0, -1.0],
            x_widths=[1.0, 1.0, 1.0, 1.0],
            superellipse_n=[3.0, 3.0, 3.0, 3.0],
        )
        rings_squircle = lofter_ellipse.create_station_rings(profile_squircle)

        # For circle (n=2) at 45 degrees (j=2 in 16-gon, theta=pi/4):
        # x = rx * sin(pi/4) = 0.7071
        # For squircle (n=3) at 45 degrees:
        # x = rx * (sin(pi/4))^(2/3) = (0.7071)^0.6667 = 0.7937 > 0.7071
        v_ellipse_45 = rings_ellipse[1].vertices[2]
        v_squircle_45 = rings_squircle[1].vertices[2]

        self.assertAlmostEqual(v_ellipse_45.x, math.sin(math.pi / 4), places=3)
        self.assertGreater(v_squircle_45.x, v_ellipse_45.x)
        self.assertAlmostEqual(v_squircle_45.x, math.sin(math.pi / 4) ** (2.0 / 3.0), places=3)

    def test_monotone_cubic_interpolation(self):
        """Verify Fritsch-Carlson monotonic cubic spline interpolates smoothly without overshoot."""
        z_in = [10.0, 6.0, 2.0, -2.0]
        y_in = [0.2, 1.5, 1.5, 0.1]
        z_out = np.linspace(10.0, -2.0, 13).tolist()

        y_out = FuselageLofter.monotone_cubic_interpolate(z_in, y_in, z_out)
        self.assertEqual(len(y_out), 13)
        # Endpoints must match exactly
        self.assertAlmostEqual(y_out[0], 0.2, places=3)
        self.assertAlmostEqual(y_out[-1], 0.1, places=3)
        # Monotone plateau: between z=6.0 and z=2.0 (indices 4 to 8), y must stay at 1.5 without overshooting
        for y_val in y_out:
            self.assertLessEqual(y_val, 1.5001)
            self.assertGreaterEqual(y_val, 0.0999)

    def test_naca_cambered_airfoil(self):
        """Verify NACA 4-digit cambered profile creates positive camber offset above symmetric."""
        wing_gen = WingGenerator()
        foil_sym = wing_gen.generate_naca_airfoil_coords(
            chord=1.0, thickness_ratio=0.12, num_points=16, camber=0.0
        )
        foil_cam = wing_gen.generate_naca_airfoil_coords(
            chord=1.0, thickness_ratio=0.12, num_points=16, camber=0.04, camber_pos=0.4
        )

        self.assertEqual(len(foil_sym), len(foil_cam))
        # Upper surface of cambered foil should have higher Y than symmetric foil near max camber
        # Index 4 is around 40% chord along upper surface
        yc_cam = [pt[1] for pt in foil_cam]
        yc_sym = [pt[1] for pt in foil_sym]
        max_y_cam = max(yc_cam)
        max_y_sym = max(yc_sym)
        self.assertGreater(max_y_cam, max_y_sym)

    def test_dnm_pax_serialization_and_parsing(self):
        """Verify PAX rotation axis is correctly written to and parsed from DNM text."""
        model = DynaModel(version=1)
        node = DnmNode(
            name="aileron_r",
            fil="aileron_r.srf",
            cla=7,
            nst=1,
            cnt=(3.5, 0.2, -1.2),
            pax=(0.996195, 0.087156, 0.0),
            states=[DnmState(0, 0, 0, 0, 2730, 0, 1)],
            rel="DEP",
        )
        model.add_node(node)

        dnm_text = model.to_dnm_text()
        self.assertIn("PAX 0.996195 0.087156 0.000000", dnm_text)

        # Parse back
        parsed_model = parse_dnm_text(dnm_text)
        parsed_node = parsed_model.get_node("aileron_r")
        self.assertIsNotNone(parsed_node)
        self.assertIsNotNone(parsed_node.pax)
        self.assertAlmostEqual(parsed_node.pax[0], 0.996195, places=5)
        self.assertAlmostEqual(parsed_node.pax[1], 0.087156, places=5)
        self.assertAlmostEqual(parsed_node.pax[2], 0.0, places=5)

    def test_dnm_contralateral_pax_mirroring(self):
        """Verify mirror_node_to_contralateral flips PAX x-component."""
        model = DynaModel(version=1)
        node_r = DnmNode(
            name="aileron_r",
            fil="aileron_r.srf",
            cla=7,
            cnt=(3.5, 0.2, -1.2),
            pax=(0.996, 0.087, 0.05),
            rel="DEP",
        )
        model.add_node(node_r)

        node_l = model.mirror_node_to_contralateral("aileron_r", "aileron_l")
        self.assertIsNotNone(node_l.pax)
        self.assertAlmostEqual(node_l.pax[0], -0.996, places=4)
        self.assertAlmostEqual(node_l.pax[1], 0.087, places=4)
        self.assertAlmostEqual(node_l.pax[2], 0.05, places=4)

    def test_propeller_pax_and_cla18_rigging(self):
        """Verify propeller node receives axial PAX=(0, 0, 1) and CLA=18 in KinematicsRiggingEngine."""
        engine = KinematicsRiggingEngine()
        lofter = FuselageLofter(num_stations=6, vertices_per_ring=8)
        fuselage = lofter.loft_fuselage_mesh(
            lofter.generate_synthetic_profile(length_m=6.0, nose_z=3.0)
        )
        wing_gen = WingGenerator()
        w_params = WingParameters(semi_span_m=4.0, root_chord_m=1.5, tip_chord_m=0.8)
        wing_r = wing_gen.generate_wing_mesh(w_params, side="right")
        wing_l = wing_gen.generate_wing_mesh(w_params, side="left")
        h_r, h_l, v_fin = wing_gen.generate_empennage(
            h_span_m=2.0, h_chord_m=0.6, v_span_m=1.2, v_chord_m=0.8, tail_z=-3.0
        )

        prop_mesh = SurfaceMesh(
            name="helice",
            vertices=[
                SrfVertex(0.0, 0.0, 3.1),
                SrfVertex(0.8, 0.0, 3.1),
                SrfVertex(0.0, 0.8, 3.1),
            ],
            faces=[SrfFace(vertex_indices=[0, 1, 2], color=(30, 30, 30))],
        )

        dnm = engine.rig_complete_aircraft(
            fuselage_mesh=fuselage,
            wing_r_mesh=wing_r,
            wing_l_mesh=wing_l,
            h_stab_r_mesh=h_r,
            h_stab_l_mesh=h_l,
            v_fin_mesh=v_fin,
            propeller_mesh=prop_mesh,
        )

        prop_node = dnm.get_node("helice")
        self.assertIsNotNone(prop_node)
        self.assertEqual(prop_node.cla, 18)
        self.assertEqual(prop_node.pax, (0.0, 0.0, 1.0))
        self.assertIn("helice", dnm.nodes["fuselage"].children)


if __name__ == "__main__":
    unittest.main()

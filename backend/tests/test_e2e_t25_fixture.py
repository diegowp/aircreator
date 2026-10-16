"""End-to-end integration test validating the complete real T-25 Universal aircraft package."""

import unittest
from pathlib import Path

from app.parsers.dat import parse_dat_file, parse_lst_text
from app.parsers.dnm import parse_dnm_file
from app.parsers.srf import parse_srf_file


class TestT25FixtureE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs_dir = Path(__file__).resolve().parent.parent.parent / "docs"
        cls.t25_dir = cls.docs_dir / "t-25"

        cls.lst_file = cls.t25_dir / "t25universal.lst"
        cls.dat_file = cls.t25_dir / "t25universal.dat"
        cls.dnm_file = cls.t25_dir / "t25universal.dnm"
        cls.coll_srf_file = cls.t25_dir / "t25universal_coll.srf"

    def test_complete_t25_aircraft_package(self):
        # 1. Validate manifest
        self.assertTrue(self.lst_file.exists())
        lst_entries = parse_lst_text(self.lst_file.read_text(encoding="utf-8"))
        self.assertEqual(len(lst_entries), 3)

        # 2. Parse Flight Dynamics (.dat)
        self.assertTrue(self.dat_file.exists())
        dat_model = parse_dat_file(self.dat_file)
        self.assertEqual(dat_model.identify, "[PRIMU] T-25 AFA")
        self.assertEqual(dat_model.category, "TRAINER")
        self.assertAlmostEqual(dat_model.propellr_hp, 750.0)

        # Validate physics compliance
        issues = dat_model.validate_physics()
        self.assertEqual(len(issues), 0, f"Physics validation failed: {issues}")

        # 3. Parse Kinematic Scene Graph (.dnm)
        self.assertTrue(self.dnm_file.exists())
        dnm_model = parse_dnm_file(self.dnm_file)

        # Assert all primary aeronautical control components are present
        self.assertIn("0", dnm_model.nodes)  # Fuselage
        self.assertIn("1", dnm_model.nodes)  # Main Wing
        self.assertIn("8", dnm_model.nodes)  # Right Aileron
        self.assertIn("9", dnm_model.nodes)  # Left Aileron
        self.assertIn("7", dnm_model.nodes)  # Elevator
        self.assertIn("6", dnm_model.nodes)  # Rudder
        self.assertIn("2", dnm_model.nodes)  # Low-RPM Propeller
        self.assertIn("3", dnm_model.nodes)  # High-RPM Propeller Disk

        # Verify correct animation channels (CLA)
        self.assertEqual(dnm_model.nodes["8"].cla, 7)  # Aileron
        self.assertEqual(dnm_model.nodes["9"].cla, 7)  # Aileron
        self.assertEqual(dnm_model.nodes["7"].cla, 6)  # Elevator
        self.assertEqual(dnm_model.nodes["6"].cla, 8)  # Rudder
        self.assertEqual(dnm_model.nodes["2"].cla, 18)  # Static prop
        self.assertEqual(dnm_model.nodes["3"].cla, 20)  # Blurred prop disk

        # 4. Parse Collision Mesh (.srf)
        self.assertTrue(self.coll_srf_file.exists())
        coll_mesh = parse_srf_file(self.coll_srf_file)
        (min_x, min_y, min_z), (max_x, max_y, max_z) = coll_mesh.bounding_box()

        # 5. Cross-validate physical metrics between .dat and 3D geometry
        wingspan_mesh = max_x - min_x
        # T-25 physical wingspan is ~10-12m (with tip probes ~12.6m)
        self.assertGreater(wingspan_mesh, 9.0)
        self.assertLess(wingspan_mesh, 14.0)

        # Gear triangle width in .dat must be inside physical wingspan
        gear_width_dat = abs(dat_model.righgear.x - dat_model.leftgear.x)
        self.assertLess(gear_width_dat, wingspan_mesh)
        self.assertAlmostEqual(gear_width_dat, 4.0, places=1)

        # Collision sphere radius in .dat must encapsulate the aircraft center-to-tip distance
        half_span = wingspan_mesh / 2.0
        self.assertGreater(dat_model.htradius, half_span * 0.9)


if __name__ == "__main__":
    unittest.main()

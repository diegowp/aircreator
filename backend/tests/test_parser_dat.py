"""Unit tests for YSFlight flight dynamics (.dat) and manifest (.lst) parser."""

import unittest
from pathlib import Path

from app.parsers.dat import (
    DatFlightModel,
    Vector3Dat,
    parse_angle_deg,
    parse_dat_file,
    parse_dat_text,
    parse_distance,
    parse_lst_text,
    parse_speed_kmh,
    parse_weight_ton,
    write_lst_text,
)


class TestDatParser(unittest.TestCase):
    def test_unit_conversions(self):
        # Distance
        self.assertAlmostEqual(parse_distance("10m"), 10.0)
        self.assertAlmostEqual(parse_distance("10ft"), 3.048)
        self.assertAlmostEqual(parse_distance("10in"), 0.254)

        # Weight
        self.assertAlmostEqual(parse_weight_ton("1.5t"), 1.5)
        self.assertAlmostEqual(parse_weight_ton("1500kg"), 1.5)
        self.assertAlmostEqual(parse_weight_ton("2204.62lb"), 1.0, places=2)

        # Speed
        self.assertAlmostEqual(parse_speed_kmh("100km/h"), 100.0)
        self.assertAlmostEqual(parse_speed_kmh("100kt"), 185.2)
        self.assertAlmostEqual(parse_speed_kmh("10m/s"), 36.0)

        # Angle
        self.assertAlmostEqual(parse_angle_deg("45deg"), 45.0)

    def test_dat_physics_validation(self):
        # Valid model
        valid_model = DatFlightModel(
            identify="Test Trainer",
            weighcln=1.0,
            weigfuel=0.3,
            weigload=0.2,
            wingarea=14.0,
            critaoap=15.0,
            critaoam=-12.0,
            manespd1_kmh=90.0,
            manespd2_kmh=120.0,
            critsped_kmh=250.0,
            maxspeed_kmh=300.0,
            htradius=5.0,
            leftgear=Vector3Dat(-1.2, -1.2, 0.0),
            righgear=Vector3Dat(1.2, -1.2, 0.0),
            whelgear=Vector3Dat(0.0, -1.1, 1.8),
        )
        issues = valid_model.validate_physics()
        self.assertEqual(len(issues), 0)

        # Invalid model: negative weight, inverted stall angles, gear error
        invalid_model = DatFlightModel(
            weighcln=-1.0,
            critaoap=-10.0,
            critaoam=15.0,
            leftgear=Vector3Dat(1.2, -1.2, 0.0),  # Wrong side!
            righgear=Vector3Dat(-1.2, -1.2, 0.0),
        )
        bad_issues = invalid_model.validate_physics()
        self.assertGreaterEqual(len(bad_issues), 3)

    def test_dat_roundtrip(self):
        model1 = DatFlightModel(
            identify="Aero Fighter",
            category="FIGHTER",
            thrmilit=8500.0,
            thraftbn=12000.0,
            weighcln=6.5,
            weigfuel=2.5,
            wingarea=28.0,
        )
        text = model1.to_dat_text()
        model2 = parse_dat_text(text)

        self.assertEqual(model2.identify, "Aero Fighter")
        self.assertEqual(model2.category, "FIGHTER")
        self.assertAlmostEqual(model2.weighcln, 6.5)
        self.assertAlmostEqual(model2.thrmilit, 8500.0)
        self.assertAlmostEqual(model2.thraftbn, 12000.0)

    def test_lst_manifest(self):
        manifest_text = write_lst_text(
            dat_rel_path="user/t-25/t25.dat",
            dnm_rel_path="user/t-25/t25.dnm",
            coll_srf_rel_path="user/t-25/t25_coll.srf",
        )
        entries = parse_lst_text(manifest_text)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0], "user/t-25/t25.dat")
        self.assertEqual(entries[1], "user/t-25/t25.dnm")
        self.assertEqual(entries[2], "user/t-25/t25_coll.srf")

    def test_parse_real_t25_dat_and_lst(self):
        docs_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "t-25"
        dat_path = docs_dir / "t25universal.dat"
        lst_path = docs_dir / "t25universal.lst"

        if not dat_path.exists() or not lst_path.exists():
            self.skipTest("T-25 files not found")

        # Test .lst
        lst_entries = parse_lst_text(lst_path.read_text(encoding="utf-8"))
        self.assertEqual(len(lst_entries), 3)
        self.assertIn("user/primu/t-25/t25universal.dat", lst_entries[0])

        # Test .dat
        model = parse_dat_file(dat_path)
        self.assertEqual(model.identify, "[PRIMU] T-25 AFA")
        self.assertEqual(model.category, "TRAINER")
        self.assertAlmostEqual(model.propellr_hp, 750.0)
        self.assertAlmostEqual(model.weighcln, 1.81)
        self.assertAlmostEqual(model.weigfuel, 0.37)
        self.assertAlmostEqual(model.wingarea, 17.2)

        # Gears
        self.assertAlmostEqual(model.leftgear.x, -2.0)
        self.assertAlmostEqual(model.righgear.x, 2.0)
        self.assertAlmostEqual(model.whelgear.x, 0.0)

        # Physics check
        issues = model.validate_physics()
        self.assertEqual(len(issues), 0, f"Unexpected validation issues: {issues}")


if __name__ == "__main__":
    unittest.main()

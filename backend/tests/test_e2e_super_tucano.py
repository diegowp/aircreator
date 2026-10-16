"""Full End-to-End Validation Test: Reconstructing EMB-314 Super Tucano from blueprint.jpg."""

import io
import unittest
import zipfile
from pathlib import Path

from app.api.endpoints.export import ExportRequest, build_pipeline_package
from app.export import AircraftValidator
from app.parsers.dat import parse_dat_text, parse_lst_text
from app.parsers.dnm import parse_dnm_text
from app.parsers.srf import parse_srf_text


class TestE2ESuperTucano(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bp_path = Path(__file__).resolve().parent.parent.parent / "docs" / "blueprint.jpg"

    def test_complete_super_tucano_pipeline(self):
        if not self.bp_path.exists():
            self.skipTest("docs/blueprint.jpg not found")

        req = ExportRequest(
            aircraft_name="EMB-314 Super Tucano",
            blueprint_path=str(self.bp_path),
            preset_name="SUPER_TUCANO",
            wingspan_m=11.14,
            length_m=11.38,
            height_m=3.97,
        )

        # 1. Run complete reconstruction pipeline
        package = build_pipeline_package(req)

        self.assertEqual(package.aircraft_id, "emb_314_super_tucano")
        self.assertIsNotNone(package.dat_model)
        self.assertIsNotNone(package.dnm_model)
        self.assertIsNotNone(package.collision_mesh)
        self.assertIsNotNone(package.visual_mesh)

        # 2. Run Technical Specification Validator
        validator = AircraftValidator()
        report = validator.validate_package(package)

        self.assertTrue(report.is_valid, f"Validation failed with errors: {report.errors}")
        self.assertEqual(len(report.errors), 0)

        # 3. Test YSFlight ZIP Package Generation
        zip_bytes = package.generate_ysflight_zip()
        self.assertGreater(len(zip_bytes), 1000)

        # Inspect ZIP archive contents
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            file_list = zf.namelist()
            aid = package.aircraft_id

            expected_files = [
                f"{aid}/{aid}.lst",
                f"{aid}/{aid}.dat",
                f"{aid}/{aid}.dnm",
                f"{aid}/{aid}_coll.srf",
                f"{aid}/aircraft_lst_snippet.txt",
                f"{aid}/README.txt",
            ]
            for ef in expected_files:
                self.assertIn(ef, file_list)

            # Verify files inside ZIP are syntactically valid
            lst_content = zf.read(f"{aid}/{aid}.lst").decode("utf-8")
            entries = parse_lst_text(lst_content)
            self.assertEqual(len(entries), 3)

            dat_content = zf.read(f"{aid}/{aid}.dat").decode("utf-8")
            reloaded_dat = parse_dat_text(dat_content)
            self.assertEqual(reloaded_dat.identify, "EMB-314 Super Tucano")

            dnm_content = zf.read(f"{aid}/{aid}.dnm").decode("utf-8")
            reloaded_dnm = parse_dnm_text(dnm_content)
            self.assertIn("fuselage", reloaded_dnm.nodes)
            self.assertIn("aileron_d", reloaded_dnm.nodes)

            coll_content = zf.read(f"{aid}/{aid}_coll.srf").decode("utf-8")
            reloaded_coll = parse_srf_text(coll_content)
            self.assertGreater(len(reloaded_coll.vertices), 20)

        # 4. Test Universal OBJ + MTL Export
        obj_text, mtl_text = package.generate_obj_with_mtl()
        self.assertIn("o emb_314_super_tucano", obj_text)
        self.assertIn("mtllib emb_314_super_tucano.mtl", obj_text)
        self.assertIn("newmtl mat_", mtl_text)


if __name__ == "__main__":
    unittest.main()

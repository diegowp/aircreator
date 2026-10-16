"""Integration tests for dynamic reconstruction endpoints."""

import io
import unittest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


class TestDynamicReconstructionEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_generate_aircraft_endpoint_default(self):
        response = self.client.post(
            "/api/v1/reconstruction/generate-aircraft",
            json={
                "wingspan_m": 12.0,
                "length_m": 10.5,
                "height_m": 3.8,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("component_meshes", data)
        self.assertIn("fuselagem", data["component_meshes"])
        self.assertIn("wing_r", data["component_meshes"])
        self.assertIn("wing_l", data["component_meshes"])
        self.assertIn("metrics", data)
        self.assertGreater(data["metrics"]["num_vertices"], 100)
        self.assertGreater(data["metrics"]["num_faces"], 100)
        self.assertIn("spec", data)

    def test_upload_views_endpoint_separate_images(self):
        # Create minimal 100x100 PNG images
        def make_dummy_png():
            img = Image.new("RGB", (100, 100), color=(255, 255, 255))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return buf.getvalue()

        top_bytes = make_dummy_png()
        side_bytes = make_dummy_png()
        front_bytes = make_dummy_png()

        files = {
            "top_file": ("test_top.png", top_bytes, "image/png"),
            "side_file": ("test_side.png", side_bytes, "image/png"),
            "front_file": ("test_front.png", front_bytes, "image/png"),
        }
        data = {
            "aircraft_name": "Test Experimental Jet",
            "wingspan_m": "14.5",
            "length_m": "16.0",
            "height_m": "4.8",
        }

        response = self.client.post(
            "/api/v1/reconstruction/upload-views",
            files=files,
            data=data,
        )
        self.assertEqual(response.status_code, 200)
        res = response.json()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["aircraft_name"], "Test Experimental Jet")
        self.assertIn("component_meshes", res)
        self.assertIn("view_urls", res)
        self.assertIn("top", res["view_urls"])
        self.assertTrue(res["view_urls"]["top"].startswith("data:image/png;base64,"))
        self.assertIn("full_srf", res)
        self.assertIn("spec", res)

    def test_boeing_737_airliner_reconstruction(self):
        """Test commercial twin-turbofan airliner reconstruction (Boeing 737 MAX 8 style)."""
        response = self.client.post(
            "/api/v1/reconstruction/generate-aircraft",
            json={
                "blueprint_path": "docs/blueprint.jpg",
                "wingspan_m": 35.92,
                "length_m": 39.52,
                "height_m": 12.3,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        comps = data["component_meshes"]

        # 1. Underwing Turbofan Pods
        self.assertIn("engine_r", comps, "Should generate starboard turbofan pod")
        self.assertIn("engine_l", comps, "Should generate port turbofan pod")
        self.assertGreater(len(comps["engine_r"]["vertices"]), 80)
        self.assertGreater(len(comps["engine_l"]["vertices"]), 80)

        # 2. Split Scimitar Winglets
        self.assertIn("winglet_r", comps, "Should generate starboard winglet")
        self.assertIn("winglet_l", comps, "Should generate port winglet")

        # 3. Dorsal Fin Fillet
        self.assertIn("dorsal_fin", comps, "Should generate vertical fin dorsal fillet")

        # 4. Fuselage dimensions & stations
        spec = data["spec"]
        self.assertEqual(spec["aircraft_type"], "airliner")
        self.assertEqual(spec["propulsion"]["type"], "jet_pod_underwing")
        self.assertAlmostEqual(spec["wings"]["sweep_leading_edge_deg"], 25.0, delta=1.0)
        self.assertTrue(spec["wings"]["has_winglets"])
        self.assertFalse(spec["fuselage"]["cockpit"]["present"], "Airliners should not have bubble canopies")

        # 5. Clean, uncorrupted wing meshes (water-tight, no face loss)
        self.assertGreater(len(comps["wing_r"]["faces"]), 20)
        self.assertGreater(len(comps["wing_l"]["faces"]), 20)
        self.assertGreater(len(comps["aileron_d"]["faces"]), 2)
        self.assertGreater(len(comps["aileron_lef"]["faces"]), 2)

        # 6. Symmetrical Horizontal Stabilizers & Elevators (Port & Starboard)
        elev_1_xs = [v[0] for v in comps["elevator_1"]["vertices"]]
        self.assertLess(min(elev_1_xs), -4.0, "Fixed stabilizer must cover port side")
        self.assertGreater(max(elev_1_xs), 4.0, "Fixed stabilizer must cover starboard side")

        elev_xs = [v[0] for v in comps["elevator"]["vertices"]]
        self.assertLess(min(elev_xs), -4.0, "Movable elevator must cover port side")
        self.assertGreater(max(elev_xs), 4.0, "Movable elevator must cover starboard side")


if __name__ == "__main__":
    unittest.main()

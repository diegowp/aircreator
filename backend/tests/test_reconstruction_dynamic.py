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


if __name__ == "__main__":
    unittest.main()

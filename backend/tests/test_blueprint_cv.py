"""Unit tests for blueprint computer vision decomposition, axis detection, and calibration."""

import unittest
from pathlib import Path

from app.cv import (
    AircraftDimensions,
    AxisDetector,
    BlueprintCalibrator,
    BlueprintProcessor,
)


class TestBlueprintCV(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blueprint_path = Path(__file__).resolve().parent.parent.parent / "docs" / "blueprint.jpg"

    def test_blueprint_decomposition_on_real_image(self):
        if not self.blueprint_path.exists():
            self.skipTest("blueprint.jpg not found in docs/")

        processor = BlueprintProcessor()
        result = processor.decompose_file(self.blueprint_path)

        self.assertEqual(result.original_shape, (600, 800))

        # Check all 3 views are extracted
        self.assertIsNotNone(result.top_view)
        self.assertIsNotNone(result.front_view)
        self.assertIsNotNone(result.side_view)

        # Check bounding box sanity
        # Top view (left side)
        self.assertLess(result.top_view.bbox.x, 50)
        self.assertGreater(result.top_view.bbox.width, 400)
        self.assertGreater(result.top_view.bbox.height, 400)

        # Front view (top right)
        self.assertGreater(result.front_view.bbox.x, 250)
        self.assertLess(result.front_view.bbox.y, 50)
        self.assertGreater(result.front_view.bbox.width, 400)

        # Side view (bottom right)
        self.assertGreater(result.side_view.bbox.x, 250)
        self.assertGreater(result.side_view.bbox.y, 350)
        self.assertGreater(result.side_view.bbox.width, 450)

    def test_axis_and_dimension_detection(self):
        if not self.blueprint_path.exists():
            self.skipTest("blueprint.jpg not found in docs/")

        processor = BlueprintProcessor()
        decomp = processor.decompose_file(self.blueprint_path)

        detector = AxisDetector()
        axes = detector.analyze_all(decomp.top_view, decomp.front_view, decomp.side_view)

        # In Super Tucano blueprint.jpg, wingspan in top view is 486px, front is 486px!
        self.assertAlmostEqual(axes.wingspan_px, 486.0, delta=10.0)

        # Length in side view is ~503px, top view is ~514px
        self.assertAlmostEqual(axes.length_px, 508.0, delta=15.0)

        # Check symmetry axes exist
        self.assertIsNotNone(axes.top)
        self.assertGreater(axes.top.centerline_px, 200.0)
        self.assertIsNotNone(axes.front)
        self.assertGreater(axes.front.centerline_px, 200.0)

    def test_metric_calibration(self):
        if not self.blueprint_path.exists():
            self.skipTest("blueprint.jpg not found in docs/")

        processor = BlueprintProcessor()
        decomp = processor.decompose_file(self.blueprint_path)
        detector = AxisDetector()
        axes = detector.analyze_all(decomp.top_view, decomp.front_view, decomp.side_view)

        calibrator = BlueprintCalibrator()
        # Super Tucano real physical dimensions: wingspan 11.14m, length 11.38m
        specs = AircraftDimensions(wingspan_m=11.14, length_m=11.38, height_m=3.97)

        calib = calibrator.calibrate(axes, specs)

        # ~486 px / 11.14 m ~= 43.6 pixels/meter
        self.assertAlmostEqual(calib.pixels_per_meter, 43.6, delta=2.0)

        # Test coordinate mapping: center of symmetry should yield X ~= 0.0m
        z0, y0 = calib.origin_top_px
        x_world, z_world = calib.top_pixel_to_world(z0, y0)
        self.assertAlmostEqual(x_world, 0.0, places=2)
        self.assertAlmostEqual(z_world, 0.0, places=2)


if __name__ == "__main__":
    unittest.main()

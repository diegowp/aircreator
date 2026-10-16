"""Unit tests for YSFlight .srf parser and serializer."""

import unittest
from pathlib import Path

from app.parsers.srf import (
    SrfFace,
    SrfVertex,
    SurfaceMesh,
    color15_to_rgb,
    parse_srf_file,
    parse_srf_text,
    rgb_to_color15,
)


class TestSrfParser(unittest.TestCase):
    def test_color_15bit_conversion(self):
        # Pure White
        white_15 = rgb_to_color15(255, 255, 255)
        self.assertEqual(white_15, 0x7FFF)
        r, g, b = color15_to_rgb(white_15)
        self.assertEqual((r, g, b), (255, 255, 255))

        # Pure Black
        black_15 = rgb_to_color15(0, 0, 0)
        self.assertEqual(black_15, 0)
        r, g, b = color15_to_rgb(black_15)
        self.assertEqual((r, g, b), (0, 0, 0))

        # Pure Red
        red_15 = rgb_to_color15(255, 0, 0)
        r, g, b = color15_to_rgb(red_15)
        self.assertEqual((r, g, b), (255, 0, 0))

    def test_parse_simple_srf(self):
        srf_text = """
SURF
V 0.0 0.0 0.0 R
V 1.0 0.0 0.0 R
V 1.0 1.0 0.0
V 0.0 1.0 0.0
F
C 255 128 64
N 0.5 0.5 0.0 0.0 0.0 1.0
V 0 1 2 3
E
F
C 100 100 100
V 0 1 2
B
E
E
ZA 0 150
"""
        mesh = parse_srf_text(srf_text, name="quad_mesh")

        self.assertEqual(len(mesh.vertices), 4)
        self.assertTrue(mesh.vertices[0].round_shading)
        self.assertTrue(mesh.vertices[1].round_shading)
        self.assertFalse(mesh.vertices[2].round_shading)

        self.assertEqual(len(mesh.faces), 2)
        # Face 0
        self.assertEqual(mesh.faces[0].color, (255, 128, 64))
        self.assertEqual(mesh.faces[0].vertex_indices, [0, 1, 2, 3])
        self.assertEqual(mesh.faces[0].alpha, 150)
        self.assertFalse(mesh.faces[0].bright)

        # Face 1
        self.assertEqual(mesh.faces[1].color, (100, 100, 100))
        self.assertEqual(mesh.faces[1].vertex_indices, [0, 1, 2])
        self.assertTrue(mesh.faces[1].bright)
        self.assertEqual(mesh.faces[1].alpha, 255)

    def test_bidirectional_roundtrip(self):
        mesh1 = SurfaceMesh(
            name="triangle",
            vertices=[
                SrfVertex(0.0, 0.0, 0.0, round_shading=True),
                SrfVertex(2.0, 0.0, 0.0, round_shading=True),
                SrfVertex(1.0, 2.0, 0.0, round_shading=False),
            ],
            faces=[
                SrfFace(
                    vertex_indices=[0, 1, 2],
                    color=(200, 50, 50),
                    bright=True,
                    alpha=180,
                )
            ],
        )

        srf_string = mesh1.to_srf(short_syntax=True)
        mesh2 = parse_srf_text(srf_string, name="reloaded")

        self.assertEqual(len(mesh2.vertices), 3)
        self.assertEqual(len(mesh2.faces), 1)
        self.assertEqual(mesh2.faces[0].color, (200, 50, 50))
        self.assertEqual(mesh2.faces[0].alpha, 180)
        self.assertTrue(mesh2.faces[0].bright)
        self.assertEqual(mesh2.faces[0].vertex_indices, [0, 1, 2])

    def test_mirror_x(self):
        mesh = SurfaceMesh(
            name="left_wing",
            vertices=[
                SrfVertex(-1.0, 0.0, 0.0),
                SrfVertex(-4.0, 0.0, 0.0),
                SrfVertex(-4.0, 0.0, -2.0),
            ],
            faces=[
                SrfFace(vertex_indices=[0, 1, 2], color=(255, 255, 0)),
            ],
        )
        mesh.compute_missing_normals()
        mirrored = mesh.mirror_x("right_wing")

        self.assertEqual(mirrored.name, "right_wing")
        # Inverted X coordinates
        self.assertAlmostEqual(mirrored.vertices[0].x, 1.0)
        self.assertAlmostEqual(mirrored.vertices[1].x, 4.0)
        self.assertAlmostEqual(mirrored.vertices[2].x, 4.0)

        # Reversed winding order to preserve outward normals
        self.assertEqual(mirrored.faces[0].vertex_indices, [2, 1, 0])

    def test_parse_real_t25_collision_file(self):
        srf_path = Path(__file__).resolve().parent.parent.parent / "docs" / "t-25" / "t25universal_coll.srf"
        if not srf_path.exists():
            self.skipTest("t25universal_coll.srf not found in docs/t-25")

        mesh = parse_srf_file(srf_path)
        self.assertGreater(len(mesh.vertices), 4000)
        self.assertGreater(len(mesh.faces), 3000)

        # Verify transparent faces (canopy in T-25 has ZA transparent entries)
        transparent_faces = [f for f in mesh.faces if f.alpha < 255]
        self.assertGreater(len(transparent_faces), 0)

        # Check bounding box
        (min_x, min_y, min_z), (max_x, max_y, max_z) = mesh.bounding_box()
        # Wingspan check: T-25 wingspan is ~10m (X ranges from ~ -5 to +5)
        self.assertLess(min_x, -4.0)
        self.assertGreater(max_x, 4.0)
        # Length check: T-25 length is ~8.6m
        self.assertLess(min_z, -3.5)
        self.assertGreater(max_z, 3.0)


if __name__ == "__main__":
    unittest.main()

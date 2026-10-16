"""Unit tests for YSFlight DynaModel (.dnm) scene graph and kinematics parser."""

import unittest
from pathlib import Path

from app.parsers.dnm import (
    DnmNode,
    DnmPos,
    DnmState,
    DynaModel,
    parse_dnm_file,
    parse_dnm_text,
)
from app.parsers.srf import SrfFace, SrfVertex, SurfaceMesh


class TestDnmParser(unittest.TestCase):
    def test_parse_synthetic_dnm(self):
        dnm_text = """
DYNAMODEL
DNMVER 1

PCK test_mesh.srf 8
SURF
V 0.0 0.0 0.0
V 1.0 0.0 0.0
V 0.0 1.0 0.0
F
C 255 0 0
V 0 1 2
E
E

SRF "fuselage"
FIL test_mesh.srf
CLA 0
NST 0
POS 0.0000 0.0000 0.0000 0 0 0 1
CNT 0.0000 0.0000 0.0000
REL DEP
NCH 1
CLD "aileron_l"
END

SRF "aileron_l"
FIL test_mesh.srf
CLA 7
NST 2
STA 0.0 0.0 0.0 0 2730 0 1
STA 0.0 0.0 0.0 0 -2730 0 1
POS -3.0000 0.2000 -1.0000 0 0 0 1
CNT -3.0000 0.2000 -1.0000
REL DEP
NCH 0
END

END
"""
        model = parse_dnm_text(dnm_text)

        self.assertEqual(model.version, 1)
        self.assertIn("test_mesh.srf", model.pck_meshes)
        self.assertEqual(len(model.pck_meshes["test_mesh.srf"].vertices), 3)

        self.assertIn("fuselage", model.nodes)
        self.assertIn("aileron_l", model.nodes)

        fuselage = model.nodes["fuselage"]
        self.assertEqual(fuselage.cla, 0)
        self.assertEqual(fuselage.children, ["aileron_l"])

        aileron = model.nodes["aileron_l"]
        self.assertEqual(aileron.cla, 7)  # CLA 7: Aileron
        self.assertEqual(len(aileron.states), 2)
        self.assertEqual(aileron.states[0].dp, 2730)
        self.assertEqual(aileron.cnt, (-3.0, 0.2, -1.0))

    def test_dnm_roundtrip(self):
        model1 = DynaModel(version=1)
        mesh = SurfaceMesh(
            name="box",
            vertices=[SrfVertex(0, 0, 0), SrfVertex(1, 0, 0), SrfVertex(1, 1, 0)],
            faces=[SrfFace(vertex_indices=[0, 1, 2], color=(0, 255, 0))],
        )
        model1.embed_mesh("box.srf", mesh)

        node = DnmNode(
            name="main_gear",
            fil="box.srf",
            cla=0,
            pos=DnmPos(x=-1.5, y=-1.0, z=0.5, h=0, p=0, b=0, vis=1),
            cnt=(-1.5, -0.2, 0.5),
            states=[
                DnmState(dx=0, dy=0, dz=0, dh=0, dp=0, db=0, vis=1),
                DnmState(dx=0.5, dy=0.8, dz=0, dh=0, dp=0, db=-16384, vis=0),
            ],
        )
        model1.add_node(node)

        text = model1.to_dnm_text()
        model2 = parse_dnm_text(text)

        self.assertIn("box.srf", model2.pck_meshes)
        self.assertIn("main_gear", model2.nodes)
        reloaded_node = model2.nodes["main_gear"]
        self.assertEqual(reloaded_node.cla, 0)
        self.assertEqual(len(reloaded_node.states), 2)
        self.assertEqual(reloaded_node.states[1].db, -16384)
        self.assertAlmostEqual(reloaded_node.pos.x, -1.5)

    def test_mirror_node_contralateral(self):
        model = DynaModel(version=1)
        left_node = DnmNode(
            name="aileron_left",
            fil="aileron_l.srf",
            cla=7,
            pos=DnmPos(x=-4.0, y=0.5, z=-1.0, h=500, p=0, b=200, vis=1),
            cnt=(-4.0, 0.5, -1.0),
            states=[
                DnmState(dx=0, dy=0, dz=0, dh=0, dp=2000, db=1000, vis=1),
            ],
        )
        model.add_node(left_node)

        right_node = model.mirror_node_to_contralateral(
            source_node_name="aileron_left",
            target_node_name="aileron_right",
            target_fil_name="aileron_r.srf",
        )
        model.add_node(right_node)

        # Mirrored position: X inverted, heading and bank flipped
        self.assertAlmostEqual(right_node.pos.x, 4.0)
        self.assertEqual(right_node.pos.h, -500)
        self.assertEqual(right_node.pos.b, -200)

        # Mirrored pivot CNT: X inverted
        self.assertAlmostEqual(right_node.cnt[0], 4.0)
        self.assertAlmostEqual(right_node.cnt[1], 0.5)

        # Mirrored state deltas
        self.assertEqual(right_node.states[0].dp, 2000)
        self.assertEqual(right_node.states[0].db, -1000)

    def test_parse_real_t25_dnm(self):
        dnm_path = Path(__file__).resolve().parent.parent.parent / "docs" / "t-25" / "t25universal.dnm"
        if not dnm_path.exists():
            self.skipTest("t25universal.dnm not found in docs/t-25")

        model = parse_dnm_file(dnm_path)

        # Check total nodes (25 nodes in T-25)
        self.assertGreaterEqual(len(model.nodes), 20)

        # Check specific key nodes
        self.assertIn("0", model.nodes)  # Fuselage
        self.assertEqual(model.nodes["0"].fil, "fuselagem.srf")

        self.assertIn("8", model.nodes)  # Aileron right
        self.assertEqual(model.nodes["8"].cla, 7)  # CLA 7

        self.assertIn("9", model.nodes)  # Aileron left
        self.assertEqual(model.nodes["9"].cla, 7)

        self.assertIn("7", model.nodes)  # Elevator
        self.assertEqual(model.nodes["7"].cla, 6)  # CLA 6

        self.assertIn("6", model.nodes)  # Rudder
        self.assertEqual(model.nodes["6"].cla, 8)  # CLA 8

        # Check embedded PCK meshes
        self.assertIn("cockpit_.srf", model.pck_meshes)
        cockpit_mesh = model.pck_meshes["cockpit_.srf"]
        self.assertGreater(len(cockpit_mesh.vertices), 100)


if __name__ == "__main__":
    unittest.main()

"""Kinematics Auto-Rigging Engine and DynaModel Scene Graph Builder.

Automates the assembly of an articulated YSFlight DynaModel (.dnm):
- Computes hinge axis pivots (CNT vectors).
- Assigns simulation animation classes (CLA 0..31).
- Generates 16-bit angular states (STA) for pitch, roll, yaw, flaps, gears.
- Mirrors kinematic contralateral nodes (left/right ailerons and main landing gears).
- Packs all component meshes into single-file PCK blocks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.geometry.part_slicer import PartSlicer
from app.parsers.dnm import DnmNode, DnmPos, DnmState, DynaModel
from app.parsers.srf import SurfaceMesh


def degrees_to_angle16(deg: float) -> int:
    """Convert degrees to YSFlight 16-bit integer angle (-32768..32767)."""
    val = round((deg * 65536.0) / 360.0)
    # Wrap to signed 16-bit range
    if val > 32767:
        val -= 65536
    elif val < -32768:
        val += 65536
    return int(val)


@dataclass
class AircraftRiggingComponents:
    fuselage: SurfaceMesh
    wing_right: SurfaceMesh
    wing_left: SurfaceMesh
    elevator_fixed_r: SurfaceMesh
    elevator_fixed_l: SurfaceMesh
    rudder_fixed: SurfaceMesh
    aileron_right: SurfaceMesh | None = None
    aileron_left: SurfaceMesh | None = None
    elevator_movable: SurfaceMesh | None = None
    rudder_movable: SurfaceMesh | None = None
    propeller_static: SurfaceMesh | None = None
    propeller_blurred: SurfaceMesh | None = None


class KinematicsRiggingEngine:
    def __init__(self):
        self.slicer = PartSlicer()
        self.last_rigged_components: dict[str, dict] = {}

    def rig_complete_aircraft(
        self,
        fuselage_mesh: SurfaceMesh,
        wing_r_mesh: SurfaceMesh,
        wing_l_mesh: SurfaceMesh,
        h_stab_r_mesh: SurfaceMesh,
        h_stab_l_mesh: SurfaceMesh,
        v_fin_mesh: SurfaceMesh,
        propeller_mesh: SurfaceMesh | None = None,
        canopy_mesh: SurfaceMesh | None = None,
        aileron_deflection_deg: float = 15.0,
        elevator_deflection_deg: float = 18.0,
        rudder_deflection_deg: float = 25.0,
    ) -> DynaModel:
        """
        Slice control surfaces, compute hinge pivots, assign CLA channels,
        and build a fully articulated DynaModel with PCK packages.
        """
        model = DynaModel(version=1)

        # 1. Slice Ailerons from Wings
        sliced_wing_r = self.slicer.slice_trailing_edge_surface(
            wing_r_mesh,
            chord_cut_fraction=0.70,
            span_start_fraction=0.55,
            span_end_fraction=0.98,
            movable_name="aileron_d",
            fixed_name="wing_r_fixed",
            is_vertical=False,
        )

        sliced_wing_l = self.slicer.slice_trailing_edge_surface(
            wing_l_mesh,
            chord_cut_fraction=0.70,
            span_start_fraction=0.02,
            span_end_fraction=0.45,
            movable_name="aileron_lef",
            fixed_name="wing_l_fixed",
            is_vertical=False,
        )

        # 2. Slice Elevator from Horizontal Stabilizer Right
        sliced_h_stab = self.slicer.slice_trailing_edge_surface(
            h_stab_r_mesh,
            chord_cut_fraction=0.60,
            span_start_fraction=0.05,
            span_end_fraction=0.95,
            movable_name="elevator",
            fixed_name="elevator_1",
            is_vertical=False,
        )

        # 3. Slice Rudder from Vertical Fin
        sliced_v_fin = self.slicer.slice_trailing_edge_surface(
            v_fin_mesh,
            chord_cut_fraction=0.55,
            span_start_fraction=0.10,
            span_end_fraction=0.95,
            movable_name="rudder_2",
            fixed_name="rudder_1",
            is_vertical=True,
        )

        # 4. Embed all meshes as PCK blocks
        model.embed_mesh("fuselagem.srf", fuselage_mesh)
        model.embed_mesh("wing_r.srf", sliced_wing_r.fixed_mesh)
        model.embed_mesh("wing_l.srf", sliced_wing_l.fixed_mesh)
        model.embed_mesh("aileron_d.srf", sliced_wing_r.movable_mesh)
        model.embed_mesh("aileron_lef.srf", sliced_wing_l.movable_mesh)
        model.embed_mesh("elevator_1.srf", sliced_h_stab.fixed_mesh)
        model.embed_mesh("elevator.srf", sliced_h_stab.movable_mesh)
        model.embed_mesh("rudder_1.srf", sliced_v_fin.fixed_mesh)
        model.embed_mesh("rudder_2.srf", sliced_v_fin.movable_mesh)

        if canopy_mesh:
            model.embed_mesh("canopy.srf", canopy_mesh)

        if propeller_mesh:
            model.embed_mesh("helice.srf", propeller_mesh)

        # 5. Build Scene Graph Nodes

        # Root Node: Fuselage (SRF 0)
        fuselage_children = ["wing_r", "wing_l", "elevator_1", "rudder_1"]
        if canopy_mesh:
            fuselage_children.append("canopy")

        node_fuselage = DnmNode(
            name="fuselage",
            fil="fuselagem.srf",
            cla=0,
            pos=DnmPos(0, 0, 0, 0, 0, 0, 1),
            cnt=(0, 0, 0),
            rel="DEP",
            children=fuselage_children,
        )
        model.add_node(node_fuselage)

        if canopy_mesh:
            node_canopy = DnmNode(
                name="canopy",
                fil="canopy.srf",
                cla=0,
                pos=DnmPos(0, 0, 0, 0, 0, 0, 1),
                cnt=(0, 0, 0),
                rel="DEP",
            )
            model.add_node(node_canopy, parent_name="fuselage")

        # Fixed Wing Right (parent of aileron right)
        node_wing_r = DnmNode(
            name="wing_r",
            fil="wing_r.srf",
            cla=0,
            pos=DnmPos(0, 0, 0, 0, 0, 0, 1),
            cnt=(0, 0, 0),
            rel="DEP",
            children=["aileron_d"],
        )
        model.add_node(node_wing_r)

        # Fixed Wing Left (parent of aileron left)
        node_wing_l = DnmNode(
            name="wing_l",
            fil="wing_l.srf",
            cla=0,
            pos=DnmPos(0, 0, 0, 0, 0, 0, 1),
            cnt=(0, 0, 0),
            rel="DEP",
            children=["aileron_lef"],
        )
        model.add_node(node_wing_l)

        # Aileron Right: CLA 7 (3 States: Neutral, Roll Right, Roll Left)
        # Roll Right: TE UP (Pitch positive angle around CNT)
        aileron_angle16 = degrees_to_angle16(aileron_deflection_deg)
        cnt_aileron_r = sliced_wing_r.hinge_center
        node_aileron_r = DnmNode(
            name="aileron_d",
            fil="aileron_d.srf",
            cla=7,
            nst=3,
            cnt=cnt_aileron_r,
            rel="DEP",
            states=[
                DnmState(0, 0, 0, 0, 0, 0, 1),  # Neutral
                DnmState(0, 0, 0, 0, aileron_angle16, 0, 1),  # Right bank: TE UP
                DnmState(0, 0, 0, 0, -aileron_angle16, 0, 1),  # Left bank: TE DOWN
            ],
        )
        model.add_node(node_aileron_r)

        # Aileron Left: CLA 7 (Opposite deflections)
        cnt_aileron_l = sliced_wing_l.hinge_center
        node_aileron_l = DnmNode(
            name="aileron_lef",
            fil="aileron_lef.srf",
            cla=7,
            nst=3,
            cnt=cnt_aileron_l,
            rel="DEP",
            states=[
                DnmState(0, 0, 0, 0, 0, 0, 1),  # Neutral
                DnmState(0, 0, 0, 0, -aileron_angle16, 0, 1),  # Right bank: TE DOWN
                DnmState(0, 0, 0, 0, aileron_angle16, 0, 1),  # Left bank: TE UP
            ],
        )
        model.add_node(node_aileron_l)

        # Fixed Horizontal Stabilizer (parent of elevator)
        node_h_stab = DnmNode(
            name="elevator_1",
            fil="elevator_1.srf",
            cla=0,
            pos=DnmPos(0, 0, 0, 0, 0, 0, 1),
            cnt=(0, 0, 0),
            rel="DEP",
            children=["elevator"],
        )
        model.add_node(node_h_stab)

        # Movable Elevator: CLA 6 (Pitch: 3 States: Neutral, Pitch UP, Pitch DOWN)
        elev_angle16 = degrees_to_angle16(elevator_deflection_deg)
        cnt_elevator = sliced_h_stab.hinge_center
        node_elevator = DnmNode(
            name="elevator",
            fil="elevator.srf",
            cla=6,
            nst=3,
            cnt=cnt_elevator,
            rel="DEP",
            states=[
                DnmState(0, 0, 0, 0, 0, 0, 1),  # Neutral
                DnmState(0, 0, 0, 0, -elev_angle16, 0, 1),  # Pitch UP (Cabrar)
                DnmState(0, 0, 0, 0, elev_angle16, 0, 1),  # Pitch DOWN (Picar)
            ],
        )
        model.add_node(node_elevator)

        # Fixed Vertical Fin (parent of rudder)
        node_v_fin = DnmNode(
            name="rudder_1",
            fil="rudder_1.srf",
            cla=0,
            pos=DnmPos(0, 0, 0, 0, 0, 0, 1),
            cnt=(0, 0, 0),
            rel="DEP",
            children=["rudder_2"],
        )
        model.add_node(node_v_fin)

        # Movable Rudder: CLA 8 (Yaw: 3 States: Neutral, Yaw Right, Yaw Left)
        rudder_angle16 = degrees_to_angle16(rudder_deflection_deg)
        cnt_rudder = sliced_v_fin.hinge_center
        node_rudder = DnmNode(
            name="rudder_2",
            fil="rudder_2.srf",
            cla=8,
            nst=3,
            cnt=cnt_rudder,
            rel="DEP",
            states=[
                DnmState(0, 0, 0, 0, 0, 0, 1),  # Neutral
                DnmState(0, 0, 0, -rudder_angle16, 0, 0, 1),  # Yaw Right (Heading deflection)
                DnmState(0, 0, 0, rudder_angle16, 0, 0, 1),  # Yaw Left
            ],
        )
        model.add_node(node_rudder)

        # Record rigged components for API & WebGL rendering
        (min_x, min_y, min_z), (max_x, max_y, max_z) = fuselage_mesh.bounding_box()
        nose_spinner = (0.0, 0.0, max_z + 0.1)

        self.last_rigged_components = {
            "fuselagem": {
                "mesh": fuselage_mesh,
                "pivot": (0.0, 0.0, 0.0),
                "cla": 0,
            },
            "wing_r": {
                "mesh": sliced_wing_r.fixed_mesh,
                "pivot": (0.0, 0.0, 0.0),
                "cla": 0,
            },
            "wing_l": {
                "mesh": sliced_wing_l.fixed_mesh,
                "pivot": (0.0, 0.0, 0.0),
                "cla": 0,
            },
            "aileron_d": {
                "mesh": sliced_wing_r.movable_mesh,
                "pivot": cnt_aileron_r,
                "cla": 7,
            },
            "aileron_lef": {
                "mesh": sliced_wing_l.movable_mesh,
                "pivot": cnt_aileron_l,
                "cla": 7,
            },
            "elevator_1": {
                "mesh": sliced_h_stab.fixed_mesh,
                "pivot": (0.0, 0.0, 0.0),
                "cla": 0,
            },
            "elevator": {
                "mesh": sliced_h_stab.movable_mesh,
                "pivot": cnt_elevator,
                "cla": 6,
            },
            "rudder_1": {
                "mesh": sliced_v_fin.fixed_mesh,
                "pivot": (0.0, 0.0, 0.0),
                "cla": 0,
            },
            "rudder_2": {
                "mesh": sliced_v_fin.movable_mesh,
                "pivot": cnt_rudder,
                "cla": 8,
            },
        }

        if canopy_mesh:
            self.last_rigged_components["canopy"] = {
                "mesh": canopy_mesh,
                "pivot": (0.0, 0.0, 0.0),
                "cla": 0,
            }

        if propeller_mesh:
            self.last_rigged_components["helice"] = {
                "mesh": propeller_mesh,
                "pivot": nose_spinner,
                "cla": 18,
            }

        return model

    def get_component_meshes_dict(self) -> dict[str, dict]:
        """
        Export all rigged component meshes to JSON-serializable dictionaries
        with vertices, faces, colors, alphas, round_shading, pivot, and cla.
        """
        res: dict[str, dict] = {}
        for name, item in self.last_rigged_components.items():
            mesh_dict = item["mesh"].to_dict()
            mesh_dict["pivot"] = [float(p) for p in item["pivot"]]
            mesh_dict["cla"] = int(item["cla"])
            res[name] = mesh_dict
        return res

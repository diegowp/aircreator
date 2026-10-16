"""Parametric Wing, Stabilizer, and Control Surface Geometry Generator.

Constructs aerodynamic lifting surfaces:
- Semi-span extrusion from root to tip.
- NACA 4-digit airfoil cross-sections or parameterized foil loops.
- Chord taper (root chord -> tip chord).
- Quarter-chord sweep angle (from Top view).
- Dihedral angle (from Front view).
- Washout aerodynamic twist.
- Clean quad-strip skinning with Round Shading on leading edge.
- Wingtip and root capping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.parsers.srf import SrfFace, SrfVertex, SurfaceMesh


@dataclass
class WingParameters:
    name: str = "main_wing"
    semi_span_m: float = 5.57  # Half wingspan (meters)
    root_chord_m: float = 2.20
    tip_chord_m: float = 1.10
    sweep_deg: float = 4.5  # Leading edge / quarter chord sweep
    dihedral_deg: float = 5.0  # Wing dihedral angle
    incidence_deg: float = 1.5  # Angle of incidence
    washout_deg: float = -1.5  # Wingtip twist
    thickness_ratio: float = 0.13  # 13% thickness NACA foil
    root_x: float = 0.60  # Root offset from centerline (fuselage junction)
    root_y: float = -0.20  # Root vertical offset
    root_z: float = 0.80  # Root longitudinal offset
    num_span_stations: int = 8  # Subdivisions along span
    num_foil_points: int = 12  # Points around airfoil profile
    color: tuple[int, int, int] = (235, 190, 40)  # Golden yellow (like T-25 / Super Tucano demo)
    is_vertical: bool = False  # True for vertical stabilizer / rudder fin


class WingGenerator:
    def __init__(self):
        pass

    def generate_naca_airfoil_coords(
        self,
        chord: float,
        thickness_ratio: float,
        num_points: int = 12,
    ) -> list[tuple[float, float]]:
        """
        Generate (x_chord, y_thickness) normalized coordinates for a NACA 00xx symmetric airfoil.
        Returns coordinates ordered counter-clockwise starting at Trailing Edge -> Upper Surface ->
        Leading Edge -> Lower Surface -> Trailing Edge.
        """
        half_pts = max(4, num_points // 2)

        # Cosine spacing for higher density at leading edge
        beta = np.linspace(0, math.pi, half_pts)
        x_norm = (1.0 - np.cos(beta)) / 2.0  # 0 at LE, 1 at TE

        # NACA thickness distribution formula
        t = thickness_ratio
        yt = 5.0 * t * (
            0.2969 * np.sqrt(x_norm)
            - 0.1260 * x_norm
            - 0.3516 * (x_norm**2)
            + 0.2843 * (x_norm**3)
            - 0.1036 * (x_norm**4)  # Closed trailing edge
        )

        upper_pts: list[tuple[float, float]] = []
        lower_pts: list[tuple[float, float]] = []

        # From TE (x=1) to LE (x=0) for upper
        for i in reversed(range(half_pts)):
            xc = float(x_norm[i] * chord)
            yc = float(yt[i] * chord)
            upper_pts.append((xc, yc))

        # From LE (x=0) to TE (x=1) for lower (skip LE to avoid duplicate)
        for i in range(1, half_pts):
            xc = float(x_norm[i] * chord)
            yc = float(-yt[i] * chord)
            lower_pts.append((xc, yc))

        return upper_pts + lower_pts

    def generate_wing_mesh(
        self,
        params: WingParameters,
        side: str = "right",  # 'right' (+X), 'left' (-X), or 'vertical' (+Y)
    ) -> SurfaceMesh:
        """Generate polygonal surface mesh for a wing or stabilizer surface."""
        all_vertices: list[SrfVertex] = []
        faces: list[SrfFace] = []

        n_span = params.num_span_stations
        eta_coords = np.linspace(0.0, 1.0, n_span)  # Spanwise fraction 0.0 (root) to 1.0 (tip)

        sweep_rad = math.radians(params.sweep_deg)
        dihedral_rad = math.radians(params.dihedral_deg)

        span_rings_start: list[int] = []

        sign_x = -1.0 if side == "left" else 1.0

        for eta in eta_coords:
            span_pos = eta * params.semi_span_m
            chord = params.root_chord_m + eta * (params.tip_chord_m - params.root_chord_m)
            twist_deg = params.incidence_deg + eta * params.washout_deg
            twist_rad = math.radians(twist_deg)

            # Airfoil 2D profile coordinates (xc along chord, yc thickness)
            foil_2d = self.generate_naca_airfoil_coords(
                chord=chord,
                thickness_ratio=params.thickness_ratio,
                num_points=params.num_foil_points,
            )

            # Station 3D origin
            if not params.is_vertical:
                # Horizontal wing: span extends along X
                x_station = sign_x * (params.root_x + span_pos)
                y_station = params.root_y + span_pos * math.sin(dihedral_rad)
                # Sweep shifts chord backward (-Z)
                z_station = params.root_z - span_pos * math.sin(sweep_rad)
            else:
                # Vertical fin: span extends upward (+Y)
                x_station = 0.0
                y_station = params.root_y + span_pos
                z_station = params.root_z - span_pos * math.sin(sweep_rad)

            ring_start = len(all_vertices)
            span_rings_start.append(ring_start)

            # Transform 2D airfoil points into 3D world station ring
            for xc, yc in foil_2d:
                # In YSFlight: +Z is forward (towards nose), -Z is trailing edge
                # Airfoil xc=0 is Leading Edge, xc=chord is Trailing Edge
                # Apply pitch twist rotation
                dz_chord = -(xc * math.cos(twist_rad) - yc * math.sin(twist_rad))
                dy_thick = xc * math.sin(twist_rad) + yc * math.cos(twist_rad)

                # Leading edge vicinity gets Round Shading 'R'
                is_round = xc < chord * 0.35

                if not params.is_vertical:
                    vx = x_station
                    vy = y_station + dy_thick
                    vz = z_station + dz_chord
                else:
                    vx = x_station + dy_thick
                    vy = y_station
                    vz = z_station + dz_chord

                all_vertices.append(SrfVertex(x=vx, y=vy, z=vz, round_shading=is_round))

        m = len(foil_2d)

        # Skinning: Connect adjacent span stations with quad faces
        for i in range(n_span - 1):
            r_curr = span_rings_start[i]
            r_next = span_rings_start[i + 1]

            for j in range(m):
                j_next = (j + 1) % m

                v_curr_j = r_curr + j
                v_curr_next = r_curr + j_next
                v_next_next = r_next + j_next
                v_next_j = r_next + j

                # Counter-clockwise winding seen from outside
                if side == "right" or params.is_vertical:
                    face_indices = [v_curr_j, v_next_j, v_next_next, v_curr_next]
                else:
                    face_indices = [v_curr_j, v_curr_next, v_next_next, v_next_j]

                faces.append(SrfFace(vertex_indices=face_indices, color=params.color))

        # Root Cap (flat polygon closing the root junction)
        root_start = span_rings_start[0]
        root_indices = [root_start + j for j in range(m)]
        if side == "right":
            root_indices = list(reversed(root_indices))
        faces.append(SrfFace(vertex_indices=root_indices, color=params.color))

        # Tip Cap (flat polygon closing the wingtip)
        tip_start = span_rings_start[-1]
        tip_indices = [tip_start + j for j in range(m)]
        if side != "right" and not params.is_vertical:
            tip_indices = list(reversed(tip_indices))
        faces.append(SrfFace(vertex_indices=tip_indices, color=params.color))

        mesh = SurfaceMesh(name=f"{params.name}_{side}", vertices=all_vertices, faces=faces)
        mesh.compute_missing_normals()
        return mesh

    def generate_empennage(
        self,
        h_span_m: float = 3.80,
        h_chord_m: float = 1.00,
        v_span_m: float = 2.10,
        v_chord_m: float = 1.50,
        tail_z: float = -4.50,
        tail_y: float = 0.40,
        color: tuple[int, int, int] = (240, 240, 245),
    ) -> tuple[SurfaceMesh, SurfaceMesh, SurfaceMesh]:
        """
        Generate complete tail empennage:
        Returns: (horizontal_stabilizer_right, horizontal_stabilizer_left, vertical_fin).
        """
        # Horizontal Stabilizer Right
        h_params = WingParameters(
            name="elevator_1",
            semi_span_m=h_span_m / 2.0,
            root_chord_m=h_chord_m,
            tip_chord_m=h_chord_m * 0.65,
            sweep_deg=3.0,
            dihedral_deg=0.0,
            thickness_ratio=0.10,
            root_x=0.20,
            root_y=tail_y,
            root_z=tail_z,
            color=color,
        )
        h_stab_r = self.generate_wing_mesh(h_params, side="right")
        h_stab_l = self.generate_wing_mesh(h_params, side="left")

        # Vertical Stabilizer Fin
        v_params = WingParameters(
            name="rudder_1",
            semi_span_m=v_span_m,
            root_chord_m=v_chord_m,
            tip_chord_m=v_chord_m * 0.50,
            sweep_deg=22.0,
            dihedral_deg=0.0,
            thickness_ratio=0.10,
            root_x=0.0,
            root_y=tail_y + 0.10,
            root_z=tail_z + 0.50,
            color=color,
            is_vertical=True,
        )
        v_fin = self.generate_wing_mesh(v_params, side="center")

        return (h_stab_r, h_stab_l, v_fin)

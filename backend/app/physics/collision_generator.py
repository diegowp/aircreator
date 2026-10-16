"""Collision Mesh (_coll.srf) Generator.

Creates low-poly, convex physical collision geometry for real-time projectile
and terrain collision detection in YSFlight:
- Generates octagonal fuselage bounding volume.
- Generates simplified wing leading-edge / trailing-edge collision plates.
- Generates tail fin collision volume.
- Guarantees under 200 polygons total for maximum simulation physics performance.
"""

from __future__ import annotations

import math

from app.parsers.srf import SrfFace, SrfVertex, SurfaceMesh


class CollisionMeshGenerator:
    def __init__(self, color: tuple[int, int, int] = (255, 106, 0)):
        # Default collision orange color (identical to docs/t-25/t25universal_coll.srf)
        self.color = color

    def generate_collision_mesh(
        self,
        full_aircraft_mesh: SurfaceMesh,
        mesh_name: str = "aircraft_coll",
    ) -> SurfaceMesh:
        """
        Build an optimized, low-polygon collision hull from the visual aircraft model.
        """
        (min_x, min_y, min_z), (max_x, max_y, max_z) = full_aircraft_mesh.bounding_box()

        wingspan = max_x - min_x
        length = max_z - min_z
        height = max_y - min_y

        vertices: list[SrfVertex] = []
        faces: list[SrfFace] = []

        # 1. Fuselage Collision Octagonal Prism (5 stations along Z)
        num_stations = 5
        z_stations = [
            max_z,  # Nose tip
            max_z - length * 0.20,  # Front fuselage
            max_z - length * 0.50,  # Mid fuselage / wing root
            max_z - length * 0.80,  # Aft fuselage
            min_z,  # Tail tip
        ]

        # Station radii (rx, ry)
        fuselage_radii = [
            (0.15, 0.15),
            (0.60, 0.70),
            (0.70, 0.80),
            (0.40, 0.50),
            (0.10, 0.20),
        ]

        mid_y = min_y + height * 0.55

        station_starts: list[int] = []
        m = 8  # Octagon (8 vertices per ring)

        for i, z in enumerate(z_stations):
            rx, ry = fuselage_radii[i]
            station_starts.append(len(vertices))

            for j in range(m):
                theta = (2.0 * math.pi * j) / m
                vx = rx * math.sin(theta)
                vy = mid_y + ry * math.cos(theta)
                vz = z
                vertices.append(SrfVertex(x=vx, y=vy, z=vz, round_shading=True))

        # Fuselage skin faces
        for i in range(num_stations - 1):
            s_curr = station_starts[i]
            s_next = station_starts[i + 1]
            for j in range(m):
                j_next = (j + 1) % m
                faces.append(
                    SrfFace(
                        vertex_indices=[s_curr + j, s_next + j, s_next + j_next, s_curr + j_next],
                        color=self.color,
                    )
                )

        # 2. Right Wing Collision Box
        rw_start = len(vertices)
        wing_y = mid_y - 0.20
        wing_le_z = max_z - length * 0.35
        wing_te_z = max_z - length * 0.60
        wing_thick = 0.25

        # 8 vertices for right wing box
        rw_pts = [
            # Root: bottom LE, top LE, top TE, bottom TE
            (0.60, wing_y - wing_thick, wing_le_z),
            (0.60, wing_y + wing_thick, wing_le_z),
            (0.60, wing_y + wing_thick, wing_te_z),
            (0.60, wing_y - wing_thick, wing_te_z),
            # Tip: bottom LE, top LE, top TE, bottom TE
            (max_x, wing_y - wing_thick, wing_le_z - 0.5),
            (max_x, wing_y + wing_thick, wing_le_z - 0.5),
            (max_x, wing_y + wing_thick, wing_te_z - 0.5),
            (max_x, wing_y - wing_thick, wing_te_z - 0.5),
        ]
        for pt in rw_pts:
            vertices.append(SrfVertex(x=pt[0], y=pt[1], z=pt[2], round_shading=False))

        # Right wing box 6 quad faces
        faces.extend([
            SrfFace(vertex_indices=[rw_start + 0, rw_start + 1, rw_start + 5, rw_start + 4], color=self.color),
            SrfFace(vertex_indices=[rw_start + 1, rw_start + 2, rw_start + 6, rw_start + 5], color=self.color),
            SrfFace(vertex_indices=[rw_start + 2, rw_start + 3, rw_start + 7, rw_start + 6], color=self.color),
            SrfFace(vertex_indices=[rw_start + 3, rw_start + 0, rw_start + 4, rw_start + 7], color=self.color),
            SrfFace(vertex_indices=[rw_start + 4, rw_start + 5, rw_start + 6, rw_start + 7], color=self.color),
        ])

        # 3. Left Wing Collision Box (Mirrored)
        lw_start = len(vertices)
        for pt in rw_pts:
            vertices.append(SrfVertex(x=-pt[0], y=pt[1], z=pt[2], round_shading=False))

        faces.extend([
            SrfFace(vertex_indices=[lw_start + 1, lw_start + 0, lw_start + 4, lw_start + 5], color=self.color),
            SrfFace(vertex_indices=[lw_start + 2, lw_start + 1, lw_start + 5, lw_start + 6], color=self.color),
            SrfFace(vertex_indices=[lw_start + 3, lw_start + 2, lw_start + 6, lw_start + 7], color=self.color),
            SrfFace(vertex_indices=[lw_start + 0, lw_start + 3, lw_start + 7, lw_start + 4], color=self.color),
            SrfFace(vertex_indices=[lw_start + 5, lw_start + 4, lw_start + 7, lw_start + 6], color=self.color),
        ])

        # 4. Vertical Stabilizer Collision Box
        fin_start = len(vertices)
        fin_le_z = min_z + length * 0.25
        fin_te_z = min_z
        fin_thick = 0.15
        fin_pts = [
            # Base
            (-fin_thick, mid_y + 0.3, fin_le_z),
            (fin_thick, mid_y + 0.3, fin_le_z),
            (fin_thick, mid_y + 0.3, fin_te_z),
            (-fin_thick, mid_y + 0.3, fin_te_z),
            # Tip
            (-fin_thick, max_y, fin_le_z - 0.4),
            (fin_thick, max_y, fin_le_z - 0.4),
            (fin_thick, max_y, fin_te_z),
            (-fin_thick, max_y, fin_te_z),
        ]
        for pt in fin_pts:
            vertices.append(SrfVertex(x=pt[0], y=pt[1], z=pt[2], round_shading=False))

        faces.extend([
            SrfFace(vertex_indices=[fin_start + 0, fin_start + 1, fin_start + 5, fin_start + 4], color=self.color),
            SrfFace(vertex_indices=[fin_start + 1, fin_start + 2, fin_start + 6, fin_start + 5], color=self.color),
            SrfFace(vertex_indices=[fin_start + 2, fin_start + 3, fin_start + 7, fin_start + 6], color=self.color),
            SrfFace(vertex_indices=[fin_start + 3, fin_start + 0, fin_start + 4, fin_start + 7], color=self.color),
            SrfFace(vertex_indices=[fin_start + 4, fin_start + 5, fin_start + 6, fin_start + 7], color=self.color),
        ])

        coll_mesh = SurfaceMesh(name=mesh_name, vertices=vertices, faces=faces)
        coll_mesh.compute_missing_normals()
        return coll_mesh

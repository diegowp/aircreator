"""Fuselage Station Lofting and Quad-Ring Geometry Generator.

Reconstructs a clean, low-to-mid poly fuselage mesh from orthographic profile curves:
- Discretizes the aircraft longitudinal axis (Z) into N stations.
- Samples dorsal (top) and ventral (bottom) profile heights from Side view.
- Samples lateral half-widths from Top view.
- Generates M regular vertices per station ring (typically 12, 16, or 24 vertices).
- Assembles quad/triangle faces wound counter-clockwise with Round Shading ('R' flag).
- Closes nose and tail with aerodynamic apex caps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.parsers.srf import SrfFace, SrfVertex, SurfaceMesh


@dataclass
class FuselageStation:
    station_index: int
    z: float  # Longitudinal coordinate in meters
    y_center: float  # Vertical center of cross-section
    radius_x: float  # Lateral half-width in meters
    radius_y: float  # Vertical half-height in meters
    camber_bias: float = 0.0  # Optional offset for flatter belly / bulbous canopy
    vertices: list[SrfVertex] = field(default_factory=list)


@dataclass
class LoftingProfileData:
    z_coords: list[float]  # Stations along Z (from nose to tail, descending Z in YSFlight)
    y_dorsal: list[float]  # Top edge of fuselage at each Z
    y_ventral: list[float]  # Bottom edge of fuselage at each Z
    x_widths: list[float]  # Half-width (radius_x) at each Z


class FuselageLofter:
    def __init__(
        self,
        num_stations: int = 18,
        vertices_per_ring: int = 16,  # 16 vertices per cross-section (matches Metasequoia low/mid-poly)
        default_color: tuple[int, int, int] = (240, 240, 245),  # Aircraft white
    ):
        self.num_stations = max(6, num_stations)
        self.vertices_per_ring = max(8, vertices_per_ring)
        self.default_color = default_color

    def generate_synthetic_profile(
        self,
        length_m: float = 11.38,
        max_width_m: float = 1.30,
        max_height_m: float = 1.65,
        thrustline_y: float = 0.0,
        nose_z: float = 5.0,
    ) -> LoftingProfileData:
        """
        Generate an aerodynamic profile curve for an aircraft fuselage
        (useful for standalone generation or when contours are parameterized).
        """
        tail_z = nose_z - length_m
        z_coords = np.linspace(nose_z, tail_z, self.num_stations).tolist()

        y_dorsal: list[float] = []
        y_ventral: list[float] = []
        x_widths: list[float] = []

        for z in z_coords:
            # Normalized position from nose (0.0) to tail (1.0)
            u = (nose_z - z) / length_m

            # Elliptic-parabolic radius envelope
            if u < 0.35:
                # Nose section (smooth parabolic expansion)
                envelope = math.sin((u / 0.35) * (math.pi / 2))
            else:
                # Mid and aft fuselage tapering to tail cone
                envelope = math.cos(((u - 0.35) / 0.65) * (math.pi / 2.2))

            envelope = max(0.04, envelope)

            # Cockpit canopy hump between u=0.20 and u=0.55
            canopy_bump = 0.0
            if 0.18 < u < 0.58:
                canopy_bump = math.sin(((u - 0.18) / 0.40) * math.pi) * 0.35

            half_w = (max_width_m / 2.0) * envelope
            half_h = (max_height_m / 2.0) * envelope

            y_top = thrustline_y + half_h + canopy_bump
            y_bot = thrustline_y - half_h * 0.85

            z_coords_val = float(z)
            y_dorsal.append(float(y_top))
            y_ventral.append(float(y_bot))
            x_widths.append(float(half_w))

        return LoftingProfileData(
            z_coords=z_coords,
            y_dorsal=y_dorsal,
            y_ventral=y_ventral,
            x_widths=x_widths,
        )

    def extract_profile_from_masks(
        self,
        top_mask: np.ndarray,
        side_mask: np.ndarray,
        pixels_per_meter: float,
        origin_top: tuple[float, float],
        origin_side: tuple[float, float],
        num_stations: int | None = None,
    ) -> LoftingProfileData:
        """
        Sample dorsal/ventral profiles from Side view mask and widths from Top view mask.
        Converts extracted pixel boundaries into metric (meters) profile curves.
        """
        n_stations = num_stations or self.num_stations
        z0_top, x0_top = origin_top
        z0_side, y0_side = origin_side

        # Longitudinal bounds in side view
        horiz_side = np.sum(side_mask > 0, axis=0)
        non_zero_x = np.where(horiz_side > 0)[0]
        if len(non_zero_x) == 0:
            return self.generate_synthetic_profile()

        nose_px = float(non_zero_x[0])
        tail_px = float(non_zero_x[-1])

        # Station sampling points along pixel X (which represents Z axis)
        sample_x_coords = np.linspace(nose_px + 2, tail_px - 2, n_stations)

        z_coords: list[float] = []
        y_dorsal: list[float] = []
        y_ventral: list[float] = []
        x_widths: list[float] = []

        for px in sample_x_coords:
            ix = int(round(px))
            ix = max(0, min(side_mask.shape[1] - 1, ix))

            # Metric Z coordinate (+Z forward, so (z0 - px)/ppm)
            z_m = (z0_side - px) / pixels_per_meter
            z_coords.append(float(z_m))

            # Side view column slice for Y_dorsal and Y_ventral
            col_side = np.where(side_mask[:, ix] > 0)[0]
            if len(col_side) > 0:
                y_top_px = float(col_side[0])
                y_bot_px = float(col_side[-1])
                y_top_m = (y0_side - y_top_px) / pixels_per_meter
                y_bot_m = (y0_side - y_bot_px) / pixels_per_meter
            else:
                y_top_m = 0.5
                y_bot_m = -0.5

            y_dorsal.append(float(y_top_m))
            y_ventral.append(float(y_bot_m))

            # Top view column slice for lateral width
            # In horizontal top view, px aligns with longitudinal axis
            ix_top = int(round(px))
            if 0 <= ix_top < top_mask.shape[1]:
                col_top = np.where(top_mask[:, ix_top] > 0)[0]
                if len(col_top) > 0:
                    width_px = float(col_top[-1] - col_top[0])
                    # Half-width in meters (filter out wings if slice crosses root chord)
                    half_w_m = min(1.5, (width_px / 2.0) / pixels_per_meter)
                else:
                    half_w_m = 0.4
            else:
                half_w_m = 0.4

            x_widths.append(float(half_w_m))

        return LoftingProfileData(
            z_coords=z_coords,
            y_dorsal=y_dorsal,
            y_ventral=y_ventral,
            x_widths=x_widths,
        )

    def create_station_rings(self, profile: LoftingProfileData) -> list[FuselageStation]:
        """Compute 3D vertices for each cross-section station ring around the fuselage."""
        stations: list[FuselageStation] = []
        n = len(profile.z_coords)
        m = self.vertices_per_ring

        for i in range(n):
            z = profile.z_coords[i]
            y_top = profile.y_dorsal[i]
            y_bot = profile.y_ventral[i]
            rx = max(0.02, profile.x_widths[i])
            ry = max(0.02, (y_top - y_bot) / 2.0)
            yc = (y_top + y_bot) / 2.0

            station = FuselageStation(
                station_index=i,
                z=z,
                y_center=yc,
                radius_x=rx,
                radius_y=ry,
            )

            # Generate M vertices around the ring
            # Angle 0 starts at Top (Dorsal: X=0, Y=max), going clockwise
            # YSFlight left-handed: +X right, +Y up, +Z front
            for j in range(m):
                theta = (2.0 * math.pi * j) / m
                # X = radius_x * sin(theta) (positive for starboard, negative for port)
                # Y = y_center + radius_y * cos(theta)
                vx = rx * math.sin(theta)
                vy = yc + ry * math.cos(theta)
                vz = z

                # Vertices on curved fuselage body have Round Shading ('R' flag)
                v = SrfVertex(x=vx, y=vy, z=vz, round_shading=True)
                station.vertices.append(v)

            stations.append(station)

        return stations

    def loft_fuselage_mesh(
        self,
        profile: LoftingProfileData,
        mesh_name: str = "fuselage",
    ) -> SurfaceMesh:
        """
        Build complete polygonal SurfaceMesh connecting all stations.
        Generates quad faces wound counter-clockwise and caps nose and tail.
        """
        stations = self.create_station_rings(profile)
        all_vertices: list[SrfVertex] = []
        faces: list[SrfFace] = []

        m = self.vertices_per_ring
        n = len(stations)

        # 1. Add all station vertices first
        station_start_indices: list[int] = []
        for station in stations:
            start_idx = len(all_vertices)
            station_start_indices.append(start_idx)
            all_vertices.extend(station.vertices)

        # 2. Aerodynamic Ellipsoidal Radome Nose (Multi-Ring Quad Dome)
        r0_x = max(0.05, stations[0].radius_x)
        r0_y = max(0.05, stations[0].radius_y)
        # Maintain circular or near-circular cross-section to eliminate front-view egg distortion
        r0_y_radome = min(r0_y, r0_x * 1.05)
        y0_c = stations[0].y_center
        z0 = stations[0].z
        l_dome = r0_x * 0.65

        k_dome = 3
        dome_ring_starts: list[int] = []
        for k in range(1, k_dome + 1):
            u = k / (k_dome + 0.35)
            phi = u * (math.pi / 2.0)
            r_scale = math.cos(phi)
            z_k = z0 + l_dome * math.sin(phi)
            rx_k = r0_x * r_scale
            ry_k = r0_y_radome * r_scale
            yc_k = y0_c - (0.05 * r0_y_radome) * math.sin(phi)

            r_start = len(all_vertices)
            dome_ring_starts.append(r_start)
            for j in range(m):
                theta = (2.0 * math.pi * j) / m
                vx = rx_k * math.sin(theta)
                vy = yc_k + ry_k * math.cos(theta)
                vz = z_k
                all_vertices.append(SrfVertex(x=vx, y=vy, z=vz, round_shading=True))

        # 3. Tail apex vertex (APU / tail cone)
        tail_z = stations[-1].z - max(0.08, stations[-1].radius_x * 0.45)
        tail_y = stations[-1].y_center
        tail_apex = SrfVertex(x=0.0, y=tail_y, z=tail_z, round_shading=True)
        tail_idx = len(all_vertices)
        all_vertices.append(tail_apex)

        # 4. Nose Quad Strips and Pure Quad Cap (Zero Apex Vertex, Zero Spoke Fan)
        s0_start = station_start_indices[0]
        r1_start = dome_ring_starts[0]
        for j in range(m):
            j_next = (j + 1) % m
            faces.append(
                SrfFace(
                    vertex_indices=[s0_start + j, r1_start + j, r1_start + j_next, s0_start + j_next],
                    color=self.default_color,
                )
            )

        for k in range(k_dome - 1):
            curr_start = dome_ring_starts[k]
            next_start = dome_ring_starts[k + 1]
            for j in range(m):
                j_next = (j + 1) % m
                faces.append(
                    SrfFace(
                        vertex_indices=[curr_start + j, next_start + j, next_start + j_next, curr_start + j_next],
                        color=self.default_color,
                    )
                )

        # Cap tip dome ring with pure quad faces (counter-clockwise outward facing +Z)
        tip_start = dome_ring_starts[-1]
        for i in range(m // 2 - 1):
            v0 = (m - 1 - i) % m
            v1 = i
            v2 = i + 1
            v3 = m - 2 - i
            faces.append(
                SrfFace(
                    vertex_indices=[
                        tip_start + v3,
                        tip_start + v2,
                        tip_start + v1,
                        tip_start + v0,
                    ],
                    color=self.default_color,
                )
            )

        # 5. Station-to-Station Quad Strips
        for i in range(n - 1):
            s_curr = station_start_indices[i]
            s_next = station_start_indices[i + 1]

            for j in range(m):
                j_next = (j + 1) % m

                # Quad vertices:
                # curr[j] -> curr[j_next] -> next[j_next] -> next[j]
                v_curr_j = s_curr + j
                v_curr_next = s_curr + j_next
                v_next_next = s_next + j_next
                v_next_j = s_next + j

                # Counter-clockwise winding seen from outside
                faces.append(
                    SrfFace(
                        vertex_indices=[v_curr_j, v_next_j, v_next_next, v_curr_next],
                        color=self.default_color,
                    )
                )

        # 6. Tail Cap Faces (triangle fan from last station to tail apex)
        s_last_start = station_start_indices[-1]
        for j in range(m):
            j_next = (j + 1) % m
            v0 = s_last_start + j
            v1 = tail_idx
            v2 = s_last_start + j_next
            faces.append(
                SrfFace(
                    vertex_indices=[v0, v1, v2],
                    color=self.default_color,
                )
            )

        mesh = SurfaceMesh(name=mesh_name, vertices=all_vertices, faces=faces)
        mesh.compute_missing_normals()
        return mesh

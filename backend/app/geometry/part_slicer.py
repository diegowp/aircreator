"""Part Slicer: Dissects lifting surfaces to isolate movable control surfaces.

Slices a parent aerodynamic surface into:
- Fixed structural part (e.g. wing, horizontal stabilizer, vertical fin).
- Articulated movable surface (e.g. ailerons, flaps, elevator, rudder).
- Calculates the geometric hinge line and boundary vertices between the two parts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.parsers.srf import SrfFace, SrfVertex, SurfaceMesh


@dataclass
class SlicedControlSurfaceResult:
    fixed_mesh: SurfaceMesh
    movable_mesh: SurfaceMesh
    hinge_vertices: list[SrfVertex]
    hinge_center: tuple[float, float, float]
    hinge_vector: tuple[float, float, float]


class PartSlicer:
    def __init__(self):
        pass

    def slice_trailing_edge_surface(
        self,
        surface_mesh: SurfaceMesh,
        chord_cut_fraction: float = 0.70,  # Aft 30% becomes movable surface
        span_start_fraction: float = 0.50,  # Span fraction start (e.g. 0.50 for aileron)
        span_end_fraction: float = 0.98,  # Span fraction end (e.g. 0.98 near wingtip)
        movable_name: str = "aileron",
        fixed_name: str = "wing_fixed",
        is_vertical: bool = False,
    ) -> SlicedControlSurfaceResult:
        """
        Slice an aerodynamic surface to extract an articulated control surface.
        chord_cut_fraction: fraction along chord where hinge line is placed (0.0=LE, 1.0=TE).
        """
        (min_x, min_y, min_z), (max_x, max_y, max_z) = surface_mesh.bounding_box()

        # In YSFlight: +Z is forward (Leading Edge), -Z is rear (Trailing Edge)
        span_dim = (min_y, max_y) if is_vertical else (min_x, max_x)
        span_len = max(0.1, span_dim[1] - span_dim[0])
        chord_len = max(0.1, max_z - min_z)

        # Boundaries in metric space
        s_min = span_dim[0] + span_start_fraction * span_len
        s_max = span_dim[0] + span_end_fraction * span_len

        # Compute local chord bounds for each span station to support swept wings
        span_bins: dict[int, list[float]] = {}
        for v in surface_mesh.vertices:
            span_val = v.y if is_vertical else v.x
            bin_idx = int(round((span_val - span_dim[0]) / max(0.05, span_len) * 30))
            if bin_idx not in span_bins:
                span_bins[bin_idx] = []
            span_bins[bin_idx].append(v.z)

        station_cut_cache: dict[int, float] = {}
        for b_idx, z_vals in span_bins.items():
            st_max_z = max(z_vals)
            st_min_z = min(z_vals)
            st_chord = max(0.2, st_max_z - st_min_z)
            station_cut_cache[b_idx] = st_max_z - chord_cut_fraction * st_chord

        # Classify vertices
        fixed_vertices: list[SrfVertex] = []
        movable_vertices: list[SrfVertex] = []
        old_to_fixed: dict[int, int] = {}
        old_to_movable: dict[int, int] = {}
        hinge_pts: list[SrfVertex] = []

        for idx, v in enumerate(surface_mesh.vertices):
            span_val = v.y if is_vertical else v.x
            is_in_span = s_min <= span_val <= s_max
            b_idx = int(round((span_val - span_dim[0]) / max(0.05, span_len) * 30))
            z_hinge_cut = station_cut_cache.get(b_idx, max_z - chord_cut_fraction * chord_len)
            is_aft = v.z <= z_hinge_cut

            if is_in_span and is_aft:
                old_to_movable[idx] = len(movable_vertices)
                movable_vertices.append(
                    SrfVertex(x=v.x, y=v.y, z=v.z, round_shading=v.round_shading)
                )
                if abs(v.z - z_hinge_cut) < chord_len * 0.15:
                    hinge_pts.append(v)
            else:
                old_to_fixed[idx] = len(fixed_vertices)
                fixed_vertices.append(
                    SrfVertex(x=v.x, y=v.y, z=v.z, round_shading=v.round_shading)
                )

        # Distribute faces: NEVER discard faces to maintain water-tight solid wing mesh!
        fixed_faces: list[SrfFace] = []
        movable_faces: list[SrfFace] = []

        for f in surface_mesh.faces:
            if all(vi in old_to_movable for vi in f.vertex_indices):
                new_indices = [old_to_movable[vi] for vi in f.vertex_indices]
                movable_faces.append(
                    SrfFace(
                        vertex_indices=new_indices,
                        color=f.color,
                        bright=f.bright,
                        alpha=f.alpha,
                    )
                )
            else:
                # Keep face in fixed wing mesh. Ensure all required vertices exist in fixed_vertices
                new_indices = []
                for vi in f.vertex_indices:
                    if vi not in old_to_fixed:
                        v = surface_mesh.vertices[vi]
                        old_to_fixed[vi] = len(fixed_vertices)
                        fixed_vertices.append(
                            SrfVertex(x=v.x, y=v.y, z=v.z, round_shading=v.round_shading)
                        )
                    new_indices.append(old_to_fixed[vi])
                fixed_faces.append(
                    SrfFace(
                        vertex_indices=new_indices,
                        color=f.color,
                        bright=f.bright,
                        alpha=f.alpha,
                    )
                )

        # Calculate Hinge Center & Direction Vector
        if hinge_pts:
            cx = sum(v.x for v in hinge_pts) / len(hinge_pts)
            cy = sum(v.y for v in hinge_pts) / len(hinge_pts)
            cz = sum(v.z for v in hinge_pts) / len(hinge_pts)
            hinge_center = (cx, cy, cz)

            # Direction along span
            if is_vertical:
                hinge_vector = (0.0, 1.0, 0.0)
            else:
                hinge_vector = (1.0, 0.0, 0.0)
        else:
            hinge_center = (
                (s_min + s_max) / 2.0 if not is_vertical else 0.0,
                0.0 if not is_vertical else (s_min + s_max) / 2.0,
                z_hinge_cut,
            )
            hinge_vector = (0.0, 1.0, 0.0) if is_vertical else (1.0, 0.0, 0.0)

        fixed_mesh = SurfaceMesh(name=fixed_name, vertices=fixed_vertices, faces=fixed_faces)
        fixed_mesh.compute_missing_normals()

        movable_mesh = SurfaceMesh(name=movable_name, vertices=movable_vertices, faces=movable_faces)
        movable_mesh.compute_missing_normals()

        return SlicedControlSurfaceResult(
            fixed_mesh=fixed_mesh,
            movable_mesh=movable_mesh,
            hinge_vertices=hinge_pts,
            hinge_center=hinge_center,
            hinge_vector=hinge_vector,
        )

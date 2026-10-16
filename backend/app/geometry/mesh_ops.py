"""Mesh Operations: Symmetry Mirroring, Merging, and Metric Calculations.

Handles:
- Exact geometric reflection across the X=0 plane.
- Reversal of face vertex winding to guarantee outward-pointing normals.
- Multi-mesh merging with index re-mapping.
- Planform surface area integration (for aerodynamic wing area WINGAREA).
"""

from __future__ import annotations

import math

from app.parsers.srf import SrfFace, SrfVertex, SurfaceMesh


def mirror_mesh_x(mesh: SurfaceMesh, new_name: str | None = None) -> SurfaceMesh:
    """
    Create a mirrored copy of the mesh across the X=0 symmetry plane.
    - X coordinates are inverted: X -> -X.
    - Face vertex indices are reversed to maintain counter-clockwise normal winding.
    - Normal vectors and centers are mirrored on X.
    """
    return mesh.mirror_x(new_name=new_name)


def merge_meshes(meshes: list[SurfaceMesh], merged_name: str = "merged_aircraft") -> SurfaceMesh:
    """Combine multiple SurfaceMesh instances into a unified SurfaceMesh."""
    merged_vertices: list[SrfVertex] = []
    merged_faces: list[SrfFace] = []

    for m in meshes:
        v_offset = len(merged_vertices)
        merged_vertices.extend(m.vertices)

        for f in m.faces:
            reindexed = [vi + v_offset for vi in f.vertex_indices]
            merged_faces.append(
                SrfFace(
                    vertex_indices=reindexed,
                    color=f.color,
                    normal=f.normal,
                    center=f.center,
                    bright=f.bright,
                    alpha=f.alpha,
                    is_light=f.is_light,
                )
            )

    merged = SurfaceMesh(name=merged_name, vertices=merged_vertices, faces=merged_faces)
    merged.compute_missing_normals()
    return merged


def calculate_projected_planform_area(mesh: SurfaceMesh) -> float:
    """
    Calculate the projected planform surface area on the horizontal XZ plane (meters^2).
    Used directly to estimate WINGAREA in .dat flight dynamics.
    """
    total_area = 0.0

    for f in mesh.faces:
        if len(f.vertex_indices) < 3:
            continue

        # Check face normal: only count faces pointing generally upward (+Y > 0)
        if f.normal and f.normal[1] <= 0.05:
            continue

        # Shoelace formula on XZ plane
        pts = [(mesh.vertices[idx].x, mesh.vertices[idx].z) for idx in f.vertex_indices]
        area = 0.0
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
        total_area += abs(area) * 0.5

    return total_area


def calculate_mesh_metrics(mesh: SurfaceMesh) -> dict:
    """Calculate key geometric metrics from a SurfaceMesh."""
    (min_x, min_y, min_z), (max_x, max_y, max_z) = mesh.bounding_box()

    wingspan = max_x - min_x
    height = max_y - min_y
    length = max_z - min_z

    # Center of gravity / centroid
    if mesh.vertices:
        cx = sum(v.x for v in mesh.vertices) / len(mesh.vertices)
        cy = sum(v.y for v in mesh.vertices) / len(mesh.vertices)
        cz = sum(v.z for v in mesh.vertices) / len(mesh.vertices)
    else:
        cx, cy, cz = 0.0, 0.0, 0.0

    return {
        "num_vertices": len(mesh.vertices),
        "num_faces": len(mesh.faces),
        "wingspan_m": round(wingspan, 3),
        "length_m": round(length, 3),
        "height_m": round(height, 3),
        "centroid": (round(cx, 3), round(cy, 3), round(cz, 3)),
        "bounding_box": {
            "min": (round(min_x, 3), round(min_y, 3), round(min_z, 3)),
            "max": (round(max_x, 3), round(max_y, 3), round(max_z, 3)),
        },
    }

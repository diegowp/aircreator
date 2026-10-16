"""YSFlight Surface (.srf) Mesh Parser and Serializer.

Handles:
- Vertex parsing (V / VER) with optional Round Shading ('R' flag).
- Face parsing (F / FAC) with RGB (0..255) or 15-bit packed colors.
- Normals and center points (N / NOR).
- Bright / unshaded flag (B / BRI).
- Transparency tags (ZA <polyIndex> <alpha 0..255>).
- Light sprite tags (ZL <polyIndex>).
- Bidirectional serialization (Mesh -> SRF, SRF -> Mesh).
- OBJ conversion for 3D engine interoperability.
- Geometry mirroring across the X=0 symmetry plane.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path


def color15_to_rgb(c15: int) -> tuple[int, int, int]:
    """Convert YSFlight 15-bit packed color to 24-bit RGB (0..255)."""
    g5 = (c15 >> 10) & 31
    r5 = (c15 >> 5) & 31
    b5 = c15 & 31

    r = round((r5 * 255) / 31)
    g = round((g5 * 255) / 31)
    b = round((b5 * 255) / 31)
    return (r, g, b)


def rgb_to_color15(r: int, g: int, b: int) -> int:
    """Convert 24-bit RGB (0..255) to YSFlight 15-bit packed color."""
    r5 = max(0, min(31, round((r * 31) / 255)))
    g5 = max(0, min(31, round((g * 31) / 255)))
    b5 = max(0, min(31, round((b * 31) / 255)))
    return (g5 << 10) | (r5 << 5) | b5


@dataclass
class SrfVertex:
    x: float
    y: float
    z: float
    round_shading: bool = False

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class SrfFace:
    vertex_indices: list[int]
    color: tuple[int, int, int] = (200, 200, 200)
    normal: tuple[float, float, float] | None = None
    center: tuple[float, float, float] | None = None
    bright: bool = False
    alpha: int = 255
    is_light: bool = False


@dataclass
class SurfaceMesh:
    name: str = "surface"
    vertices: list[SrfVertex] = field(default_factory=list)
    faces: list[SrfFace] = field(default_factory=list)

    def calculate_face_normal_and_center(self, face: SrfFace) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Calculate geometric center and outward normal using counter-clockwise vertex winding."""
        if len(face.vertex_indices) < 3:
            return ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))

        v0 = self.vertices[face.vertex_indices[0]]
        v1 = self.vertices[face.vertex_indices[1]]
        v2 = self.vertices[face.vertex_indices[2]]

        # Center: average of all vertices
        cx = sum(self.vertices[i].x for i in face.vertex_indices) / len(face.vertex_indices)
        cy = sum(self.vertices[i].y for i in face.vertex_indices) / len(face.vertex_indices)
        cz = sum(self.vertices[i].z for i in face.vertex_indices) / len(face.vertex_indices)

        # Cross product (v1 - v0) x (v2 - v0)
        ax, ay, az = v1.x - v0.x, v1.y - v0.y, v1.z - v0.z
        bx, by, bz = v2.x - v0.x, v2.y - v0.y, v2.z - v0.z

        nx = ay * bz - az * by
        ny = az * bx - ax * bz
        nz = ax * by - ay * bx

        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length > 1e-9:
            nx /= length
            ny /= length
            nz /= length
        else:
            nx, ny, nz = 0.0, 1.0, 0.0

        return ((cx, cy, cz), (nx, ny, nz))

    def compute_missing_normals(self) -> None:
        """Ensure all faces have valid center and normal vectors."""
        for face in self.faces:
            if face.normal is None or face.center is None:
                center, normal = self.calculate_face_normal_and_center(face)
                if face.center is None:
                    face.center = center
                if face.normal is None:
                    face.normal = normal

    def mirror_x(self, new_name: str | None = None) -> SurfaceMesh:
        """
        Create a mirrored copy of the mesh across the X=0 plane.
        - Inverts vertex X coordinates.
        - Reverses vertex indices order per face to maintain outward normal winding.
        - Mirrors normals and centers on X.
        """
        mirrored_name = new_name or f"{self.name}_mirrored"
        mirrored_vertices = [
            SrfVertex(
                x=-v.x,
                y=v.y,
                z=v.z,
                round_shading=v.round_shading,
            )
            for v in self.vertices
        ]

        mirrored_faces = []
        for face in self.faces:
            # Reverse vertex winding order to maintain outward normals
            reversed_indices = list(reversed(face.vertex_indices))

            mirrored_normal = None
            if face.normal:
                mirrored_normal = (-face.normal[0], face.normal[1], face.normal[2])

            mirrored_center = None
            if face.center:
                mirrored_center = (-face.center[0], face.center[1], face.center[2])

            mirrored_faces.append(
                SrfFace(
                    vertex_indices=reversed_indices,
                    color=face.color,
                    normal=mirrored_normal,
                    center=mirrored_center,
                    bright=face.bright,
                    alpha=face.alpha,
                    is_light=face.is_light,
                )
            )

        mirrored_mesh = SurfaceMesh(
            name=mirrored_name,
            vertices=mirrored_vertices,
            faces=mirrored_faces,
        )
        return mirrored_mesh

    def bounding_box(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Return ((min_x, min_y, min_z), (max_x, max_y, max_z))."""
        if not self.vertices:
            return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

        min_x = min(v.x for v in self.vertices)
        min_y = min(v.y for v in self.vertices)
        min_z = min(v.z for v in self.vertices)

        max_x = max(v.x for v in self.vertices)
        max_y = max(v.y for v in self.vertices)
        max_z = max(v.z for v in self.vertices)

        return ((min_x, min_y, min_z), (max_x, max_y, max_z))

    def to_srf(self, short_syntax: bool = True) -> str:
        """Serialize mesh to YSFlight .srf format string."""
        self.compute_missing_normals()
        lines: list[str] = ["SURF" if short_syntax else "Surf"]

        # Vertices
        v_tag = "V" if short_syntax else "VER"
        for v in self.vertices:
            r_flag = " R" if v.round_shading else ""
            lines.append(f"{v_tag} {v.x:.5f} {v.y:.5f} {v.z:.5f}{r_flag}")

        # Faces
        f_start = "F" if short_syntax else "FAC"
        c_tag = "C" if short_syntax else "COL"
        n_tag = "N" if short_syntax else "NOR"
        e_tag = "E" if short_syntax else "END"

        za_entries: list[tuple[int, int]] = []
        zl_entries: list[int] = []

        for idx, face in enumerate(self.faces):
            lines.append(f_start)
            r, g, b = face.color
            lines.append(f"{c_tag} {r} {g} {b}")

            if face.normal and face.center:
                cx, cy, cz = face.center
                nx, ny, nz = face.normal
                lines.append(f"{n_tag} {cx:.4f} {cy:.4f} {cz:.4f} {nx:.4f} {ny:.4f} {nz:.4f}")
            elif face.normal:
                nx, ny, nz = face.normal
                lines.append(f"{n_tag} {nx:.4f} {ny:.4f} {nz:.4f}")

            v_indices_str = " ".join(str(vi) for vi in face.vertex_indices)
            lines.append(f"{v_tag} {v_indices_str}")

            if face.bright:
                lines.append("B" if short_syntax else "BRI")

            lines.append(e_tag)

            if face.alpha < 255:
                za_entries.append((idx, face.alpha))

            if face.is_light:
                zl_entries.append(idx)

        # End of SURF block
        lines.append(e_tag)

        # Post-SURF Alpha transparency (ZA)
        if za_entries:
            # Group into chunks of 8 pairs per line for clean readability
            chunk_size = 8
            for i in range(0, len(za_entries), chunk_size):
                chunk = za_entries[i : i + chunk_size]
                chunk_str = " ".join(f"{p_idx} {alpha}" for p_idx, alpha in chunk)
                lines.append(f"ZA {chunk_str}")

        # Post-SURF Light sprites (ZL)
        if zl_entries:
            chunk_size = 16
            for i in range(0, len(zl_entries), chunk_size):
                chunk = zl_entries[i : i + chunk_size]
                chunk_str = " ".join(str(p_idx) for p_idx in chunk)
                lines.append(f"ZL {chunk_str}")

        return "\n".join(lines) + "\n"

    def to_obj(self) -> str:
        """Export to standard Wavefront OBJ format for universal 3D tools."""
        lines = [f"# AirCreator export: {self.name}", f"o {self.name}"]

        # Vertices (YSFlight Left-Handed -> OBJ Right-Handed: invert X or Z)
        # Standard conversion: (x_ys, y_ys, z_ys) -> (-x, y, z)
        for v in self.vertices:
            lines.append(f"v {-v.x:.5f} {v.y:.5f} {v.z:.5f}")

        # Normals
        for face in self.faces:
            if face.normal:
                nx, ny, nz = face.normal
                lines.append(f"vn {-nx:.4f} {ny:.4f} {nz:.4f}")

        # Faces (1-indexed)
        norm_idx = 1
        for face in self.faces:
            indices = [str(vi + 1) for vi in face.vertex_indices]
            if face.normal:
                face_str = " ".join(f"{vi}//{norm_idx}" for vi in indices)
                norm_idx += 1
            else:
                face_str = " ".join(indices)
            lines.append(f"f {face_str}")

        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict:
        """Export to JSON-serializable dictionary for API and WebGL rendering."""
        return {
            "name": self.name,
            "vertices": [[round(v.x, 4), round(v.y, 4), round(v.z, 4)] for v in self.vertices],
            "faces": [f.vertex_indices for f in self.faces],
            "colors": [list(f.color) for f in self.faces],
            "alphas": [f.alpha for f in self.faces],
            "round_shading": [bool(v.round_shading) for v in self.vertices],
        }


def parse_srf_text(text: str, name: str = "surface") -> SurfaceMesh:
    """Parse raw SRF ASCII text into a SurfaceMesh instance."""
    lines = text.splitlines()
    vertices: list[SrfVertex] = []
    faces: list[SrfFace] = []

    in_face = False
    current_face: SrfFace | None = None
    surf_closed = False

    za_map: dict[int, int] = {}
    zl_set: set[int] = set()

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        tokens = line.split()
        if not tokens:
            continue

        cmd = tokens[0].upper()

        if cmd in ("SURF",):
            surf_closed = False
            continue

        if not surf_closed:
            # Vertex declaration: V / VER <x> <y> <z> [R]
            if not in_face and cmd in ("V", "VER"):
                if len(tokens) >= 4:
                    x = float(tokens[1])
                    y = float(tokens[2])
                    z = float(tokens[3])
                    is_round = len(tokens) >= 5 and tokens[4].upper() == "R"
                    vertices.append(SrfVertex(x=x, y=y, z=z, round_shading=is_round))
                continue

            # Face start: F / FAC
            if cmd in ("F", "FAC"):
                in_face = True
                current_face = SrfFace(vertex_indices=[])
                continue

            # Inside Face definitions
            if in_face and current_face is not None:
                if cmd in ("C", "COL"):
                    if len(tokens) >= 4:
                        r = int(tokens[1])
                        g = int(tokens[2])
                        b = int(tokens[3])
                        current_face.color = (r, g, b)
                    elif len(tokens) == 2:
                        c15 = int(tokens[1])
                        current_face.color = color15_to_rgb(c15)
                    continue

                if cmd in ("N", "NOR"):
                    if len(tokens) >= 7:
                        cx, cy, cz = float(tokens[1]), float(tokens[2]), float(tokens[3])
                        nx, ny, nz = float(tokens[4]), float(tokens[5]), float(tokens[6])
                        current_face.center = (cx, cy, cz)
                        current_face.normal = (nx, ny, nz)
                    elif len(tokens) >= 4:
                        nx, ny, nz = float(tokens[1]), float(tokens[2]), float(tokens[3])
                        current_face.normal = (nx, ny, nz)
                    continue

                if cmd in ("V", "VER"):
                    # Indices list
                    indices = [int(tok) for tok in tokens[1:]]
                    current_face.vertex_indices.extend(indices)
                    continue

                if cmd in ("B", "BRI"):
                    current_face.bright = True
                    continue

                if cmd in ("E", "END"):
                    faces.append(current_face)
                    in_face = False
                    current_face = None
                    continue

            # End of SURF block
            if not in_face and cmd in ("E", "END"):
                surf_closed = True
                continue

        # Post-SURF blocks (ZA / ZL)
        if cmd == "ZA":
            pairs = tokens[1:]
            for i in range(0, len(pairs) - 1, 2):
                p_idx = int(pairs[i])
                alpha = int(pairs[i + 1])
                za_map[p_idx] = alpha
            continue

        if cmd == "ZL":
            for tok in tokens[1:]:
                zl_set.add(int(tok))
            continue

    # Apply ZA alpha and ZL light sprites to faces
    for p_idx, alpha in za_map.items():
        if 0 <= p_idx < len(faces):
            faces[p_idx].alpha = alpha

    for p_idx in zl_set:
        if 0 <= p_idx < len(faces):
            faces[p_idx].is_light = True

    mesh = SurfaceMesh(name=name, vertices=vertices, faces=faces)
    return mesh


def parse_srf_file(filepath: str | Path) -> SurfaceMesh:
    """Read and parse an .srf file from filesystem."""
    path = Path(filepath)
    content = path.read_text(encoding="utf-8", errors="replace")
    return parse_srf_text(content, name=path.stem)


def write_srf_file(mesh: SurfaceMesh, filepath: str | Path, short_syntax: bool = True) -> None:
    """Serialize and write a SurfaceMesh to file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mesh.to_srf(short_syntax=short_syntax), encoding="utf-8")

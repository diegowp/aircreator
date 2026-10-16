"""YSFlight Package and Universal 3D Asset Export Pipeline.

Generates:
1. Complete YSFlight Aircraft ZIP Archive:
   - <aircraft_id>/<aircraft_id>.lst (Local manifest)
   - <aircraft_id>/<aircraft_id>.dat (Flight dynamics)
   - <aircraft_id>/<aircraft_id>.dnm (Kinematic scene graph with PCK)
   - <aircraft_id>/<aircraft_id>_coll.srf (Collision hull)
   - aircraft.lst.snippet (Global registration entry)
2. Wavefront OBJ + MTL export for Blender, Unreal, Unity.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.parsers.dat import DatFlightModel, write_lst_text
from app.parsers.dnm import DynaModel
from app.parsers.srf import SurfaceMesh


def sanitize_aircraft_id(name: str) -> str:
    """Convert display name into safe filesystem identifier (e.g. 'EMB-314 Super Tucano' -> 'emb314_supertucano')."""
    clean = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[-\s]+", "_", clean)


@dataclass
class AircraftExportPackage:
    aircraft_id: str
    display_name: str
    dat_model: DatFlightModel
    dnm_model: DynaModel
    collision_mesh: SurfaceMesh
    visual_mesh: SurfaceMesh

    def generate_ysflight_zip(self) -> bytes:
        """Create a complete ZIP archive ready to drop into YSFlight's aircraft/ folder."""
        buffer = io.BytesIO()
        aid = self.aircraft_id

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Local Manifest: <aid>/<aid>.lst
            lst_content = write_lst_text(
                dat_rel_path=f"{aid}/{aid}.dat",
                dnm_rel_path=f"{aid}/{aid}.dnm",
                coll_srf_rel_path=f"{aid}/{aid}_coll.srf",
            )
            zf.writestr(f"{aid}/{aid}.lst", lst_content)

            # 2. Flight Dynamics: <aid>/<aid>.dat
            dat_content = self.dat_model.to_dat_text()
            zf.writestr(f"{aid}/{aid}.dat", dat_content)

            # 3. Kinematic Scene Graph with PCK: <aid>/<aid>.dnm
            dnm_content = self.dnm_model.to_dnm_text()
            zf.writestr(f"{aid}/{aid}.dnm", dnm_content)

            # 4. Collision Hull: <aid>/<aid>_coll.srf
            coll_content = self.collision_mesh.to_srf(short_syntax=True)
            zf.writestr(f"{aid}/{aid}_coll.srf", coll_content)

            # 5. Global Registration snippet (instruction for aircraft.lst)
            global_snippet = (
                f"# Add this line to YSFLIGHT/aircraft/aircraft.lst:\n"
                f"{aid} {aid}/{aid}.dat {aid}/{aid}.dnm\n"
            )
            zf.writestr(f"{aid}/aircraft_lst_snippet.txt", global_snippet)

            # 6. Readme with instructions
            readme_text = (
                f"# {self.display_name} for YSFlight\n"
                f"Generated automatically by AirCreator.\n\n"
                f"Installation:\n"
                f"1. Copy the folder '{aid}' to your 'YSFLIGHT/aircraft/' directory.\n"
                f"2. Add the line from 'aircraft_lst_snippet.txt' to 'YSFLIGHT/aircraft/aircraft.lst'.\n"
                f"3. Start YSFlight and fly!\n"
            )
            zf.writestr(f"{aid}/README.txt", readme_text)

        buffer.seek(0)
        return buffer.getvalue()

    def generate_obj_with_mtl(self) -> tuple[str, str]:
        """Export as Wavefront OBJ and MTL pair."""
        aid = self.aircraft_id
        mtl_filename = f"{aid}.mtl"

        # Build OBJ text
        obj_lines = [
            f"# AirCreator export: {self.display_name}",
            f"mtllib {mtl_filename}",
            f"o {aid}",
        ]

        # Invert X for Right-Handed OpenGL/Three.js convention
        for v in self.visual_mesh.vertices:
            obj_lines.append(f"v {-v.x:.5f} {v.y:.5f} {v.z:.5f}")

        for f in self.visual_mesh.faces:
            if f.normal:
                nx, ny, nz = f.normal
                obj_lines.append(f"vn {-nx:.4f} {ny:.4f} {nz:.4f}")

        # Group faces by material/color
        color_materials: dict[tuple[int, int, int], str] = {}
        mat_count = 0

        norm_idx = 1
        for f in self.visual_mesh.faces:
            col = f.color
            if col not in color_materials:
                mat_count += 1
                color_materials[col] = f"mat_{mat_count}"
                obj_lines.append(f"usemtl {color_materials[col]}")

            indices = [str(vi + 1) for vi in f.vertex_indices]
            if f.normal:
                face_str = " ".join(f"{vi}//{norm_idx}" for vi in indices)
                norm_idx += 1
            else:
                face_str = " ".join(indices)
            obj_lines.append(f"f {face_str}")

        obj_text = "\n".join(obj_lines) + "\n"

        # Build MTL text
        mtl_lines = [f"# Material definition for {aid}"]
        for (r, g, b), m_name in color_materials.items():
            rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
            mtl_lines.extend([
                f"newmtl {m_name}",
                f"Kd {rf:.3f} {gf:.3f} {bf:.3f}",
                "Ka 0.200 0.200 0.200",
                "Ks 0.100 0.100 0.100",
                "d 1.0",
                "illum 2",
                "",
            ])

        mtl_text = "\n".join(mtl_lines) + "\n"
        return (obj_text, mtl_text)

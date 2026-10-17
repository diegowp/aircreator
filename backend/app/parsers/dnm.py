"""YSFlight DynaModel (.dnm) Scene Graph and Kinematics Parser & Serializer.

Handles:
- DNMVER 1 header.
- Embedded PCK packages (<mesh_file.srf> <line_count>).
- SRF node definitions:
  - FIL (Surface mesh reference, resolved internally or externally).
  - CLA (Animation class 0..31).
  - NST and STA (Animation states, 16-bit angular deltas).
  - POS (Static placement translation and attitude).
  - CNT (Rotation pivot / hinge vector).
  - REL (DEP / IND dependency).
  - NCH and CLD (Parent-child hierarchy).
- Automatic line-count calculation for PCK blocks.
- Kinematic node mirroring (e.g. left aileron -> right aileron).
- Bidirectional parsing & generation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.parsers.srf import SurfaceMesh, parse_srf_text


@dataclass
class DnmState:
    dx: float = 0.0
    dy: float = 0.0
    dz: float = 0.0
    dh: int = 0  # 16-bit angle
    dp: int = 0
    db: int = 0
    vis: int = 1


@dataclass
class DnmPos:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    h: int = 0
    p: int = 0
    b: int = 0
    vis: int = 1


@dataclass
class DnmNode:
    name: str
    fil: str = ""
    mesh: SurfaceMesh | None = None
    cla: int = 0
    nst: int = 0
    states: list[DnmState] = field(default_factory=list)
    pos: DnmPos = field(default_factory=DnmPos)
    cnt: tuple[float, float, float] = (0.0, 0.0, 0.0)
    pax: tuple[float, float, float] | None = None
    rel: str = "DEP"  # DEP or IND
    children: list[str] = field(default_factory=list)


@dataclass
class DynaModel:
    version: int = 1
    pck_meshes: dict[str, SurfaceMesh] = field(default_factory=dict)
    nodes: dict[str, DnmNode] = field(default_factory=dict)

    def add_node(self, node: DnmNode, parent_name: str | None = None) -> None:
        """Add node to scene graph and update parent's child list if specified."""
        self.nodes[node.name] = node
        if parent_name and parent_name in self.nodes:
            if node.name not in self.nodes[parent_name].children:
                self.nodes[parent_name].children.append(node.name)

    def get_node(self, name: str) -> DnmNode | None:
        return self.nodes.get(name)

    def embed_mesh(self, fil_name: str, mesh: SurfaceMesh) -> None:
        """Embed a mesh into PCK packages."""
        self.pck_meshes[fil_name] = mesh

    def mirror_node_to_contralateral(
        self,
        source_node_name: str,
        target_node_name: str,
        target_fil_name: str | None = None,
    ) -> DnmNode:
        """
        Mirror a kinematic node from left to right (or vice-versa).
        - Inverts X in POS and flips heading (h) and bank (b).
        - Inverts X in CNT pivot.
        - Inverts X in STA delta positions, and flips dh, db in STA.
        - Mirrors internal mesh if present.
        """
        source = self.nodes[source_node_name]
        new_fil = target_fil_name or f"{target_node_name}.srf"

        # Mirror states
        mirrored_states: list[DnmState] = []
        for st in source.states:
            mirrored_states.append(
                DnmState(
                    dx=-st.dx,
                    dy=st.dy,
                    dz=st.dz,
                    dh=-st.dh,
                    dp=st.dp,
                    db=-st.db,
                    vis=st.vis,
                )
            )

        # Mirror POS
        mirrored_pos = DnmPos(
            x=-source.pos.x,
            y=source.pos.y,
            z=source.pos.z,
            h=-source.pos.h,
            p=source.pos.p,
            b=-source.pos.b,
            vis=source.pos.vis,
        )

        # Mirror CNT
        mirrored_cnt = (-source.cnt[0], source.cnt[1], source.cnt[2])

        # Mirror PAX (rotation axis)
        mirrored_pax = (-source.pax[0], source.pax[1], source.pax[2]) if source.pax else None

        # Mirror mesh if available
        mirrored_mesh = None
        source_mesh = source.mesh or self.pck_meshes.get(source.fil)
        if source_mesh:
            mirrored_mesh = source_mesh.mirror_x(new_name=target_node_name)
            self.embed_mesh(new_fil, mirrored_mesh)

        mirrored_node = DnmNode(
            name=target_node_name,
            fil=new_fil,
            mesh=mirrored_mesh,
            cla=source.cla,
            nst=len(mirrored_states),
            states=mirrored_states,
            pos=mirrored_pos,
            cnt=mirrored_cnt,
            pax=mirrored_pax,
            rel=source.rel,
            children=[],
        )

        return mirrored_node

    def to_dnm_text(self) -> str:
        """Serialize DynaModel to standard YSFlight .dnm text format."""
        lines: list[str] = [
            "DYNAMODEL",
            f"DNMVER {self.version}",
            "",
        ]

        # 1. Output PCK blocks
        for fil_name, mesh in self.pck_meshes.items():
            srf_content = mesh.to_srf(short_syntax=True)
            srf_lines = [l for l in srf_content.splitlines() if l.strip()]
            line_count = len(srf_lines)
            lines.append(f"PCK {fil_name} {line_count}")
            lines.extend(srf_lines)
            lines.append("")

        # 2. Output SRF nodes
        for node in self.nodes.values():
            lines.append(f'SRF "{node.name}"')
            if node.fil:
                lines.append(f"FIL {node.fil}")
            lines.append(f"CLA {node.cla}")
            lines.append(f"NST {len(node.states)}")

            for st in node.states:
                lines.append(
                    f"STA {st.dx:.4f} {st.dy:.4f} {st.dz:.4f} {st.dh} {st.dp} {st.db} {st.vis}"
                )

            lines.append(
                f"POS {node.pos.x:.4f} {node.pos.y:.4f} {node.pos.z:.4f} {node.pos.h} {node.pos.p} {node.pos.b} {node.pos.vis}"
            )
            lines.append(f"CNT {node.cnt[0]:.4f} {node.cnt[1]:.4f} {node.cnt[2]:.4f}")
            if node.pax is not None:
                lines.append(f"PAX {node.pax[0]:.6f} {node.pax[1]:.6f} {node.pax[2]:.6f}")
            lines.append(f"REL {node.rel}")
            lines.append(f"NCH {len(node.children)}")
            for child in node.children:
                lines.append(f'CLD "{child}"')
            lines.append("END")
            lines.append("")

        lines.append("END")
        lines.append("")
        return "\n".join(lines)


def parse_dnm_text(text: str) -> DynaModel:
    """Parse YSFlight .dnm text format into a DynaModel scene graph."""
    lines = text.splitlines()
    total_lines = len(lines)
    idx = 0

    version = 1
    pck_meshes: dict[str, SurfaceMesh] = {}
    nodes: dict[str, DnmNode] = {}

    while idx < total_lines:
        line = lines[idx].strip()
        idx += 1

        if not line or line.startswith("#"):
            continue

        tokens = line.split()
        cmd = tokens[0].upper()

        if cmd == "DYNAMODEL":
            continue

        if cmd == "DNMVER":
            if len(tokens) >= 2:
                version = int(tokens[1])
            continue

        # PCK block: PCK <filename> <line_count>
        if cmd == "PCK":
            if len(tokens) >= 3:
                pck_fil = tokens[1]
                count = int(tokens[2])
                pck_text_lines: list[str] = []
                for _ in range(count):
                    if idx < total_lines:
                        pck_text_lines.append(lines[idx])
                        idx += 1
                pck_srf_str = "\n".join(pck_text_lines)
                mesh = parse_srf_text(pck_srf_str, name=pck_fil)
                pck_meshes[pck_fil] = mesh
            continue

        # SRF node: SRF "<name>" or SRF <name>
        if cmd == "SRF":
            # Extract node name (strip quotes)
            match = re.search(r'SRF\s+"?([^"\s]+)"?', line, re.IGNORECASE)
            node_name = match.group(1) if match else (tokens[1] if len(tokens) > 1 else "node")

            node = DnmNode(name=node_name)

            # Parse until node END
            while idx < total_lines:
                n_line = lines[idx].strip()
                idx += 1
                if not n_line or n_line.startswith("#"):
                    continue

                n_tokens = n_line.split()
                n_cmd = n_tokens[0].upper()

                if n_cmd == "FIL":
                    if len(n_tokens) >= 2:
                        node.fil = n_tokens[1]
                        if node.fil in pck_meshes:
                            node.mesh = pck_meshes[node.fil]
                elif n_cmd == "CLA":
                    if len(n_tokens) >= 2:
                        node.cla = int(n_tokens[1])
                elif n_cmd == "NST":
                    if len(n_tokens) >= 2:
                        node.nst = int(n_tokens[1])
                elif n_cmd == "STA":
                    if len(n_tokens) >= 7:
                        dx, dy, dz = float(n_tokens[1]), float(n_tokens[2]), float(n_tokens[3])
                        dh, dp, db = int(n_tokens[4]), int(n_tokens[5]), int(n_tokens[6])
                        vis = int(n_tokens[7]) if len(n_tokens) >= 8 else 1
                        node.states.append(
                            DnmState(dx=dx, dy=dy, dz=dz, dh=dh, dp=dp, db=db, vis=vis)
                        )
                elif n_cmd == "POS":
                    if len(n_tokens) >= 7:
                        x, y, z = float(n_tokens[1]), float(n_tokens[2]), float(n_tokens[3])
                        h, p, b = int(n_tokens[4]), int(n_tokens[5]), int(n_tokens[6])
                        vis = int(n_tokens[7]) if len(n_tokens) >= 8 else 1
                        node.pos = DnmPos(x=x, y=y, z=z, h=h, p=p, b=b, vis=vis)
                elif n_cmd == "CNT":
                    if len(n_tokens) >= 4:
                        cx, cy, cz = float(n_tokens[1]), float(n_tokens[2]), float(n_tokens[3])
                        node.cnt = (cx, cy, cz)
                elif n_cmd == "PAX":
                    if len(n_tokens) >= 4:
                        ax, ay, az = float(n_tokens[1]), float(n_tokens[2]), float(n_tokens[3])
                        node.pax = (ax, ay, az)
                elif n_cmd == "REL":
                    if len(n_tokens) >= 2:
                        node.rel = n_tokens[1].upper()
                elif n_cmd == "NCH":
                    pass  # Count read, children parsed via CLD
                elif n_cmd == "CLD":
                    c_match = re.search(r'CLD\s+"?([^"\s]+)"?', n_line, re.IGNORECASE)
                    if c_match:
                        node.children.append(c_match.group(1))
                elif n_cmd == "END":
                    nodes[node.name] = node
                    break

        if cmd == "END":
            # Model end
            break

    return DynaModel(version=version, pck_meshes=pck_meshes, nodes=nodes)


def parse_dnm_file(filepath: str | Path) -> DynaModel:
    """Read and parse a .dnm file from filesystem."""
    path = Path(filepath)
    content = path.read_text(encoding="utf-8", errors="replace")
    return parse_dnm_text(content)


def write_dnm_file(model: DynaModel, filepath: str | Path) -> None:
    """Serialize and write a DynaModel to file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.to_dnm_text(), encoding="utf-8")

"""Dynamic Aircraft Geometry Builder from Semantic Specification.

Constructs 3D polygonal aircraft meshes (.srf, .dnm, WebGL components)
strictly driven by an AircraftSemanticSpec without hardcoded aircraft templates.
Supports any aircraft: commercial twin/quad turbofans, fighters, trainers, airliners, gliders.
"""

from __future__ import annotations

import math
from typing import Any

from app.ai.spec import AircraftSemanticSpec
from app.geometry.fuselage_lofter import FuselageLofter, FuselageStation, LoftingProfileData
from app.geometry.kinematics_rigging import KinematicsRiggingEngine
from app.geometry.mesh_ops import calculate_mesh_metrics, calculate_projected_planform_area, merge_meshes
from app.geometry.wing_generator import WingGenerator, WingParameters
from app.parsers.dnm import DnmNode, DynaModel
from app.parsers.srf import SrfFace, SrfVertex, SurfaceMesh


def build_fuselage_from_spec(spec: AircraftSemanticSpec, vertices_per_ring: int = 24) -> SurfaceMesh:
    """Build fuselage mesh directly from station cross-sections in spec."""
    z_coords = [s.z_m for s in spec.fuselage.stations]
    y_dorsal = [s.y_top_m for s in spec.fuselage.stations]
    y_ventral = [s.y_bot_m for s in spec.fuselage.stations]
    x_widths = [s.half_width_m for s in spec.fuselage.stations]

    default_n = 2.6 if spec.aircraft_type in ("airliner", "cargo") else 2.0
    super_n = [
        getattr(s, "superellipse_n", default_n)
        if getattr(s, "superellipse_n", 2.0) != 2.0
        else default_n
        for s in spec.fuselage.stations
    ]

    profile = LoftingProfileData(
        z_coords=z_coords,
        y_dorsal=y_dorsal,
        y_ventral=y_ventral,
        x_widths=x_widths,
        superellipse_n=super_n,
    )

    target_stations = max(18, len(z_coords))
    lofter = FuselageLofter(num_stations=target_stations, vertices_per_ring=vertices_per_ring)
    if len(z_coords) < target_stations:
        profile = lofter.smooth_interpolate_profile(profile, target_num_stations=target_stations)

    return lofter.loft_fuselage_mesh(profile, mesh_name="fuselagem")


def build_turbofan_nacelle_mesh(
    nacelle_name: str,
    intake_z: float,
    center_x: float,
    center_y: float,
    nacelle_radius: float = 0.90,
    nacelle_length: float = 3.80,
    pylon_top_y: float | None = None,
    pylon_le_z: float | None = None,
    pylon_aft_z: float | None = None,
    color_cowl: tuple[int, int, int] = (240, 245, 250),
    color_lip: tuple[int, int, int] = (195, 200, 210),
    color_fan: tuple[int, int, int] = (30, 32, 38),
) -> SurfaceMesh:
    """
    Construct high-bypass turbofan engine nacelle (e.g. CFM LEAP-1B, GE90, CFM56):
    - Inlet lip ring (titanium/metallic highlight)
    - Fan cowl / thrust reverser outer barrel
    - Exhaust nozzle rim and core cone
    - Inner fan disc with spinner cone
    - Mounting pylon connecting nacelle to wing intrados
    """
    all_vertices: list[SrfVertex] = []
    faces: list[SrfFace] = []
    m = 16

    cowl_stations = [
        (0.00 * nacelle_length, 0.88 * nacelle_radius, color_lip),     # Inlet Lip Ring
        (0.22 * nacelle_length, 1.00 * nacelle_radius, color_cowl),    # Fan Cowl (Max Diameter)
        (0.65 * nacelle_length, 0.93 * nacelle_radius, color_cowl),    # Thrust Reverser Cowl
        (0.92 * nacelle_length, 0.76 * nacelle_radius, color_cowl),    # Core Cowl Aft
        (1.00 * nacelle_length, 0.62 * nacelle_radius, (50, 52, 58)),  # Exhaust Nozzle Rim
    ]

    ring_start_indices: list[int] = []
    for dz, r, _ in cowl_stations:
        r_start = len(all_vertices)
        ring_start_indices.append(r_start)
        vz = intake_z - dz
        for j in range(m):
            theta = (2.0 * math.pi * j) / m
            vx = center_x + r * math.sin(theta)
            vy = center_y + r * math.cos(theta)
            all_vertices.append(SrfVertex(x=vx, y=vy, z=vz, round_shading=True))

    # Outer cowl quad strips
    for i in range(len(cowl_stations) - 1):
        r_curr = ring_start_indices[i]
        r_next = ring_start_indices[i + 1]
        col = cowl_stations[i][2]
        for j in range(m):
            j_next = (j + 1) % m
            v0 = r_curr + j
            v1 = r_next + j
            v2 = r_next + j_next
            v3 = r_curr + j_next
            faces.append(SrfFace(vertex_indices=[v0, v1, v2, v3], color=col))

    # Inner Fan Face Disc & Center Spinner
    fan_z = intake_z - 0.35
    fan_r = 0.80 * nacelle_radius
    fan_ring_start = len(all_vertices)
    for j in range(m):
        theta = (2.0 * math.pi * j) / m
        vx = center_x + fan_r * math.sin(theta)
        vy = center_y + fan_r * math.cos(theta)
        all_vertices.append(SrfVertex(x=vx, y=vy, z=fan_z, round_shading=False))

    spinner_apex = SrfVertex(x=center_x, y=center_y, z=intake_z - 0.10, round_shading=True)
    spin_idx = len(all_vertices)
    all_vertices.append(spinner_apex)

    for j in range(m):
        j_next = (j + 1) % m
        faces.append(SrfFace(vertex_indices=[spin_idx, fan_ring_start + j, fan_ring_start + j_next], color=color_fan))

    # Core Exhaust Cone
    exhaust_apex = SrfVertex(x=center_x, y=center_y, z=intake_z - nacelle_length * 1.18, round_shading=True)
    ex_idx = len(all_vertices)
    all_vertices.append(exhaust_apex)
    r_last = ring_start_indices[-1]
    for j in range(m):
        j_next = (j + 1) % m
        faces.append(SrfFace(vertex_indices=[ex_idx, r_last + j_next, r_last + j], color=(35, 36, 42)))

    # Mounting Pylon (strut connecting top of nacelle to wing lower surface and leading edge)
    top_y = pylon_top_y if pylon_top_y is not None else (center_y + nacelle_radius + 0.35)
    bot_y = center_y + nacelle_radius * 0.70
    p_fwd = pylon_le_z if pylon_le_z is not None else (intake_z - 0.25 * nacelle_length)
    p_aft = pylon_aft_z if pylon_aft_z is not None else (intake_z - 0.90 * nacelle_length)
    pw = 0.12

    pv_start = len(all_vertices)
    p_pts = [
        (center_x - pw, bot_y, p_fwd),  # 0
        (center_x + pw, bot_y, p_fwd),  # 1
        (center_x + pw, bot_y, p_aft),  # 2
        (center_x - pw, bot_y, p_aft),  # 3
        (center_x - pw, top_y, p_fwd),  # 4
        (center_x + pw, top_y, p_fwd),  # 5
        (center_x + pw, top_y, p_aft),  # 6
        (center_x - pw, top_y, p_aft),  # 7
    ]
    for px, py, pz in p_pts:
        all_vertices.append(SrfVertex(x=px, y=py, z=pz, round_shading=False))

    pylon_faces = [
        [0, 1, 5, 4],  # front
        [1, 2, 6, 5],  # right
        [2, 3, 7, 6],  # rear
        [3, 0, 4, 7],  # left
    ]
    pylon_col = (210, 215, 225)
    for pf in pylon_faces:
        faces.append(SrfFace(vertex_indices=[pv_start + idx for idx in pf], color=pylon_col))

    mesh = SurfaceMesh(name=nacelle_name, vertices=all_vertices, faces=faces)
    mesh.compute_missing_normals()
    return mesh


def build_winglet_mesh(
    winglet_name: str,
    tip_x: float,
    tip_y: float,
    tip_z: float,
    tip_chord: float,
    winglet_height: float = 1.40,
    is_split_scimitar: bool = True,
    side: str = "right",
    color: tuple[int, int, int] = (235, 190, 40),
) -> SurfaceMesh:
    """Construct wingtip winglet (Split Scimitar or canted blended winglet)."""
    all_vertices: list[SrfVertex] = []
    faces: list[SrfFace] = []
    sign_x = 1.0 if side == "right" else -1.0

    # Upper Winglet
    up_tip_x = tip_x + sign_x * 0.22
    up_tip_y = tip_y + winglet_height
    up_tip_z = tip_z - winglet_height * 0.35
    up_chord = max(0.20, tip_chord * 0.35)

    base_pts = [
        (tip_x, tip_y, tip_z),                         # 0: base LE
        (tip_x, tip_y, tip_z - tip_chord),             # 1: base TE
        (up_tip_x, up_tip_y, up_tip_z - up_chord),     # 2: upper tip TE
        (up_tip_x, up_tip_y, up_tip_z),                # 3: upper tip LE
    ]
    v_start = len(all_vertices)
    for px, py, pz in base_pts:
        all_vertices.append(SrfVertex(x=px, y=py, z=pz, round_shading=True))

    faces.append(SrfFace(vertex_indices=[v_start, v_start + 1, v_start + 2, v_start + 3], color=color))
    faces.append(SrfFace(vertex_indices=[v_start, v_start + 3, v_start + 2, v_start + 1], color=color))

    # Lower Scimitar Strake (Split Scimitar)
    if is_split_scimitar:
        low_tip_x = tip_x + sign_x * 0.12
        low_tip_y = tip_y - winglet_height * 0.42
        low_tip_z = tip_z - winglet_height * 0.22
        low_chord = max(0.18, tip_chord * 0.28)

        v_low_start = len(all_vertices)
        low_pts = [
            (tip_x, tip_y, tip_z - tip_chord * 0.35),       # 0
            (tip_x, tip_y, tip_z - tip_chord * 0.90),       # 1
            (low_tip_x, low_tip_y, low_tip_z - low_chord),  # 2
            (low_tip_x, low_tip_y, low_tip_z),              # 3
        ]
        for px, py, pz in low_pts:
            all_vertices.append(SrfVertex(x=px, y=py, z=pz, round_shading=True))

        faces.append(SrfFace(vertex_indices=[v_low_start, v_low_start + 1, v_low_start + 2, v_low_start + 3], color=color))
        faces.append(SrfFace(vertex_indices=[v_low_start, v_low_start + 3, v_low_start + 2, v_low_start + 1], color=color))

    mesh = SurfaceMesh(name=winglet_name, vertices=all_vertices, faces=faces)
    mesh.compute_missing_normals()
    return mesh


def build_dorsal_fin_mesh(
    fin_root_z: float,
    fin_root_y: float,
    dorsal_length: float = 2.80,
    dorsal_height: float = 0.70,
    color: tuple[int, int, int] = (240, 245, 250),
) -> SurfaceMesh:
    """Construct forward dorsal fillet extension on fuselage spine ahead of vertical fin."""
    all_vertices: list[SrfVertex] = []
    faces: list[SrfFace] = []
    th = 0.08

    pts = [
        (0.0, fin_root_y, fin_root_z + dorsal_length),  # 0: fwd apex on spine
        (-th, fin_root_y, fin_root_z),                  # 1: aft left base
        (-th, fin_root_y + dorsal_height, fin_root_z),  # 2: aft left top
        (+th, fin_root_y + dorsal_height, fin_root_z),  # 3: aft right top
        (+th, fin_root_y, fin_root_z),                  # 4: aft right base
    ]
    for px, py, pz in pts:
        all_vertices.append(SrfVertex(x=px, y=py, z=pz, round_shading=True))

    faces.append(SrfFace(vertex_indices=[0, 1, 2], color=color))
    faces.append(SrfFace(vertex_indices=[0, 3, 4], color=color))
    faces.append(SrfFace(vertex_indices=[0, 2, 3], color=color))

    mesh = SurfaceMesh(name="dorsal_fin", vertices=all_vertices, faces=faces)
    mesh.compute_missing_normals()
    return mesh


def build_jet_nozzle_mesh(
    exhaust_z: float,
    exhaust_radius: float = 0.35,
    nozzle_length: float = 0.50,
    thrustline_y: float = 0.0,
    offset_x: float = 0.0,
    color: tuple[int, int, int] = (25, 25, 30),
) -> SurfaceMesh:
    """Build circular jet exhaust nozzle for internal jet fighters."""
    all_vertices: list[SrfVertex] = []
    faces: list[SrfFace] = []
    m = 16

    for i in range(m):
        th = (2.0 * math.pi * i) / m
        vx = offset_x + exhaust_radius * math.cos(th)
        vy = thrustline_y + exhaust_radius * math.sin(th)
        vz = exhaust_z + nozzle_length
        all_vertices.append(SrfVertex(x=vx, y=vy, z=vz, round_shading=True))

    for i in range(m):
        th = (2.0 * math.pi * i) / m
        vx = offset_x + (exhaust_radius * 0.95) * math.cos(th)
        vy = thrustline_y + (exhaust_radius * 0.95) * math.sin(th)
        vz = exhaust_z
        all_vertices.append(SrfVertex(x=vx, y=vy, z=vz, round_shading=True))

    for i in range(m):
        i_next = (i + 1) % m
        v0 = i
        v1 = i_next
        v2 = m + i_next
        v3 = m + i
        faces.append(SrfFace(vertex_indices=[v0, v1, v2, v3], color=color))

    mesh = SurfaceMesh(name="jet_nozzle", vertices=all_vertices, faces=faces)
    mesh.compute_missing_normals()
    return mesh


def _fuselage_section_at(spec: AircraftSemanticSpec, z: float) -> tuple[float, float, float]:
    """Interpolate the fuselage cross-section (y_center, radius_y, radius_x) at longitudinal position z."""
    stations = sorted(spec.fuselage.stations, key=lambda s: s.z_m)
    if not stations:
        return 0.0, 1.0, 1.0

    def section(s) -> tuple[float, float, float]:
        return (
            (s.y_top_m + s.y_bot_m) / 2.0,
            max(0.02, (s.y_top_m - s.y_bot_m) / 2.0),
            max(0.02, s.half_width_m),
        )

    if z <= stations[0].z_m:
        return section(stations[0])
    if z >= stations[-1].z_m:
        return section(stations[-1])
    for a, b in zip(stations[:-1], stations[1:]):
        if a.z_m <= z <= b.z_m:
            t = (z - a.z_m) / max(1e-6, b.z_m - a.z_m)
            sa, sb = section(a), section(b)
            return (
                sa[0] + t * (sb[0] - sa[0]),
                sa[1] + t * (sb[1] - sa[1]),
                sa[2] + t * (sb[2] - sa[2]),
            )
    return section(stations[-1])


def _skin_half_width(spec: AircraftSemanticSpec, z: float, y: float) -> float:
    """Lateral half-width of the elliptical fuselage skin at height y of station z."""
    yc, ry, rx = _fuselage_section_at(spec, z)
    frac = max(-0.97, min(0.97, (y - yc) / ry))
    return rx * math.sqrt(1.0 - frac * frac)


def build_aircraft_from_semantic_spec(
    spec: AircraftSemanticSpec,
    vertices_per_ring: int = 24,
) -> dict[str, Any]:
    """
    Construct complete 3D aircraft from an AircraftSemanticSpec.
    Returns:
        dict with:
            - full_aircraft: SurfaceMesh
            - component_meshes: dict[str, dict]
            - dnm_model: DynaModel
            - metrics: dict
            - wing_area_m2: float
    """
    wing_gen = WingGenerator()
    components_to_merge: list[SurfaceMesh] = []

    # 1. Fuselage
    fuselage_mesh = build_fuselage_from_spec(spec, vertices_per_ring=vertices_per_ring)
    components_to_merge.append(fuselage_mesh)

    # 2. Canopy (if present, for trainers/fighters)
    canopy_mesh: SurfaceMesh | None = None
    if spec.fuselage.cockpit and spec.fuselage.cockpit.present:
        canopy_mesh = wing_gen.generate_canopy_mesh(
            cockpit_start_z=spec.fuselage.cockpit.start_z,
            cockpit_end_z=spec.fuselage.cockpit.end_z,
            base_y=0.35,
            max_height=spec.fuselage.cockpit.max_height,
            max_half_width=spec.fuselage.cockpit.max_half_width,
        )
        components_to_merge.append(canopy_mesh)

    # 3. Wings
    w = spec.wings
    sweep_tan = math.tan(math.radians(w.sweep_leading_edge_deg))
    dihedral_rad = math.radians(w.dihedral_deg)

    # Vertical mounting derived from the real fuselage section at the wing root (low / mid / high wing)
    wing_mid_z = w.root_z - 0.40 * w.root_chord_m
    yc_w, ry_w, _ = _fuselage_section_at(spec, wing_mid_z)
    if w.wing_position == "low":
        wing_root_y = yc_w - 0.78 * ry_w
    elif w.wing_position == "high":
        wing_root_y = yc_w + 0.80 * ry_w
    elif w.wing_position == "mid":
        wing_root_y = yc_w
    else:
        wing_root_y = w.root_y

    # Root junction embedded slightly inside the fuselage skin (no gap, no protrusion)
    wing_root_x = max(0.05, 0.85 * _skin_half_width(spec, wing_mid_z, wing_root_y))

    # span_m is centerline-to-tip; the overall wingspan (user dimension) is authoritative
    semi_span_total = spec.wingspan_m / 2.0 if (spec.wingspan_m and spec.wingspan_m > 0) else w.span_m
    panel_span = max(0.5, semi_span_total - wing_root_x)

    w_params = WingParameters(
        name="wing",
        semi_span_m=panel_span,
        root_chord_m=w.root_chord_m,
        tip_chord_m=w.tip_chord_m,
        sweep_deg=w.sweep_leading_edge_deg,
        dihedral_deg=w.dihedral_deg,
        washout_deg=getattr(w, "washout_deg", -1.5),
        camber=getattr(w, "camber", 0.0),
        camber_pos=getattr(w, "camber_pos", 0.4),
        root_x=wing_root_x,
        root_y=wing_root_y,
        root_z=w.root_z,
        thickness_ratio=w.thickness_ratio,
        kink_eta=w.kink_eta,
        kink_chord_m=w.kink_chord_m,
    )
    wing_r = wing_gen.generate_wing_mesh(w_params, side="right")
    wing_l = wing_gen.generate_wing_mesh(w_params, side="left")
    components_to_merge.extend([wing_r, wing_l])

    def wing_station(x_abs: float) -> tuple[float, float, float]:
        """Return (leading_edge_z, chord_plane_y, local_chord) at lateral position x_abs."""
        span_pos = max(0.0, min(panel_span, abs(x_abs) - wing_root_x))
        eta = span_pos / panel_span
        return (
            w.root_z - span_pos * sweep_tan,
            wing_root_y + span_pos * math.sin(dihedral_rad),
            WingGenerator.chord_at(w_params, eta),
        )

    # Wingtip Winglets (e.g. Split Scimitar for Boeing 737 MAX)
    winglet_r_mesh: SurfaceMesh | None = None
    winglet_l_mesh: SurfaceMesh | None = None
    tip_x_r: float = 0.0
    tip_y_r: float = 0.0
    tip_z_r: float = 0.0

    if w.has_winglets:
        tip_x_r = wing_root_x + panel_span
        tip_z_r, tip_y_r, tip_chord_eff = wing_station(tip_x_r)
        is_split = w.winglet_type == "split_scimitar"

        winglet_r_mesh = build_winglet_mesh(
            winglet_name="winglet_r",
            tip_x=tip_x_r,
            tip_y=tip_y_r,
            tip_z=tip_z_r,
            tip_chord=tip_chord_eff,
            winglet_height=w.winglet_height_m,
            is_split_scimitar=is_split,
            side="right",
        )
        winglet_l_mesh = build_winglet_mesh(
            winglet_name="winglet_l",
            tip_x=-tip_x_r,
            tip_y=tip_y_r,
            tip_z=tip_z_r,
            tip_chord=tip_chord_eff,
            winglet_height=w.winglet_height_m,
            is_split_scimitar=is_split,
            side="left",
        )
        components_to_merge.extend([winglet_r_mesh, winglet_l_mesh])

    # 4. Tail Empennage
    h_stab_r: SurfaceMesh | None = None
    h_stab_l: SurfaceMesh | None = None

    if spec.tail.horizontal_stabilizer and spec.tail.horizontal_stabilizer.present:
        h = spec.tail.horizontal_stabilizer
        h_mid_z = h.root_z - 0.40 * h.root_chord_m
        h_root_y = h.root_y
        if spec.tail.configuration in ("conventional", "twin_fin"):
            # Conventional stabilizers are mounted on the tail cone: keep the root inside the body
            yc_h, ry_h, _ = _fuselage_section_at(spec, h_mid_z)
            h_root_y = max(yc_h - 0.6 * ry_h, min(yc_h + 0.6 * ry_h, h.root_y))
        h_root_x = max(0.05, 0.85 * _skin_half_width(spec, h_mid_z, h_root_y))
        h_params = WingParameters(
            name="elevator_1",
            semi_span_m=max(0.3, h.semi_span_m - h_root_x),
            root_chord_m=h.root_chord_m,
            tip_chord_m=h.tip_chord_m,
            sweep_deg=h.sweep_deg,
            dihedral_deg=h.dihedral_deg,
            thickness_ratio=0.10,
            root_x=h_root_x,
            root_y=h_root_y,
            root_z=h.root_z,
        )
        h_stab_r = wing_gen.generate_wing_mesh(h_params, side="right")
        h_stab_l = wing_gen.generate_wing_mesh(h_params, side="left")
        components_to_merge.extend([h_stab_r, h_stab_l])
    else:
        h_params = WingParameters(
            name="elevator_1",
            semi_span_m=0.3,
            root_chord_m=0.3,
            tip_chord_m=0.15,
            root_z=spec.fuselage.stations[-1].z_m,
        )
        h_stab_r = wing_gen.generate_wing_mesh(h_params, side="right")
        h_stab_l = wing_gen.generate_wing_mesh(h_params, side="left")

    # Vertical Fin(s)
    main_v_fin: SurfaceMesh | None = None
    main_fin_root_y: float | None = None
    main_fin_root_z: float | None = None

    for fin_spec in spec.tail.vertical_fins:
        fin_tip_chord = fin_spec.tip_chord_m
        if fin_spec.sweep_trailing_edge_deg is not None:
            # Tip chord follows from LE and TE sweep: c_tip = c_root - h * (tan(LE) - tan(TE))
            derived = fin_spec.root_chord_m - fin_spec.height_m * (
                math.tan(math.radians(fin_spec.sweep_deg)) - math.tan(math.radians(fin_spec.sweep_trailing_edge_deg))
            )
            fin_tip_chord = max(0.15 * fin_spec.root_chord_m, min(fin_spec.root_chord_m, derived))

        fin_root_y = fin_spec.root_y
        if fin_spec.offset_x <= 0.1:
            # Seat the central fin on the fuselage spine (lowest point under the root chord)
            aft_z = fin_spec.root_z - 0.80 * fin_spec.root_chord_m
            yc_f, ry_f, _ = _fuselage_section_at(spec, aft_z)
            fin_root_y = yc_f + ry_f - 0.05

        v_params = WingParameters(
            name=fin_spec.name,
            semi_span_m=fin_spec.height_m,
            root_chord_m=fin_spec.root_chord_m,
            tip_chord_m=fin_tip_chord,
            sweep_deg=fin_spec.sweep_deg,
            dihedral_deg=0.0,
            thickness_ratio=0.10,
            root_x=fin_spec.offset_x,
            root_y=fin_root_y,
            root_z=fin_spec.root_z,
            is_vertical=True,
        )
        if fin_spec.offset_x > 0.1:
            fin_r = wing_gen.generate_wing_mesh(v_params, side="right")
            fin_l = wing_gen.generate_wing_mesh(v_params, side="left")
            components_to_merge.extend([fin_r, fin_l])
            if main_v_fin is None:
                main_v_fin = fin_r
        else:
            fin_c = wing_gen.generate_wing_mesh(v_params, side="center")
            components_to_merge.append(fin_c)
            if main_v_fin is None:
                main_v_fin = fin_c
                main_fin_root_y = fin_root_y
                main_fin_root_z = fin_spec.root_z

    if main_v_fin is None:
        fallback_params = WingParameters(name="rudder_1", semi_span_m=1.0, root_chord_m=0.8, tip_chord_m=0.4, is_vertical=True)
        main_v_fin = wing_gen.generate_wing_mesh(fallback_params, side="center")
        components_to_merge.append(main_v_fin)

    # Dorsal Fin Fillet Extension (ahead of vertical fin)
    dorsal_mesh: SurfaceMesh | None = None
    fin_root_z_val: float = 0.0
    fin_root_y_val: float = 0.5

    if spec.tail.has_dorsal_fin:
        fin_spec = spec.tail.vertical_fins[0] if spec.tail.vertical_fins else None
        if main_fin_root_z is not None and main_fin_root_y is not None:
            fin_root_z_val = main_fin_root_z
            fin_root_y_val = main_fin_root_y
        else:
            fin_root_z_val = fin_spec.root_z if fin_spec else (spec.fuselage.stations[-1].z_m + 3.0)
            fin_root_y_val = fin_spec.root_y if fin_spec else 0.5
        dorsal_mesh = build_dorsal_fin_mesh(
            fin_root_z=fin_root_z_val,
            fin_root_y=fin_root_y_val,
            dorsal_length=spec.tail.dorsal_fin_length_m,
            dorsal_height=0.75,
        )
        components_to_merge.append(dorsal_mesh)

    # 5. Propulsion
    propeller_mesh: SurfaceMesh | None = None
    jet_mesh: SurfaceMesh | None = None
    engine_r_mesh: SurfaceMesh | None = None
    engine_l_mesh: SurfaceMesh | None = None
    engine_offset_x: float = 0.0
    center_y: float = 0.0
    intake_z: float = 0.0

    if spec.propulsion.type == "jet_pod_underwing":
        # Underwing turbofan pods (Airliners / Commercial Jets)
        nacelle_radius = spec.propulsion.nacelle_radius or 0.92
        nacelle_length = spec.propulsion.nacelle_length or 3.80

        # Lateral station: must sit on the wing panel, clear of the fuselage
        engine_offset_x = spec.propulsion.nacelle_offset_x or (semi_span_total * 0.28)
        min_off = wing_root_x + nacelle_radius + 0.6
        max_off = wing_root_x + 0.65 * panel_span
        engine_offset_x = max(min_off, min(max_off, engine_offset_x))

        le_z, wing_y, c_loc = wing_station(engine_offset_x)

        # Longitudinal: exhaust plane tucked ~25% local chord under the wing (pylon-mounted turbofan)
        auto_intake = le_z - 0.25 * c_loc + nacelle_length
        nz = spec.propulsion.nacelle_z
        if nz and (le_z - 0.6 * c_loc) <= (nz - nacelle_length) <= (le_z + 0.2):
            intake_z = nz
        else:
            intake_z = auto_intake

        # Vertical: nacelle crown just below the wing chord plane (close-coupled, LEAP-1B style)
        center_y = wing_y - 1.05 * nacelle_radius

        engine_r_mesh = build_turbofan_nacelle_mesh(
            nacelle_name="engine_r",
            intake_z=intake_z,
            center_x=+engine_offset_x,
            center_y=center_y,
            nacelle_radius=nacelle_radius,
            nacelle_length=nacelle_length,
            pylon_top_y=wing_y,
            pylon_le_z=le_z,
            pylon_aft_z=le_z - 0.70 * c_loc,
        )
        engine_l_mesh = build_turbofan_nacelle_mesh(
            nacelle_name="engine_l",
            intake_z=intake_z,
            center_x=-engine_offset_x,
            center_y=center_y,
            nacelle_radius=nacelle_radius,
            nacelle_length=nacelle_length,
            pylon_top_y=wing_y,
            pylon_le_z=le_z,
            pylon_aft_z=le_z - 0.70 * c_loc,
        )
        components_to_merge.extend([engine_r_mesh, engine_l_mesh])


    # 6. Kinematics Rigging & Control Surface Slicing
    rigging_engine = KinematicsRiggingEngine()
    dnm_model = rigging_engine.rig_complete_aircraft(
        fuselage_mesh=fuselage_mesh,
        wing_r_mesh=wing_r,
        wing_l_mesh=wing_l,
        h_stab_r_mesh=h_stab_r,
        h_stab_l_mesh=h_stab_l,
        v_fin_mesh=main_v_fin,
        propeller_mesh=propeller_mesh,
        canopy_mesh=canopy_mesh,
    )

    component_meshes = rigging_engine.get_component_meshes_dict()

    if jet_mesh:
        jet_dict = jet_mesh.to_dict()
        jet_dict["pivot"] = [0.0, spec.propulsion.thrustline_y, spec.propulsion.exhaust_z]
        jet_dict["cla"] = 0
        component_meshes["jet_nozzle"] = jet_dict

    if engine_r_mesh and engine_l_mesh:
        er_dict = engine_r_mesh.to_dict()
        er_dict["pivot"] = [+engine_offset_x, center_y, intake_z]
        er_dict["cla"] = 0
        component_meshes["engine_r"] = er_dict

        el_dict = engine_l_mesh.to_dict()
        el_dict["pivot"] = [-engine_offset_x, center_y, intake_z]
        el_dict["cla"] = 0
        component_meshes["engine_l"] = el_dict

        # Embed engine meshes in DynaModel
        dnm_model.embed_mesh("engine_r.srf", engine_r_mesh)
        dnm_model.embed_mesh("engine_l.srf", engine_l_mesh)
        dnm_model.add_node(DnmNode(name="engine_r", fil="engine_r.srf", cla=0, rel="DEP"))
        dnm_model.add_node(DnmNode(name="engine_l", fil="engine_l.srf", cla=0, rel="DEP"))

    if winglet_r_mesh and winglet_l_mesh:
        wr_dict = winglet_r_mesh.to_dict()
        wr_dict["pivot"] = [tip_x_r, tip_y_r, tip_z_r]
        wr_dict["cla"] = 0
        component_meshes["winglet_r"] = wr_dict

        wl_dict = winglet_l_mesh.to_dict()
        wl_dict["pivot"] = [-tip_x_r, tip_y_r, tip_z_r]
        wl_dict["cla"] = 0
        component_meshes["winglet_l"] = wl_dict

        dnm_model.embed_mesh("winglet_r.srf", winglet_r_mesh)
        dnm_model.embed_mesh("winglet_l.srf", winglet_l_mesh)

    if dorsal_mesh:
        dm_dict = dorsal_mesh.to_dict()
        dm_dict["pivot"] = [0.0, fin_root_y_val, fin_root_z_val]
        dm_dict["cla"] = 0
        component_meshes["dorsal_fin"] = dm_dict
        dnm_model.embed_mesh("dorsal_fin.srf", dorsal_mesh)

    full_aircraft = merge_meshes(components_to_merge, merged_name="complete_aircraft")
    metrics = calculate_mesh_metrics(full_aircraft)
    wing_area_m2 = calculate_projected_planform_area(full_aircraft)

    return {
        "full_aircraft": full_aircraft,
        "component_meshes": component_meshes,
        "dnm_model": dnm_model,
        "metrics": metrics,
        "wing_area_m2": round(wing_area_m2, 2),
        "spec": spec,
    }

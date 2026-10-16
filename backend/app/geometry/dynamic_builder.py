"""Dynamic Aircraft Geometry Builder from Semantic Specification.

Constructs 3D polygonal aircraft meshes (.srf, .dnm, WebGL components)
strictly driven by an AircraftSemanticSpec without hardcoded aircraft templates.
Supports any aircraft: single/twin jets, delta wings, turbo-props, airliners, gliders.
"""

from __future__ import annotations

import math
from typing import Any

from app.ai.spec import AircraftSemanticSpec
from app.geometry.fuselage_lofter import FuselageLofter, FuselageStation, LoftingProfileData
from app.geometry.kinematics_rigging import KinematicsRiggingEngine
from app.geometry.mesh_ops import calculate_mesh_metrics, calculate_projected_planform_area, merge_meshes
from app.geometry.wing_generator import WingGenerator, WingParameters
from app.parsers.dnm import DynaModel
from app.parsers.srf import SrfFace, SrfVertex, SurfaceMesh


def build_fuselage_from_spec(spec: AircraftSemanticSpec, vertices_per_ring: int = 16) -> SurfaceMesh:
    """Build fuselage mesh directly from station cross-sections in spec."""
    lofter = FuselageLofter(num_stations=len(spec.fuselage.stations), vertices_per_ring=vertices_per_ring)

    z_coords = [s.z_m for s in spec.fuselage.stations]
    y_dorsal = [s.y_top_m for s in spec.fuselage.stations]
    y_ventral = [s.y_bot_m for s in spec.fuselage.stations]
    x_widths = [s.half_width_m for s in spec.fuselage.stations]

    profile = LoftingProfileData(
        z_coords=z_coords,
        y_dorsal=y_dorsal,
        y_ventral=y_ventral,
        x_widths=x_widths,
    )
    return lofter.loft_fuselage_mesh(profile, mesh_name="fuselagem")


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

    # Front ring (inside fuselage)
    for i in range(m):
        th = (2.0 * math.pi * i) / m
        vx = offset_x + exhaust_radius * math.cos(th)
        vy = thrustline_y + exhaust_radius * math.sin(th)
        vz = exhaust_z + nozzle_length
        all_vertices.append(SrfVertex(x=vx, y=vy, z=vz, round_shading=True))

    # Aft ring (exhaust rim)
    for i in range(m):
        th = (2.0 * math.pi * i) / m
        vx = offset_x + (exhaust_radius * 0.95) * math.cos(th)
        vy = thrustline_y + (exhaust_radius * 0.95) * math.sin(th)
        vz = exhaust_z
        all_vertices.append(SrfVertex(x=vx, y=vy, z=vz, round_shading=True))

    # Quad cylinder faces
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


def build_aircraft_from_semantic_spec(
    spec: AircraftSemanticSpec,
    vertices_per_ring: int = 16,
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

    # 2. Canopy (if present)
    canopy_mesh: SurfaceMesh | None = None
    if spec.fuselage.cockpit.present:
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
    w_params = WingParameters(
        name="wing",
        semi_span_m=w.span_m,
        root_chord_m=w.root_chord_m,
        tip_chord_m=w.tip_chord_m,
        sweep_deg=w.sweep_leading_edge_deg,
        dihedral_deg=w.dihedral_deg,
        root_x=w.root_x,
        root_y=w.root_y,
        root_z=w.root_z,
        thickness_ratio=w.thickness_ratio,
    )
    wing_r = wing_gen.generate_wing_mesh(w_params, side="right")
    wing_l = wing_gen.generate_wing_mesh(w_params, side="left")
    components_to_merge.extend([wing_r, wing_l])

    # 4. Tail Empennage
    h_stab_r: SurfaceMesh | None = None
    h_stab_l: SurfaceMesh | None = None

    if spec.tail.horizontal_stabilizer and spec.tail.horizontal_stabilizer.present:
        h = spec.tail.horizontal_stabilizer
        h_params = WingParameters(
            name="elevator_1",
            semi_span_m=h.semi_span_m,
            root_chord_m=h.root_chord_m,
            tip_chord_m=h.tip_chord_m,
            sweep_deg=h.sweep_deg,
            dihedral_deg=0.0,
            thickness_ratio=0.10,
            root_x=max(0.15, spec.fuselage.stations[-1].half_width_m),
            root_y=h.root_y,
            root_z=h.root_z,
        )
        h_stab_r = wing_gen.generate_wing_mesh(h_params, side="right")
        h_stab_l = wing_gen.generate_wing_mesh(h_params, side="left")
        components_to_merge.extend([h_stab_r, h_stab_l])
    else:
        # Dummy minimal stabilizer for kinematic consistency if tailless delta
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
    vertical_fins_meshes: list[SurfaceMesh] = []
    main_v_fin: SurfaceMesh | None = None

    for fin_spec in spec.tail.vertical_fins:
        v_params = WingParameters(
            name=fin_spec.name,
            semi_span_m=fin_spec.height_m,
            root_chord_m=fin_spec.root_chord_m,
            tip_chord_m=fin_spec.tip_chord_m,
            sweep_deg=fin_spec.sweep_deg,
            dihedral_deg=0.0,
            thickness_ratio=0.10,
            root_x=fin_spec.offset_x,
            root_y=fin_spec.root_y,
            root_z=fin_spec.root_z,
            is_vertical=True,
        )
        if fin_spec.offset_x > 0.1:
            # Twin fins (starboard & port)
            fin_r = wing_gen.generate_wing_mesh(v_params, side="right")
            fin_l = wing_gen.generate_wing_mesh(v_params, side="left")
            vertical_fins_meshes.extend([fin_r, fin_l])
            components_to_merge.extend([fin_r, fin_l])
            if main_v_fin is None:
                main_v_fin = fin_r
        else:
            # Single central fin
            fin_c = wing_gen.generate_wing_mesh(v_params, side="center")
            vertical_fins_meshes.append(fin_c)
            components_to_merge.append(fin_c)
            if main_v_fin is None:
                main_v_fin = fin_c

    if main_v_fin is None:
        # Fallback minimal fin
        fallback_params = WingParameters(name="rudder_1", semi_span_m=1.0, root_chord_m=0.8, tip_chord_m=0.4, is_vertical=True)
        main_v_fin = wing_gen.generate_wing_mesh(fallback_params, side="center")
        components_to_merge.append(main_v_fin)

    # 5. Propulsion
    propeller_mesh: SurfaceMesh | None = None
    jet_mesh: SurfaceMesh | None = None

    if spec.propulsion.type == "propeller_nose":
        (f_min_x, f_min_y, f_min_z), (f_max_x, f_max_y, f_max_z) = fuselage_mesh.bounding_box()
        f_len = max(1.0, f_max_z - f_min_z)
        propeller_mesh = wing_gen.generate_propeller_mesh(
            nose_z=f_max_z,
            thrustline_y=spec.propulsion.thrustline_y,
            spinner_length=spec.propulsion.spinner_length or (f_len * 0.08),
            spinner_radius=spec.propulsion.spinner_radius or (spec.fuselage.stations[0].half_width_m * 0.9),
            prop_radius=spec.wingspan_m * 0.12,
            num_blades=spec.propulsion.num_blades or 5,
        )
        components_to_merge.append(propeller_mesh)
    elif spec.propulsion.type == "jet_internal":
        jet_mesh = build_jet_nozzle_mesh(
            exhaust_z=spec.propulsion.exhaust_z,
            exhaust_radius=spec.propulsion.exhaust_radius or 0.35,
            thrustline_y=spec.propulsion.thrustline_y,
        )
        components_to_merge.append(jet_mesh)

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

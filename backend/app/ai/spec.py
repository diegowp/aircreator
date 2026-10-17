"""Semantic specification for aircraft 3D reconstruction.

Defines the structured intermediate representation of an aircraft extracted
from orthographic technical drawings (via Gemini Vision or vector analysis).
Decouples the geometric lofting engine from any hardcoded aircraft templates.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class FuselageStationSpec(BaseModel):
    u: float = Field(description="Normalized longitudinal position from 0.0 (nose) to 1.0 (tail)")
    z_m: float = Field(description="Longitudinal position along Z in meters (+Z forward, -Z aft)")
    y_top_m: float = Field(description="Dorsal upper contour height in meters above thrustline/waterline")
    y_bot_m: float = Field(description="Ventral lower contour height in meters (typically negative or below thrustline)")
    half_width_m: float = Field(description="Fuselage lateral radius (half width) in meters at this station")
    superellipse_n: float = Field(
        default=2.0,
        description="Lamé superellipse exponent n: 2.0 for circle/ellipse, 2.4-3.2 for squarish airliner/cargo fuselage",
    )


class CockpitSpec(BaseModel):
    present: bool = Field(default=True, description="True if aircraft has an external bubble canopy")
    start_z: float = Field(default=2.5, description="Cockpit forward start position along Z in meters")
    end_z: float = Field(default=-0.5, description="Cockpit aft end position along Z in meters")
    max_height: float = Field(default=0.55, description="Canopy apex height above fuselage dorsal line in meters")
    max_half_width: float = Field(default=0.42, description="Canopy half width in meters")


class FuselageSpec(BaseModel):
    stations: list[FuselageStationSpec] = Field(description="Series of 10 to 18 cross-section stations along fuselage")
    cockpit: CockpitSpec


class WingSpec(BaseModel):
    planform: Literal["swept", "delta", "straight", "tapered", "variable_sweep"] = Field(
        default="tapered", description="Wing planform type"
    )
    span_m: float = Field(
        description="Semi-span measured from the fuselage CENTERLINE to the wingtip in meters (= total wingspan / 2)"
    )
    root_chord_m: float = Field(description="Wing root chord length in meters (at the fuselage side)")
    tip_chord_m: float = Field(description="Wing tip chord length in meters")
    sweep_leading_edge_deg: float = Field(
        default=4.5,
        description=(
            "LEADING EDGE sweep angle in degrees measured in the Top view (0 for straight, 20-50 for swept/delta). "
            "Note: published airliner sweep values are usually quarter-chord (e.g. 737 = 25 deg c/4 = ~29 deg LE)."
        ),
    )
    dihedral_deg: float = Field(default=4.0, description="Wing dihedral angle in degrees (usually 0 to 7)")
    wing_position: Literal["low", "mid", "high"] | None = Field(
        default=None,
        description="Vertical wing mounting on the fuselage seen in Front/Side views: 'low' (airliners), 'mid', 'high' (cargo/turboprops)",
    )
    root_x: float = Field(default=0.60, description="Wing root junction X offset from fuselage centerline in meters")
    root_y: float = Field(
        default=-0.15, description="Vertical placement: negative for low wing, 0 for mid wing, positive for high wing"
    )
    root_z: float = Field(default=0.80, description="Longitudinal position of wing root leading edge along Z")
    thickness_ratio: float = Field(default=0.12, description="NACA airfoil thickness ratio (e.g. 0.10 to 0.15)")
    camber: float = Field(
        default=0.0,
        description="NACA 4-digit maximum camber fraction m (0.0 for symmetric NACA 00xx, 0.02 for NACA 2412)",
    )
    camber_pos: float = Field(
        default=0.4,
        description="Chordwise location of maximum camber p (fraction 0..1, e.g. 0.4 for 40% chord)",
    )
    washout_deg: float = Field(
        default=-1.5,
        description="Wingtip aerodynamic twist (washout) in degrees (negative for wash-out)",
    )
    kink_eta: float | None = Field(
        default=None,
        description="Spanwise fraction (0..1) of a trailing-edge kink (Yehudi) if inboard TE is unswept (airliners ~0.30-0.40)",
    )
    kink_chord_m: float | None = Field(default=None, description="Chord at the trailing-edge kink in meters (optional)")
    has_winglets: bool = Field(default=False, description="True if wingtips have vertical winglets (e.g. 737 MAX split scimitar, A320 sharklets)")
    winglet_height_m: float = Field(default=1.40, description="Height of winglet above wingtip in meters")
    winglet_type: Literal["blended", "split_scimitar", "sharklet", "fence"] = Field(
        default="split_scimitar", description="Winglet style"
    )


class VerticalFinSpec(BaseModel):
    name: str = Field(default="vertical_fin")
    height_m: float = Field(description="Height of fin in meters")
    root_chord_m: float = Field(description="Root chord length in meters")
    tip_chord_m: float = Field(description="Tip chord length in meters")
    sweep_deg: float = Field(default=20.0, description="Leading edge sweep angle in degrees")
    sweep_trailing_edge_deg: float | None = Field(
        default=None, description="Trailing edge sweep angle in degrees (optional; derives tip chord when given)"
    )
    offset_x: float = Field(default=0.0, description="Lateral offset from centerline (0 for central fin, >0 for twin fins)")
    root_y: float = Field(default=0.30, description="Vertical base position in meters")
    root_z: float = Field(default=-3.5, description="Longitudinal position of fin root in meters")


class HorizontalStabSpec(BaseModel):
    present: bool = Field(default=True, description="True if aircraft has a horizontal stabilizer (false for pure delta)")
    semi_span_m: float = Field(description="Semi-span in meters")
    root_chord_m: float = Field(description="Root chord length in meters")
    tip_chord_m: float = Field(description="Tip chord length in meters")
    sweep_deg: float = Field(default=5.0, description="Leading edge sweep angle in degrees")
    dihedral_deg: float = Field(default=0.0, description="Stabilizer dihedral in degrees seen in Front view (737 ~7)")
    root_y: float = Field(default=0.20, description="Vertical base position in meters (high for T-tail, low for conventional)")
    root_z: float = Field(default=-4.0, description="Longitudinal position in meters")


class TailSpec(BaseModel):
    configuration: Literal["conventional", "t_tail", "v_tail", "twin_fin", "tailless_delta"] = Field(
        default="conventional", description="Tail layout type"
    )
    horizontal_stabilizer: HorizontalStabSpec | None = None
    vertical_fins: list[VerticalFinSpec] = Field(description="List of vertical fins (1 for central, 2 for twin fins)")
    has_dorsal_fin: bool = Field(default=False, description="True if vertical fin has a forward dorsal fillet extension")
    dorsal_fin_length_m: float = Field(default=2.50, description="Length of dorsal fillet along fuselage spine")


class PropulsionSpec(BaseModel):
    type: Literal["propeller_nose", "jet_internal", "jet_pod_underwing", "turboprop_wing", "rocket", "none"] = Field(
        default="propeller_nose", description="Propulsion type"
    )
    num_blades: int = Field(default=5, description="Number of propeller blades if propeller_nose (e.g. 3, 4, 5)")
    spinner_length: float = Field(default=0.85, description="Spinner cone length in meters")
    spinner_radius: float = Field(default=0.38, description="Spinner cone base radius in meters")
    thrustline_y: float = Field(default=0.0, description="Thrust axis vertical coordinate")
    exhaust_z: float = Field(default=-5.0, description="Jet exhaust longitudinal coordinate if jet_internal")
    exhaust_radius: float = Field(default=0.35, description="Jet nozzle radius in meters")
    # Underwing turbofans (Airliners / Cargo Jets)
    nacelle_count: int = Field(default=2, description="Number of underwing turbofans (2 for twinjet, 4 for quadjet)")
    nacelle_radius: float = Field(default=0.90, description="Nacelle cowl outer radius in meters (diameter ~1.8m)")
    nacelle_length: float = Field(default=3.80, description="Nacelle length in meters")
    nacelle_offset_x: float = Field(default=4.80, description="Lateral distance of engine center from fuselage centerline in meters")
    nacelle_z: float = Field(default=0.0, description="Longitudinal position of nacelle intake lip in meters")


class AircraftSemanticSpec(BaseModel):
    aircraft_name: str = "Reconstructed Aircraft"
    aircraft_type: str = Field(
        default="fighter_jet",
        description="Category: trainer, fighter_jet, airliner, cargo, glider, delta_wing, drone, custom_object",
    )
    wingspan_m: float
    length_m: float
    height_m: float
    fuselage: FuselageSpec
    wings: WingSpec
    tail: TailSpec
    propulsion: PropulsionSpec

    @property
    def name(self) -> str:
        return self.aircraft_name

    @name.setter
    def name(self, value: str) -> None:
        self.aircraft_name = value

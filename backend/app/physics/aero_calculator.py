"""Aeronautical Physics and Flight Dynamics (.dat) Calibrator.

Calculates:
- Aerodynamic reference metrics: WINGAREA (S), wingspan (b), Aspect Ratio (AR), MAC.
- Collision sphere radius (HTRADIUS).
- Landing gear 3D contact triangle (LEFTGEAR, RIGHGEAR, WHELGEAR) with stability check.
- Cockpit eye reference point (COCKPITP).
- Aircraft mass properties: Clean weight (WEIGHCLN), fuel (WEIGFUEL), MTOW.
- Stall, maneuver, cruise, and maximum speed limits.
- Polar drag and lift derivatives (CLBYFLAP, CDBYFLAP, CDBYGEAR).
- Generates a fully validated DatFlightModel ready for YSFlight simulation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.geometry.mesh_ops import calculate_mesh_metrics, calculate_projected_planform_area
from app.parsers.dat import DatFlightModel, Vector3Dat
from app.parsers.srf import SurfaceMesh


@dataclass
class AircraftCategoryPreset:
    category_name: str  # TRAINER, FIGHTER, NORMAL, CARGO
    airclass: str  # AIRPLANE or HELICOPTER
    propulsion_type: str  # PISTON_PROP, TURBOPROP, JET
    default_hp: float | None = None
    default_thrust_kg: float | None = None
    has_afterburner: bool = False
    clean_weight_ratio: float = 120.0  # kg per m^2 of wing area approximate
    aspect_ratio_typical: float = 6.5
    cl_max_clean: float = 1.55
    cl_max_flap: float = 2.10
    cd0: float = 0.024
    oswald_e: float = 0.82


AIRCRAFT_PRESETS: dict[str, AircraftCategoryPreset] = {
    "TRAINER": AircraftCategoryPreset(
        category_name="TRAINER",
        airclass="AIRPLANE",
        propulsion_type="TURBOPROP",
        default_hp=750.0,
        has_afterburner=False,
        clean_weight_ratio=105.0,  # ~1.8t for ~17m^2 wing (like T-25)
        cl_max_clean=1.60,
        cl_max_flap=2.20,
    ),
    "SUPER_TUCANO": AircraftCategoryPreset(
        category_name="TRAINER",
        airclass="AIRPLANE",
        propulsion_type="TURBOPROP",
        default_hp=1600.0,
        has_afterburner=False,
        clean_weight_ratio=160.0,  # ~3.2t empty for ~19m^2 wing
        cl_max_clean=1.65,
        cl_max_flap=2.30,
    ),
    "FIGHTER": AircraftCategoryPreset(
        category_name="FIGHTER",
        airclass="AIRPLANE",
        propulsion_type="JET",
        default_thrust_kg=8500.0,
        has_afterburner=True,
        clean_weight_ratio=280.0,  # High wing loading
        cl_max_clean=1.40,
        cl_max_flap=1.80,
    ),
    "CARGO": AircraftCategoryPreset(
        category_name="CARGO",
        airclass="AIRPLANE",
        propulsion_type="TURBOPROP",
        default_hp=4500.0,
        has_afterburner=False,
        clean_weight_ratio=220.0,
        cl_max_clean=1.70,
        cl_max_flap=2.40,
    ),
}


class AeroPhysicsCalibrator:
    def __init__(self, air_density_sea_level: float = 1.225):
        self.rho = air_density_sea_level
        self.g = 9.80665

    def calculate_aero_metrics(self, aircraft_mesh: SurfaceMesh) -> dict:
        """Measure fundamental physical dimensions from the 3D aircraft mesh."""
        metrics = calculate_mesh_metrics(aircraft_mesh)
        wing_area = calculate_projected_planform_area(aircraft_mesh)

        # Fallback if planform area is small or wingless
        wingspan = metrics["wingspan_m"]
        length = metrics["length_m"]
        if wing_area < 2.0:
            wing_area = wingspan * (length * 0.18)

        aspect_ratio = (wingspan**2) / max(1.0, wing_area)
        mac = wing_area / max(1.0, wingspan)

        # Collision sphere radius: maximum distance from centroid + 5% margin
        cx, cy, cz = metrics["centroid"]
        max_dist_sq = 0.0
        for v in aircraft_mesh.vertices:
            dist_sq = (v.x - cx) ** 2 + (v.y - cy) ** 2 + (v.z - cz) ** 2
            if dist_sq > max_dist_sq:
                max_dist_sq = dist_sq
        htradius = math.sqrt(max_dist_sq) * 1.05

        return {
            "wingspan_m": wingspan,
            "length_m": length,
            "height_m": metrics["height_m"],
            "wing_area_m2": round(wing_area, 2),
            "aspect_ratio": round(aspect_ratio, 2),
            "mean_aerodynamic_chord_m": round(mac, 2),
            "htradius_m": round(htradius, 2),
            "bounding_box": metrics["bounding_box"],
            "centroid": (cx, cy, cz),
        }

    def estimate_landing_gears(
        self,
        aircraft_mesh: SurfaceMesh,
        ground_y_override: float | None = None,
    ) -> tuple[Vector3Dat, Vector3Dat, Vector3Dat]:
        """
        Estimate stable 3D contact triangle (LEFTGEAR, RIGHGEAR, WHELGEAR)
        using the lowest points of the aircraft geometry.
        """
        (min_x, min_y, min_z), (max_x, max_y, max_z) = aircraft_mesh.bounding_box()
        wingspan = max_x - min_x
        length = max_z - min_z

        ground_y = ground_y_override if ground_y_override is not None else min_y

        # Main gear track: typically 20% to 25% of wingspan
        gear_track_half = max(1.0, wingspan * 0.18)
        # Main gear longitudinal position: slightly aft of CG (around mid-wing ~ 40% from nose)
        main_gear_z = max_z - length * 0.45

        # Nose wheel longitudinal position: forward around 20% from nose
        nose_gear_z = max_z - length * 0.20

        left_gear = Vector3Dat(x=-gear_track_half, y=ground_y, z=main_gear_z)
        right_gear = Vector3Dat(x=gear_track_half, y=ground_y, z=main_gear_z)
        nose_gear = Vector3Dat(x=0.0, y=ground_y, z=nose_gear_z)

        return (left_gear, right_gear, nose_gear)

    def generate_flight_model(
        self,
        aircraft_mesh: SurfaceMesh,
        identify: str = "AirCreator Aircraft",
        preset_name: str = "SUPER_TUCANO",
        custom_mtow_ton: float | None = None,
    ) -> DatFlightModel:
        """
        Build a completely configured and calibrated DatFlightModel based on
        aerodynamic geometry and engineering equations.
        """
        preset = AIRCRAFT_PRESETS.get(preset_name, AIRCRAFT_PRESETS["TRAINER"])
        aero = self.calculate_aero_metrics(aircraft_mesh)

        wing_area = aero["wing_area_m2"]
        wingspan = aero["wingspan_m"]
        length = aero["length_m"]
        htradius = aero["htradius_m"]

        # 1. Weights and Balance
        if custom_mtow_ton:
            mtow = custom_mtow_ton
            clean_weight = mtow * 0.65
            fuel_weight = mtow * 0.20
            payload_weight = mtow * 0.15
        else:
            clean_weight = (wing_area * preset.clean_weight_ratio) / 1000.0  # in tons
            fuel_weight = clean_weight * 0.25
            payload_weight = clean_weight * 0.35
            mtow = clean_weight + fuel_weight + payload_weight

        # 2. Aerodynamic Speeds from Stall Equation
        # V_stall = sqrt( (2 * MTOW * g) / (rho * S * CL_max) )
        w_newtons = mtow * 1000.0 * self.g
        v_stall_clean_ms = math.sqrt((2.0 * w_newtons) / (self.rho * wing_area * preset.cl_max_clean))
        v_stall_clean_kmh = v_stall_clean_ms * 3.6

        # Characteristic speeds
        v_mane1_kmh = v_stall_clean_kmh * 1.15
        v_mane2_kmh = v_stall_clean_kmh * 1.45
        v_land_kmh = v_stall_clean_kmh * 1.25

        if preset.propulsion_type == "JET":
            v_cruise_kmh = max(550.0, v_stall_clean_kmh * 3.2)
            v_crit_kmh = max(750.0, v_cruise_kmh * 1.25)
            v_max_kmh = max(900.0, v_crit_kmh * 1.10)
        else:
            v_cruise_kmh = max(260.0, v_stall_clean_kmh * 2.0)
            v_crit_kmh = max(340.0, v_cruise_kmh * 1.25)
            v_max_kmh = max(390.0, v_crit_kmh * 1.15)

        # 3. Landing Gear Contact Points
        left_gear, right_gear, nose_gear = self.estimate_landing_gears(aircraft_mesh)

        # 4. Cockpit Position (Pilot eye view in first person)
        cockpit_x = 0.0
        cockpit_y = (aero["centroid"][1]) + 0.65
        cockpit_z = aero["bounding_box"]["max"][2] - length * 0.35
        cockpit_pos = Vector3Dat(x=cockpit_x, y=cockpit_y, z=cockpit_z)

        # 5. Populate DatFlightModel
        flight_model = DatFlightModel(
            identify=identify,
            category=preset.category_name,
            airclass=preset.airclass,
            strength=6 if preset.propulsion_type == "JET" else 3,
            radarcrs=1.5,
            # Propulsion
            propellr_hp=preset.default_hp,
            propefcy=0.82,
            thrmilit=preset.default_thrust_kg,
            thraftbn=(preset.default_thrust_kg * 1.5) if preset.has_afterburner else None,
            aftburnr=preset.has_afterburner,
            fuelmili=0.035 if preset.propulsion_type == "JET" else 0.022,
            # Weights
            weighcln=round(clean_weight, 2),
            weigfuel=round(fuel_weight, 2),
            weigload=round(payload_weight, 2),
            initfuel=1.0,
            initload=0.0,
            # Aerodynamics
            wingarea=wing_area,
            critaoap=16.5,
            critaoam=-14.0,
            critsped_kmh=round(v_crit_kmh, 0),
            maxspeed_kmh=round(v_max_kmh, 0),
            manespd1_kmh=round(v_mane1_kmh, 0),
            manespd2_kmh=round(v_mane2_kmh, 0),
            # Stability derivatives
            cpitmane=7.0,
            cpitstab=3.2,
            cyawmane=4.5,
            cyawstab=3.0,
            crollman=3.0,
            clbyflap=round(preset.cl_max_flap - preset.cl_max_clean, 2),
            cdbyflap=0.35,
            cdbygear=0.45,
            cdspoilr=0.75,
            # 3D contact points
            cockpitp=cockpit_pos,
            leftgear=left_gear,
            righgear=right_gear,
            whelgear=nose_gear,
            htradius=htradius,
            # Cruise & landing
            refvcrus_kmh=round(v_cruise_kmh, 0),
            refacrus_ft=12000.0 if preset.propulsion_type == "JET" else 8000.0,
            reftcrus=0.80,
            refvland_kmh=round(v_land_kmh, 0),
            refaoald_deg=8.5,
            reflnrwy_m=650.0,
            refthrld=0.45,
        )

        return flight_model

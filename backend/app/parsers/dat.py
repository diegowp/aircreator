"""YSFlight Flight Dynamics (.dat) and Manifest (.lst) Parser & Serializer.

Handles:
- Full aeronautical physics specifications:
  - Identification, Category, AirClass, Strength, Radar Cross Section.
  - Propulsion: Piston/Turboprop (HP), Jet/Turbofan (Thrust, Afterburner, Fuel).
  - Weights & Balances: Clean Weight, Fuel, Payload, MTOW calculation.
  - Aerodynamics: Wing Area, Critical AoA, Speed limits, Control stability derivatives.
  - 3D Contact Points: Left/Right/Nose gear, Cockpit eye point, Collision radius.
  - Reference parameters for autopilot / AI (Cruise, Landing).
- Unit conversions: meters, feet, inches; tons, kg, lbs; km/h, kt, Mach; deg.
- Physics integrity validation against the engineering spec.
- Local aircraft manifest (.lst) parser and writer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


def parse_distance(val_str: str) -> float:
    """Parse distance string to meters (e.g. '1.5m', '5ft', '20in', '-0.20')."""
    s = val_str.strip().lower()
    if s.endswith("m^2") or s.endswith("m2"):
        return float(s.replace("m^2", "").replace("m2", ""))
    if s.endswith("ft"):
        return float(s[:-2]) * 0.3048
    if s.endswith("in"):
        return float(s[:-2]) * 0.0254
    if s.endswith("m"):
        return float(s[:-1])
    return float(s)


def parse_thrust(val_str: str) -> float:
    """Parse thrust value in kg or N (e.g. '8500kg', '12000N', '8500')."""
    s = val_str.strip().lower()
    if s.endswith("kg"):
        return float(s[:-2])
    if s.endswith("n"):
        return float(s[:-1]) / 9.80665  # Convert Newtons to kg-force
    return float(s)



def parse_weight_ton(val_str: str) -> float:
    """Parse weight string to metric tons (1.0 = 1000kg)."""
    s = val_str.strip().lower()
    if s.endswith("kg"):
        return float(s[:-2]) / 1000.0
    if s.endswith("lb"):
        return float(s[:-2]) * 0.00045359237
    if s.endswith("t"):
        return float(s[:-1])
    return float(s)


def parse_speed_kmh(val_str: str) -> float:
    """Parse speed string to km/h."""
    s = val_str.strip().lower()
    if s.endswith("km/h"):
        return float(s[:-4])
    if s.endswith("kt"):
        return float(s[:-2]) * 1.852
    if s.endswith("m/s"):
        return float(s[:-3]) * 3.6
    if s.endswith("mach"):
        # Sea level approximate: 1 Mach = 1225 km/h
        return float(s[:-4]) * 1225.0
    return float(s)


def parse_angle_deg(val_str: str) -> float:
    """Parse angle string to degrees."""
    s = val_str.strip().lower()
    if s.endswith("deg"):
        return float(s[:-3])
    if s.endswith("rad"):
        return float(s[:-3]) * 57.2957795
    return float(s)


@dataclass
class Vector3Dat:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class DatFlightModel:
    # 1. Identification
    identify: str = "AirCreator Aircraft"
    category: str = "TRAINER"  # TRAINER, FIGHTER, NORMAL, CARGO, HELICOPTER
    airclass: str = "AIRPLANE"
    strength: int = 5
    radarcrs: float = 1.0  # m^2

    # 2. Propulsion
    propellr_hp: float | None = None  # Horsepower for prop
    propefcy: float = 0.8
    thrmilit: float | None = None  # Thrust military (kg or N)
    thraftbn: float | None = None  # Thrust with afterburner
    aftburnr: bool = False
    fuelmili: float = 0.02  # kg/sec

    # 3. Weights & Balance (Tons)
    weighcln: float = 1.0  # Clean weight (t)
    weigfuel: float = 0.3  # Max fuel (t)
    weigload: float = 0.5  # Max payload (t)
    initfuel: float = 1.0  # 100%
    initload: float = 0.0

    # 4. Aerodynamics
    wingarea: float = 15.0  # m^2
    critaoap: float = 16.0  # Positive stall AoA (deg)
    critaoam: float = -14.0  # Negative stall AoA (deg)
    critsped_kmh: float = 300.0  # km/h
    maxspeed_kmh: float = 350.0  # km/h
    manespd1_kmh: float = 100.0  # km/h
    manespd2_kmh: float = 140.0  # km/h

    # Control stability constants
    cpitmane: float = 6.0
    cpitstab: float = 3.0
    cyawmane: float = 4.0
    cyawstab: float = 3.0
    crollman: float = 2.5

    # Incremental drag/lift
    clbyflap: float = 0.3
    cdbyflap: float = 0.4
    cdbygear: float = 0.5
    cdspoilr: float = 0.8

    # 5. 3D Coordinates (YSFlight left-handed meters)
    cockpitp: Vector3Dat = field(default_factory=lambda: Vector3Dat(0.0, 0.8, 0.5))
    leftgear: Vector3Dat = field(default_factory=lambda: Vector3Dat(-1.5, -1.5, 0.0))
    righgear: Vector3Dat = field(default_factory=lambda: Vector3Dat(1.5, -1.5, 0.0))
    whelgear: Vector3Dat = field(default_factory=lambda: Vector3Dat(0.0, -1.4, 2.0))
    smokegen: Vector3Dat = field(default_factory=lambda: Vector3Dat(0.0, 0.0, -3.0))
    htradius: float = 6.0

    # 6. Autopilot / Reference Conditions
    refvcrus_kmh: float = 250.0
    refacrus_ft: float = 8000.0
    reftcrus: float = 0.75
    refvland_kmh: float = 120.0
    refaoald_deg: float = 8.0
    reflnrwy_m: float = 600.0
    refthrld: float = 0.40

    # Raw / preserved lines for custom keys
    raw_properties: dict[str, list[str]] = field(default_factory=dict)

    @property
    def mtow_ton(self) -> float:
        """Maximum Takeoff Weight in metric tons."""
        return self.weighcln + self.weigfuel + self.weigload

    @property
    def wing_loading_kg_m2(self) -> float:
        """Wing loading W/S in kg/m^2."""
        if self.wingarea <= 0:
            return 0.0
        return (self.mtow_ton * 1000.0) / self.wingarea

    def validate_physics(self) -> list[str]:
        """Validate flight dynamics against aeronautical engineering rules."""
        issues: list[str] = []

        if self.weighcln <= 0:
            issues.append(f"Clean weight WEIGHCLN must be > 0 (found {self.weighcln}t).")

        if self.weigfuel <= 0:
            issues.append(f"Fuel weight WEIGFUEL must be > 0 (found {self.weigfuel}t).")

        if self.critaoap <= 0 or self.critaoam >= 0:
            issues.append(
                f"Stall angles invalid: CRITAOAP must be > 0 and CRITAOAM < 0 (found {self.critaoap}° / {self.critaoam}°)."
            )

        if not (self.manespd1_kmh < self.manespd2_kmh <= self.critsped_kmh <= self.maxspeed_kmh):
            issues.append(
                f"Speed hierarchy invalid: expected MANESPD1 ({self.manespd1_kmh}) < "
                f"MANESPD2 ({self.manespd2_kmh}) <= CRITSPED ({self.critsped_kmh}) <= MAXSPEED ({self.maxspeed_kmh})."
            )

        if self.htradius <= 0:
            issues.append(f"Collision radius HTRADIUS must be > 0 (found {self.htradius}m).")

        # Gear triangle validation
        if not (self.leftgear.x < 0 and self.righgear.x > 0):
            issues.append(
                f"Main gears must be on opposite sides of X: LEFTGEAR.x={self.leftgear.x}, RIGHGEAR.x={self.righgear.x}."
            )

        # Wing loading check
        wl = self.wing_loading_kg_m2
        if not (30.0 <= wl <= 900.0):
            issues.append(f"Wing loading out of realistic aircraft bounds [30..900 kg/m²]: {wl:.1f} kg/m².")

        return issues

    def to_dat_text(self) -> str:
        """Serialize DatFlightModel to YSFlight .dat ASCII format string."""
        lines: list[str] = [
            f'IDENTIFY "{self.identify}"',
            f"CATEGORY {self.category}",
            f"AIRCLASS {self.airclass}",
            f"STRENGTH {self.strength}",
            f"RADARCRS {self.radarcrs:.3f}m^2",
            "",
            "# Propulsion",
        ]

        if self.propellr_hp is not None:
            lines.append(f"PROPELLR {self.propellr_hp:.0f}HP")
            lines.append(f"PROPEFCY {self.propefcy:.2f}")
        elif self.thrmilit is not None:
            lines.append(f"THRMILIT {self.thrmilit:.0f}kg")
            if self.thraftbn is not None:
                lines.append(f"THRAFTBN {self.thraftbn:.0f}kg")
                lines.append("AFTBURNR TRUE")
            else:
                lines.append("AFTBURNR FALSE")

        lines.extend([
            f"FUELMILI {self.fuelmili:.4f}kg",
            "",
            "# Weights and Balance",
            f"WEIGHCLN {self.weighcln:.2f}t",
            f"WEIGFUEL {self.weigfuel:.2f}t",
            f"WEIGLOAD {self.weigload:.2f}t",
            f"INITFUEL {int(self.initfuel * 100)}%",
            f"INITLOAD {self.initload:.2f}t",
            "",
            "# Aerodynamics",
            f"WINGAREA {self.wingarea:.2f}m^2",
            f"CRITAOAP {self.critaoap:.1f}deg",
            f"CRITAOAM {self.critaoam:.1f}deg",
            f"CRITSPED {self.critsped_kmh:.0f}km/h",
            f"MAXSPEED {self.maxspeed_kmh:.0f}km/h",
            f"MANESPD1 {self.manespd1_kmh:.0f}km/h",
            f"MANESPD2 {self.manespd2_kmh:.0f}km/h",
            f"CLBYFLAP {self.clbyflap:.2f}",
            f"CDBYFLAP {self.cdbyflap:.2f}",
            f"CDBYGEAR {self.cdbygear:.2f}",
            f"CDSPOILR {self.cdspoilr:.2f}",
            f"CPITMANE {self.cpitmane:.1f}",
            f"CPITSTAB {self.cpitstab:.1f}",
            f"CYAWMANE {self.cyawmane:.1f}",
            f"CYAWSTAB {self.cyawstab:.1f}",
            f"CROLLMAN {self.crollman:.1f}",
            "",
            "# 3D Contact Points",
            f"COCKPITP {self.cockpitp.x:.2f}m {self.cockpitp.y:.2f}m {self.cockpitp.z:.2f}m",
            f"LEFTGEAR {self.leftgear.x:.2f}m {self.leftgear.y:.2f}m {self.leftgear.z:.2f}m",
            f"RIGHGEAR {self.righgear.x:.2f}m {self.righgear.y:.2f}m {self.righgear.z:.2f}m",
            f"WHELGEAR {self.whelgear.x:.2f}m {self.whelgear.y:.2f}m {self.whelgear.z:.2f}m",
            f"HTRADIUS {self.htradius:.1f}m",
            "",
            "# AI Cruise & Landing Reference",
            f"REFVCRUS {self.refvcrus_kmh:.0f}km/h",
            f"REFACRUS {self.refacrus_ft:.0f}ft",
            f"REFTCRUS {self.reftcrus:.2f}",
            f"REFVLAND {self.refvland_kmh:.0f}km/h",
            f"REFAOALD {self.refaoald_deg:.1f}deg",
            f"REFLNRWY {self.reflnrwy_m:.0f}m",
            f"REFTHRLD {self.refthrld:.2f}",
            "",
            "AUTOCALC",
            "",
        ])

        return "\n".join(lines)


def parse_dat_text(text: str) -> DatFlightModel:
    """Parse YSFlight .dat text into a DatFlightModel instance."""
    model = DatFlightModel()
    lines = text.splitlines()

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or line.upper().startswith("REM"):
            continue

        # Strip inline comments (#...)
        if "#" in line:
            line = line.split("#")[0].strip()

        tokens = line.split()
        if not tokens:
            continue

        cmd = tokens[0].upper()

        if cmd == "IDENTIFY":
            match = re.search(r'IDENTIFY\s+"?([^"\n\r]+)"?', line, re.IGNORECASE)
            if match:
                model.identify = match.group(1).strip()
        elif cmd == "CATEGORY":
            if len(tokens) >= 2:
                model.category = tokens[1].upper()
        elif cmd == "AIRCLASS":
            if len(tokens) >= 2:
                model.airclass = tokens[1].upper()
        elif cmd == "STRENGTH":
            if len(tokens) >= 2:
                model.strength = int(tokens[1])
        elif cmd == "RADARCRS":
            if len(tokens) >= 2:
                model.radarcrs = parse_distance(tokens[1])
        elif cmd == "PROPELLR":
            if len(tokens) >= 2:
                hp_str = tokens[1].lower().replace("hp", "")
                model.propellr_hp = float(hp_str)
        elif cmd == "PROPEFCY":
            if len(tokens) >= 2:
                model.propefcy = float(tokens[1])
        elif cmd == "THRMILIT":
            if len(tokens) >= 2:
                model.thrmilit = parse_thrust(tokens[1])
        elif cmd == "THRAFTBN":
            if len(tokens) >= 2:
                model.thraftbn = parse_thrust(tokens[1])
        elif cmd == "AFTBURNR":
            if len(tokens) >= 2:
                model.aftburnr = tokens[1].upper() == "TRUE"
        elif cmd == "FUELMILI":
            if len(tokens) >= 2:
                model.fuelmili = parse_weight_ton(tokens[1]) * 1000.0
        elif cmd == "WEIGHCLN":
            if len(tokens) >= 2:
                model.weighcln = parse_weight_ton(tokens[1])
        elif cmd == "WEIGFUEL":
            if len(tokens) >= 2:
                model.weigfuel = parse_weight_ton(tokens[1])
        elif cmd == "WEIGLOAD":
            if len(tokens) >= 2:
                model.weigload = parse_weight_ton(tokens[1])
        elif cmd == "INITFUEL":
            if len(tokens) >= 2:
                pct = tokens[1].replace("%", "")
                model.initfuel = float(pct) / 100.0
        elif cmd == "INITLOAD":
            if len(tokens) >= 2:
                model.initload = parse_weight_ton(tokens[1])
        elif cmd == "WINGAREA":
            if len(tokens) >= 2:
                model.wingarea = parse_distance(tokens[1])
        elif cmd == "CRITAOAP":
            if len(tokens) >= 2:
                model.critaoap = parse_angle_deg(tokens[1])
        elif cmd == "CRITAOAM":
            if len(tokens) >= 2:
                model.critaoam = parse_angle_deg(tokens[1])
        elif cmd == "CRITSPED":
            if len(tokens) >= 2:
                model.critsped_kmh = parse_speed_kmh(tokens[1])
        elif cmd == "MAXSPEED":
            if len(tokens) >= 2:
                model.maxspeed_kmh = parse_speed_kmh(tokens[1])
        elif cmd == "MANESPD1":
            if len(tokens) >= 2:
                model.manespd1_kmh = parse_speed_kmh(tokens[1])
        elif cmd == "MANESPD2":
            if len(tokens) >= 2:
                model.manespd2_kmh = parse_speed_kmh(tokens[1])
        elif cmd == "CLBYFLAP":
            if len(tokens) >= 2:
                model.clbyflap = float(tokens[1])
        elif cmd == "CDBYFLAP":
            if len(tokens) >= 2:
                model.cdbyflap = float(tokens[1])
        elif cmd == "CDBYGEAR":
            if len(tokens) >= 2:
                model.cdbygear = float(tokens[1])
        elif cmd in ("CDSPOILR", "CDBYSPOI"):
            if len(tokens) >= 2:
                model.cdspoilr = float(tokens[1])
        elif cmd == "CPITMANE":
            if len(tokens) >= 2:
                model.cpitmane = float(tokens[1])
        elif cmd == "CPITSTAB":
            if len(tokens) >= 2:
                model.cpitstab = float(tokens[1])
        elif cmd == "CYAWMANE":
            if len(tokens) >= 2:
                model.cyawmane = float(tokens[1])
        elif cmd == "CYAWSTAB":
            if len(tokens) >= 2:
                model.cyawstab = float(tokens[1])
        elif cmd == "CROLLMAN":
            if len(tokens) >= 2:
                model.crollman = float(tokens[1])
        elif cmd == "COCKPITP":
            if len(tokens) >= 4:
                model.cockpitp = Vector3Dat(
                    x=parse_distance(tokens[1]),
                    y=parse_distance(tokens[2]),
                    z=parse_distance(tokens[3]),
                )
        elif cmd == "LEFTGEAR":
            if len(tokens) >= 4:
                model.leftgear = Vector3Dat(
                    x=parse_distance(tokens[1]),
                    y=parse_distance(tokens[2]),
                    z=parse_distance(tokens[3]),
                )
        elif cmd == "RIGHGEAR":
            if len(tokens) >= 4:
                model.righgear = Vector3Dat(
                    x=parse_distance(tokens[1]),
                    y=parse_distance(tokens[2]),
                    z=parse_distance(tokens[3]),
                )
        elif cmd in ("WHELGEAR", "NOSEGEAR"):
            if len(tokens) >= 4:
                model.whelgear = Vector3Dat(
                    x=parse_distance(tokens[1]),
                    y=parse_distance(tokens[2]),
                    z=parse_distance(tokens[3]),
                )
        elif cmd == "HTRADIUS":
            if len(tokens) >= 2:
                model.htradius = parse_distance(tokens[1])
        elif cmd == "REFVCRUS":
            if len(tokens) >= 2:
                model.refvcrus_kmh = parse_speed_kmh(tokens[1])
        elif cmd == "REFACRUS":
            if len(tokens) >= 2:
                model.refacrus_ft = parse_distance(tokens[1]) / 0.3048
        elif cmd == "REFTCRUS":
            if len(tokens) >= 2:
                model.reftcrus = float(tokens[1])
        elif cmd == "REFVLAND":
            if len(tokens) >= 2:
                model.refvland_kmh = parse_speed_kmh(tokens[1])
        elif cmd == "REFAOALD":
            if len(tokens) >= 2:
                model.refaoald_deg = parse_angle_deg(tokens[1])
        elif cmd == "REFLNRWY":
            if len(tokens) >= 2:
                model.reflnrwy_m = parse_distance(tokens[1])
        elif cmd == "REFTHRLD":
            if len(tokens) >= 2:
                model.refthrld = float(tokens[1])
        else:
            model.raw_properties[cmd] = tokens[1:]

    return model


def parse_dat_file(filepath: str | Path) -> DatFlightModel:
    """Read and parse a .dat flight dynamics file from filesystem."""
    path = Path(filepath)
    content = path.read_text(encoding="utf-8", errors="replace")
    return parse_dat_text(content)


def write_dat_file(model: DatFlightModel, filepath: str | Path) -> None:
    """Serialize and write a DatFlightModel to file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.to_dat_text(), encoding="utf-8")


def parse_lst_text(text: str) -> list[str]:
    """Parse local aircraft .lst manifest file into list of relative filepaths."""
    entries: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Split tokens on the same line if multiple paths are present
        tokens = line.split()
        entries.extend(tokens)
    return entries


def write_lst_text(
    dat_rel_path: str,
    dnm_rel_path: str,
    coll_srf_rel_path: str | None = None,
    cockpit_srf_rel_path: str | None = None,
) -> str:
    """Generate content for aircraft local .lst manifest."""
    lines = [dat_rel_path, dnm_rel_path]
    if coll_srf_rel_path:
        lines.append(coll_srf_rel_path)
    if cockpit_srf_rel_path:
        lines.append(cockpit_srf_rel_path)
    return "\n".join(lines) + "\n"

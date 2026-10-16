"""Dimensional Metric Calibrator and Coordinate Transformation Engine.

Converts 2D orthographic pixel measurements into 3D metric world coordinates (meters)
in the YSFlight left-handed coordinate convention:
  +X: Right / Starboard (meters)
  +Y: Dorsal / Up (meters)
  +Z: Longitudinal / Nose forward (meters)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.cv.axis_detector import AircraftBlueprintAxes


@dataclass
class AircraftDimensions:
    wingspan_m: float  # Physical wingspan in meters
    length_m: float  # Physical length from nose to tail in meters
    height_m: float | None = None  # Optional physical height in meters


@dataclass
class CalibrationResult:
    pixels_per_meter: float
    wingspan_px: float
    length_px: float
    origin_top_px: tuple[float, float]  # (pixel_x_for_Z0, pixel_y_for_X0)
    origin_front_px: tuple[float, float]  # (pixel_x_for_X0, pixel_y_for_Y0)
    origin_side_px: tuple[float, float]  # (pixel_x_for_Z0, pixel_y_for_Y0)

    def top_pixel_to_world(self, px: float, py: float) -> tuple[float, float]:
        """Convert top view pixel coordinates to world (X_meters, Z_meters)."""
        z0_px, x0_px = self.origin_top_px
        # Horizontal top view: nose points left (+Z), tail points right (-Z)
        # Y axis: right wing points up (+X), left wing points down (-X)
        z_m = (z0_px - px) / self.pixels_per_meter
        x_m = (x0_px - py) / self.pixels_per_meter
        return (x_m, z_m)

    def front_pixel_to_world(self, px: float, py: float) -> tuple[float, float]:
        """Convert front view pixel coordinates to world (X_meters, Y_meters)."""
        x0_px, y0_px = self.origin_front_px
        x_m = (px - x0_px) / self.pixels_per_meter
        y_m = (y0_px - py) / self.pixels_per_meter
        return (x_m, y_m)

    def side_pixel_to_world(self, px: float, py: float) -> tuple[float, float]:
        """Convert side view pixel coordinates to world (Z_meters, Y_meters)."""
        z0_px, y0_px = self.origin_side_px
        # Nose points left (+Z), tail points right (-Z)
        z_m = (z0_px - px) / self.pixels_per_meter
        y_m = (y0_px - py) / self.pixels_per_meter
        return (z_m, y_m)


class BlueprintCalibrator:
    def __init__(self, primary_dimension: str = "wingspan"):
        self.primary_dimension = primary_dimension

    def calibrate(
        self,
        axes: AircraftBlueprintAxes,
        specs: AircraftDimensions,
    ) -> CalibrationResult:
        """
        Calibrate pixel-to-meter scale using known physical dimensions.
        Calculates origin alignment offsets across all 3 orthographic views.
        """
        # Determine scale (pixels per meter)
        if self.primary_dimension == "wingspan" and axes.wingspan_px > 0 and specs.wingspan_m > 0:
            ppm = axes.wingspan_px / specs.wingspan_m
        elif axes.length_px > 0 and specs.length_m > 0:
            ppm = axes.length_px / specs.length_m
        else:
            ppm = 50.0  # Safe default (50 px = 1 m)

        # 1. Top view origin (where X=0, Z=0)
        # Z=0 is chosen as the longitudinal aerodynamic center (approx 40% chord from nose)
        top_y_center = axes.top.centerline_px if axes.top else 0.0
        top_nose_x = axes.top.nose_px if axes.top and axes.top.nose_px is not None else 0.0
        top_tail_x = axes.top.tail_px if axes.top and axes.top.tail_px is not None else (top_nose_x + axes.length_px)
        # Reference Z=0 at mid-fuselage / 40% from nose
        top_z0_x = top_nose_x + (top_tail_x - top_nose_x) * 0.40
        origin_top = (top_z0_x, top_y_center)

        # 2. Front view origin (where X=0, Y=0)
        front_x_center = axes.front.centerline_px if axes.front else 0.0
        front_y_thrust = axes.front.thrustline_px if axes.front and axes.front.thrustline_px else 0.0
        origin_front = (front_x_center, front_y_thrust)

        # 3. Side view origin (where Z=0, Y=0)
        side_nose_x = axes.side.nose_px if axes.side and axes.side.nose_px is not None else 0.0
        side_tail_x = axes.side.tail_px if axes.side and axes.side.tail_px is not None else (side_nose_x + axes.length_px)
        side_z0_x = side_nose_x + (side_tail_x - side_nose_x) * 0.40
        side_y_thrust = axes.side.thrustline_px if axes.side and axes.side.thrustline_px else 0.0
        origin_side = (side_z0_x, side_y_thrust)

        return CalibrationResult(
            pixels_per_meter=ppm,
            wingspan_px=axes.wingspan_px,
            length_px=axes.length_px,
            origin_top_px=origin_top,
            origin_front_px=origin_front,
            origin_side_px=origin_side,
        )

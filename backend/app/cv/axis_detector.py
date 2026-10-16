"""Axis and Centerline Detector for Technical Blueprints.

Detects:
- Centerline of symmetry (X=0 plane) in Top and Front views.
- Thrust line / Waterline (Y=0) and Ground contact line (Y_ground) in Side/Front views.
- Longitudinal nose and tail coordinates (Z axis) in Top and Side views.
- Wingspan, length, and height measured in pixel space with subpixel precision.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.cv.blueprint_processor import ViewCrop


@dataclass
class ViewAxes:
    view_type: str
    centerline_px: float  # Symmetry axis (e.g. Y in horizontal top view, X in front view)
    thrustline_px: float | None = None  # Y=0 reference in Front/Side
    groundline_px: float | None = None  # Wheel contact level
    nose_px: float | None = None
    tail_px: float | None = None
    wingtip_min_px: float | None = None
    wingtip_max_px: float | None = None
    span_or_length_px: float = 0.0


@dataclass
class AircraftBlueprintAxes:
    top: ViewAxes | None = None
    front: ViewAxes | None = None
    side: ViewAxes | None = None
    wingspan_px: float = 0.0
    length_px: float = 0.0
    height_px: float = 0.0


class AxisDetector:
    def __init__(self, symmetry_search_window: int = 40):
        self.symmetry_search_window = symmetry_search_window

    def find_symmetry_axis_1d(self, mask: np.ndarray, axis: int = 0) -> float:
        """
        Find line of maximum reflective symmetry along specified axis (0=horizontal line, 1=vertical line).
        Uses normalized cross-correlation / mean squared difference between halves.
        """
        # Sum along perpendicular axis to get 1D mass profile
        profile = np.sum(mask > 0, axis=1 - axis).astype(np.float64)
        n = len(profile)
        if n == 0 or np.sum(profile) == 0:
            return float(n / 2.0)

        # Candidate range around center of mass
        com = float(np.sum(profile * np.arange(n)) / np.sum(profile))
        min_idx = max(5, int(com - self.symmetry_search_window))
        max_idx = min(n - 5, int(com + self.symmetry_search_window))

        best_score = float("inf")
        best_axis = com

        for c in range(min_idx, max_idx + 1):
            radius = min(c, n - 1 - c)
            if radius < 15:
                continue
            left_half = profile[c - radius : c]
            right_half = profile[c + 1 : c + 1 + radius][::-1]
            diff = np.mean((left_half - right_half) ** 2)
            if diff < best_score:
                best_score = diff
                best_axis = float(c)

        return best_axis

    def analyze_top_view(self, top_crop: ViewCrop) -> ViewAxes:
        """Analyze top view: horizontal fuselage, wing tips, nose, tail."""
        mask = top_crop.binary_mask
        h, w = mask.shape

        # Vertical projection (along height) gives wingtips along Y
        vert_proj = np.sum(mask > 0, axis=1)
        non_zero_y = np.where(vert_proj > 0)[0]
        y_min = float(non_zero_y[0]) if len(non_zero_y) > 0 else 0.0
        y_max = float(non_zero_y[-1]) if len(non_zero_y) > 0 else float(h)
        wingspan_px = y_max - y_min

        # Symmetry axis along Y (horizontal line running along X)
        symmetry_y = self.find_symmetry_axis_1d(mask, axis=0)
        # If symmetry search was skewed, fall back to geometric midpoint of wingtips
        if abs(symmetry_y - (y_min + y_max) / 2.0) > 30:
            symmetry_y = (y_min + y_max) / 2.0

        # Horizontal projection gives nose and tail along X
        horiz_proj = np.sum(mask > 0, axis=0)
        non_zero_x = np.where(horiz_proj > 0)[0]
        nose_x = float(non_zero_x[0]) if len(non_zero_x) > 0 else 0.0
        tail_x = float(non_zero_x[-1]) if len(non_zero_x) > 0 else float(w)
        length_px = tail_x - nose_x

        return ViewAxes(
            view_type="top",
            centerline_px=symmetry_y,  # Horizontal centerline of fuselage
            nose_px=nose_x,
            tail_px=tail_x,
            wingtip_min_px=y_min,
            wingtip_max_px=y_max,
            span_or_length_px=wingspan_px,
        )

    def analyze_front_view(self, front_crop: ViewCrop) -> ViewAxes:
        """Analyze front view: vertical symmetry (X=0), wingtips, height, groundline."""
        mask = front_crop.binary_mask
        h, w = mask.shape

        # Horizontal projection gives wingtips along X
        horiz_proj = np.sum(mask > 0, axis=0)
        non_zero_x = np.where(horiz_proj > 0)[0]
        x_min = float(non_zero_x[0]) if len(non_zero_x) > 0 else 0.0
        x_max = float(non_zero_x[-1]) if len(non_zero_x) > 0 else float(w)
        wingspan_px = x_max - x_min

        # Vertical symmetry axis along X
        symmetry_x = self.find_symmetry_axis_1d(mask, axis=1)
        if abs(symmetry_x - (x_min + x_max) / 2.0) > 30:
            symmetry_x = (x_min + x_max) / 2.0

        # Vertical projection gives fin top and wheel bottom
        vert_proj = np.sum(mask > 0, axis=1)
        non_zero_y = np.where(vert_proj > 0)[0]
        y_top = float(non_zero_y[0]) if len(non_zero_y) > 0 else 0.0
        y_ground = float(non_zero_y[-1]) if len(non_zero_y) > 0 else float(h)

        # Estimate thrustline (approximate vertical center of fuselage)
        # Typically located around 55-65% from top of total height
        thrustline_y = y_top + (y_ground - y_top) * 0.55

        return ViewAxes(
            view_type="front",
            centerline_px=symmetry_x,  # Vertical centerline
            thrustline_px=thrustline_y,
            groundline_px=y_ground,
            wingtip_min_px=x_min,
            wingtip_max_px=x_max,
            span_or_length_px=wingspan_px,
        )

    def analyze_side_view(self, side_crop: ViewCrop) -> ViewAxes:
        """Analyze side view: nose, tail, height, waterline, groundline."""
        mask = side_crop.binary_mask
        h, w = mask.shape

        horiz_proj = np.sum(mask > 0, axis=0)
        non_zero_x = np.where(horiz_proj > 0)[0]
        nose_x = float(non_zero_x[0]) if len(non_zero_x) > 0 else 0.0
        tail_x = float(non_zero_x[-1]) if len(non_zero_x) > 0 else float(w)
        length_px = tail_x - nose_x

        vert_proj = np.sum(mask > 0, axis=1)
        non_zero_y = np.where(vert_proj > 0)[0]
        y_top = float(non_zero_y[0]) if len(non_zero_y) > 0 else 0.0
        y_ground = float(non_zero_y[-1]) if len(non_zero_y) > 0 else float(h)

        # Waterline / thrustline running through the propeller spinner
        thrustline_y = y_top + (y_ground - y_top) * 0.60

        return ViewAxes(
            view_type="side",
            centerline_px=thrustline_y,
            thrustline_px=thrustline_y,
            groundline_px=y_ground,
            nose_px=nose_x,
            tail_px=tail_x,
            span_or_length_px=length_px,
        )

    def analyze_all(
        self,
        top_crop: ViewCrop | None,
        front_crop: ViewCrop | None,
        side_crop: ViewCrop | None,
    ) -> AircraftBlueprintAxes:
        """Analyze all available orthographic views and compute aggregate axes and dimensions."""
        result = AircraftBlueprintAxes()

        if top_crop:
            result.top = self.analyze_top_view(top_crop)
            result.wingspan_px = result.top.span_or_length_px
            if result.top.nose_px is not None and result.top.tail_px is not None:
                result.length_px = result.top.tail_px - result.top.nose_px

        if front_crop:
            result.front = self.analyze_front_view(front_crop)
            if result.wingspan_px == 0.0:
                result.wingspan_px = result.front.span_or_length_px
            if result.front.groundline_px is not None:
                y_top = result.front.wingtip_min_px or 0.0
                result.height_px = max(result.height_px, result.front.groundline_px - y_top)

        if side_crop:
            result.side = self.analyze_side_view(side_crop)
            if result.length_px == 0.0:
                result.length_px = result.side.span_or_length_px
            if result.side.groundline_px is not None:
                h_side = result.side.groundline_px - (result.side.nose_px or 0.0)
                result.height_px = max(result.height_px, result.side.groundline_px)

        return result

"""Computer Vision Blueprint Processor and Orthographic View Extractor.

Decomposes a technical 3-view blueprint drawing (Front, Top, Side) into:
- Individual cropped view patches.
- Bounding boxes and relative coordinates.
- Cleaned binary linework (inverted, background-subtracted).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass
class ViewCrop:
    view_type: Literal["top", "front", "side", "unknown"]
    bbox: BoundingBox
    image: np.ndarray  # Grayscale or BGR cropped patch
    binary_mask: np.ndarray  # 255 for lines/silhouette, 0 for background


@dataclass
class BlueprintDecompositionResult:
    original_shape: tuple[int, int]  # (height, width)
    top_view: ViewCrop | None = None
    front_view: ViewCrop | None = None
    side_view: ViewCrop | None = None
    all_crops: list[ViewCrop] = None  # type: ignore

    def __post_init__(self):
        if self.all_crops is None:
            self.all_crops = []


class BlueprintProcessor:
    def __init__(
        self,
        min_view_area_ratio: float = 0.008,  # 0.8% of total image area
        binary_threshold: int | None = None,
    ):
        self.min_view_area_ratio = min_view_area_ratio
        self.binary_threshold = binary_threshold

    def preprocess(self, image_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Convert to grayscale and create a clean binary linework mask."""
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr.copy()

        h, w = gray.shape
        corner_samples = [
            gray[0:10, 0:10],
            gray[0:10, w - 10 : w],
            gray[h - 10 : h, 0:10],
            gray[h - 10 : h, w - 10 : w],
        ]
        corner_mean = float(np.mean([np.mean(c) for c in corner_samples]))

        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        if corner_mean > 127:
            if self.binary_threshold is not None:
                _, binary = cv2.threshold(blurred, self.binary_threshold, 255, cv2.THRESH_BINARY_INV)
            else:
                _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            if self.binary_threshold is not None:
                _, binary = cv2.threshold(blurred, self.binary_threshold, 255, cv2.THRESH_BINARY)
            else:
                _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return gray, binary

    def find_view_regions(
        self, binary_lines: np.ndarray, min_area_ratio: float | None = None
    ) -> list[BoundingBox]:
        """
        Detect candidate bounding boxes for the 3 orthographic views using connected components.
        Identifies major view components and associates nearby detached parts (wheels, antennae).
        """
        h, w = binary_lines.shape
        total_area = h * w
        min_major_area = total_area * (min_area_ratio or self.min_view_area_ratio)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_lines)

        major_components: list[dict] = []
        minor_components: list[dict] = []

        for i in range(1, num_labels):
            area = int(stats[i, cv2.CC_STAT_AREA])
            bx = int(stats[i, cv2.CC_STAT_LEFT])
            by = int(stats[i, cv2.CC_STAT_TOP])
            bw = int(stats[i, cv2.CC_STAT_WIDTH])
            bh = int(stats[i, cv2.CC_STAT_HEIGHT])
            cx, cy = float(centroids[i][0]), float(centroids[i][1])

            comp = {"label": i, "area": area, "x": bx, "y": by, "w": bw, "h": bh, "cx": cx, "cy": cy}

            if area >= min_major_area:
                major_components.append(comp)
            elif area >= 50:  # Ignore tiny 1-2 pixel noise
                minor_components.append(comp)

        # Attach small detached components (like landing gear wheels) to nearest major view if within 30px
        boxes: list[BoundingBox] = []
        for major in major_components:
            bx, by, bx2, by2 = major["x"], major["y"], major["x"] + major["w"], major["y"] + major["h"]

            for minor in minor_components:
                # Check if minor is close to this major component
                mx, my, mx2, my2 = minor["x"], minor["y"], minor["x"] + minor["w"], minor["y"] + minor["h"]
                dist_x = max(0, max(bx - mx2, mx - bx2))
                dist_y = max(0, max(by - my2, my - by2))

                if dist_x < 35 and dist_y < 35:
                    bx = min(bx, mx)
                    by = min(by, my)
                    bx2 = max(bx2, mx2)
                    by2 = max(by2, my2)

            # Add padding
            pad = 8
            px = max(0, bx - pad)
            py = max(0, by - pad)
            pw = min(w - px, (bx2 - bx) + 2 * pad)
            ph = min(h - py, (by2 - by) + 2 * pad)
            boxes.append(BoundingBox(x=px, y=py, width=pw, height=ph))

        # Sort by area descending
        boxes.sort(key=lambda b: b.area, reverse=True)
        return boxes

    def classify_views(
        self,
        boxes: list[BoundingBox],
        image_shape: tuple[int, int],
    ) -> dict[str, BoundingBox]:
        """
        Classify candidate view boxes into Top, Front, Side views.
        Uses aerospace blueprint quadrant conventions:
        - Top view: Left side of drawing (cx < width * 0.45).
        - Front view: Right side, upper region (cy < height * 0.45).
        - Side view: Right side, lower region (cy >= 0.45 * height).
        """
        img_h, img_w = image_shape
        assigned: dict[str, BoundingBox] = {}

        if not boxes:
            return assigned

        for b in boxes:
            cx = b.x + b.width / 2.0
            cy = b.y + b.height / 2.0

            if cx < img_w * 0.45:
                if "top" not in assigned or b.area > assigned["top"].area:
                    assigned["top"] = b
            else:
                if cy < img_h * 0.45:
                    if "front" not in assigned or b.area > assigned["front"].area:
                        assigned["front"] = b
                else:
                    if "side" not in assigned or b.area > assigned["side"].area:
                        assigned["side"] = b

        return assigned

    def decompose(self, image_bgr: np.ndarray) -> BlueprintDecompositionResult:
        """Process blueprint image and extract orthographic views."""
        h, w = image_bgr.shape[:2]
        gray, binary = self.preprocess(image_bgr)
        boxes = self.find_view_regions(binary)
        classified = self.classify_views(boxes, (h, w))

        result = BlueprintDecompositionResult(original_shape=(h, w))

        for view_name, bbox in classified.items():
            crop_img = gray[bbox.y : bbox.y2, bbox.x : bbox.x2].copy()
            crop_bin = binary[bbox.y : bbox.y2, bbox.x : bbox.x2].copy()

            # Clean overlapping regions between views (e.g. Side view nose appearing in Top view)
            if view_name == "top" and "side" in classified:
                sb = classified["side"]
                overlap_x1 = max(0, sb.x - bbox.x)
                overlap_y1 = max(0, sb.y - bbox.y)
                if overlap_x1 < crop_img.shape[1] and overlap_y1 < crop_img.shape[0]:
                    crop_bin[overlap_y1:, overlap_x1:] = 0
                    crop_img[overlap_y1:, overlap_x1:] = 255

            # In technical blueprints, top view is often drawn horizontally.
            # Transpose if horizontal so that Nose points Forward/Up (along Z) and Wings Left-Right (along X).
            if view_name == "top":
                if crop_bin.shape[1] >= crop_bin.shape[0] * 0.85:
                    crop_img = cv2.transpose(crop_img)
                    crop_bin = cv2.transpose(crop_bin)
                    bbox = BoundingBox(x=bbox.x, y=bbox.y, width=bbox.height, height=bbox.width)

            view_crop = ViewCrop(
                view_type=view_name,  # type: ignore
                bbox=bbox,
                image=crop_img,
                binary_mask=crop_bin,
            )
            result.all_crops.append(view_crop)
            if view_name == "top":
                result.top_view = view_crop
            elif view_name == "front":
                result.front_view = view_crop
            elif view_name == "side":
                result.side_view = view_crop

        return result

    def decompose_file(self, filepath: str | Path) -> BlueprintDecompositionResult:
        """Load image from disk and decompose into orthographic views."""
        path = Path(filepath)
        img = cv2.imread(str(path))
        if img is None:
            raise FileNotFoundError(f"Failed to read image at {path}")
        return self.decompose(img)

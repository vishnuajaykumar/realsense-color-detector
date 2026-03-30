"""
Detection pipeline use case. Orchestrates domain logic.
No ROS imports allowed here.
"""
from typing import List, Optional
import numpy as np
from collections import deque

from ..domain.cube_detector import CubeDetector
from ..domain.color_detector import _sample_depth_fallback
from ..domain.models import (
    BoundingBox,
    CameraIntrinsics,
    DetectedObject,
    Point3D,
)


class DetectionPipeline:
    """
    Runs YOLOv8 cube detection then samples aligned depth for each bbox.
    """

    def __init__(
        self,
        model_path: str,
        confidence: float = 0.40,
        depth_scale: float = 0.001,
        min_depth_m: float = 0.1,
        max_depth_m: float = 4.0,
        imgsz: int = 416,
    ):
        self._detector = CubeDetector(model_path=model_path, confidence=confidence)
        self.confidence  = confidence
        self.depth_scale = depth_scale
        self.min_depth_m = min_depth_m
        self.max_depth_m = max_depth_m
        self._imgsz = imgsz
        
        # --- Calibration state ---
        self.is_calibrated = False
        self.REQUIRED_STABILITY = 0.8  # 80% detection rate
        self.WINDOW_SIZE       = 30   # last 30 frames
        self._history          = deque(maxlen=self.WINDOW_SIZE)
        self.CALIBRATION_LABELS = {
            "red": {"Red Cube", "Red", "Red Object"},
            "green": {"Green Cube", "Green", "Green Object"},
            "blue": {"Blue Cube", "Blue", "Blue Object"}
        }
        self.MIN_COLORS_REQUIRED = 1 # Allow 1 color for immediate readiness

    def run(
        self,
        color_image: np.ndarray,
        depth_image: np.ndarray,
        intrinsics: CameraIntrinsics,
    ) -> List[DetectedObject]:

        raw = self._detector.detect(color_image, imgsz=self._imgsz)
        results: List[DetectedObject] = []

        for label, conf, bx, by, bw, bh in raw:
            bbox = BoundingBox(x=bx, y=by, w=bw, h=bh)
            cx, cy = bbox.center

            # Sample depth inside the bounding box region
            depth_m = _depth_from_bbox(
                depth_image, bx, by, bw, bh,
                self.depth_scale, self.min_depth_m, self.max_depth_m,
            )
            if depth_m is None:
                depth_m = _sample_depth_fallback(
                    depth_image, cx, cy,
                    self.depth_scale, self.min_depth_m, self.max_depth_m,
                )
            if depth_m is None:
                continue

            x = (cx - intrinsics.cx) * depth_m / intrinsics.fx
            y = (cy - intrinsics.cy) * depth_m / intrinsics.fy
            position = Point3D(x=x, y=y, z=depth_m)

            print(f"[DEBUG] {label}: {conf:.2f}")
            results.append(DetectedObject(
                label=label,
                distance_m=depth_m,
                bbox=bbox,
                position_3d=position,
            ))

        # --- Update Calibration Statemachine ---
        if not self.is_calibrated:
            current_labels = {d.label for d in results}
            if current_labels:
                print(f"[DEBUG] Labels: {current_labels}")
            
            # Check if we have at least one valid match for each required color
            matches = {
                color for color, alternatives in self.CALIBRATION_LABELS.items()
                if alternatives.intersection(current_labels)
            }
            success = len(matches) >= self.MIN_COLORS_REQUIRED
            self._history.append(success)
            
            if len(self._history) == self.WINDOW_SIZE:
                stability = sum(self._history) / self.WINDOW_SIZE
                if stability >= self.REQUIRED_STABILITY:
                    self.is_calibrated = True
                    # Transition logic: Expand classes (handled by node)

        return results

    def get_calibration_status(self) -> str:
        """Return a string describing the current calibration status."""
        if self.is_calibrated:
            return "READY"
        
        count = sum(self._history)
        total = self.WINDOW_SIZE
        progress = (count / total) * 100 if total > 0 else 0
        return f"CALIBRATING: {count}/{total} ({progress:.0f}%)"


def _depth_from_bbox(
    depth_image: np.ndarray,
    bx: int, by: int, bw: int, bh: int,
    depth_scale: float,
    min_depth_m: float,
    max_depth_m: float,
) -> Optional[float]:
    """Median of valid depth pixels within the bounding box."""
    h, w = depth_image.shape[:2]
    x0 = max(bx, 0)
    y0 = max(by, 0)
    x1 = min(bx + bw, w)
    y1 = min(by + bh, h)
    roi = depth_image[y0:y1, x0:x1].astype(np.float32) * depth_scale
    valid = roi[(roi >= min_depth_m) & (roi <= max_depth_m)]
    return float(np.median(valid)) if valid.size > 0 else None

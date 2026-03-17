"""
HSV-based color segmentation. No ROS imports allowed here.
"""
from typing import List, Optional
import cv2
import numpy as np

from .models import BoundingBox, ColorProfile, DetectedObject, HsvRange, Point3D, CameraIntrinsics


def _build_mask(hsv_image: np.ndarray, ranges: List[HsvRange]) -> np.ndarray:
    mask = np.zeros(hsv_image.shape[:2], dtype=np.uint8)
    for r in ranges:
        lo = np.array([r.h_low, r.s_low, r.v_low], dtype=np.uint8)
        hi = np.array([r.h_high, r.s_high, r.v_high], dtype=np.uint8)
        mask |= cv2.inRange(hsv_image, lo, hi)
    return mask


def _sample_depth(depth_image: np.ndarray, cx: int, cy: int, window: int = 5) -> Optional[float]:
    """Sample median depth in a small window around (cx, cy). Returns meters or None."""
    h, w = depth_image.shape[:2]
    x0 = max(cx - window, 0)
    x1 = min(cx + window, w - 1)
    y0 = max(cy - window, 0)
    y1 = min(cy + window, h - 1)
    region = depth_image[y0:y1, x0:x1]
    valid = region[region > 0]
    if valid.size == 0:
        return None
    # RealSense depth is in millimetres (uint16); convert to metres
    return float(np.median(valid)) / 1000.0


def _pixel_to_3d(px: int, py: int, depth_m: float, intrinsics: CameraIntrinsics) -> Point3D:
    x = (px - intrinsics.cx) * depth_m / intrinsics.fx
    y = (py - intrinsics.cy) * depth_m / intrinsics.fy
    return Point3D(x=x, y=y, z=depth_m)


def detect_objects(
    color_image: np.ndarray,
    depth_image: np.ndarray,
    color_profiles: List[ColorProfile],
    intrinsics: CameraIntrinsics,
    min_contour_area: float = 500.0,
) -> List[DetectedObject]:
    """
    Run HSV segmentation for each color profile and return a list of DetectedObjects.

    Args:
        color_image:      BGR uint8 image from camera.
        depth_image:      uint16 depth image aligned to color frame (mm).
        color_profiles:   List of ColorProfile definitions (label + HSV ranges).
        intrinsics:       Camera intrinsic parameters.
        min_contour_area: Minimum contour area in pixels to accept.

    Returns:
        List of DetectedObject instances.
    """
    hsv = cv2.cvtColor(color_image, cv2.COLOR_BGR2HSV)
    results: List[DetectedObject] = []

    for profile in color_profiles:
        mask = _build_mask(hsv, profile.ranges)

        # Morphological clean-up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_contour_area:
                continue

            bx, by, bw, bh = cv2.boundingRect(contour)
            bbox = BoundingBox(x=bx, y=by, w=bw, h=bh)
            cx, cy = bbox.center

            depth_m = _sample_depth(depth_image, cx, cy)
            if depth_m is None or depth_m <= 0.0:
                continue

            position = _pixel_to_3d(cx, cy, depth_m, intrinsics)

            results.append(DetectedObject(
                label=profile.label,
                distance_m=depth_m,
                bbox=bbox,
                position_3d=position,
            ))

    return results

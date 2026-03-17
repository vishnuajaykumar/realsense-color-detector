"""
HSV-based color segmentation with contour-masked depth sampling.
No ROS imports allowed here.
"""
from typing import List, Optional, Tuple
import cv2
import numpy as np

from .models import BoundingBox, ColorProfile, DetectedObject, HsvRange, Point3D, CameraIntrinsics


def _build_mask(hsv_image: np.ndarray, ranges: List[HsvRange]) -> np.ndarray:
    mask = np.zeros(hsv_image.shape[:2], dtype=np.uint8)
    for r in ranges:
        lo = np.array([r.h_low,  r.s_low,  r.v_low],  dtype=np.uint8)
        hi = np.array([r.h_high, r.s_high, r.v_high], dtype=np.uint8)
        mask |= cv2.inRange(hsv_image, lo, hi)
    return mask


def _sample_depth_from_contour(
    depth_image: np.ndarray,
    contour: np.ndarray,
    depth_scale: float,
    min_depth_m: float,
    max_depth_m: float,
) -> Optional[float]:
    """
    Sample the median depth of all valid pixels *inside* the contour.

    Using the contour mask is far more robust than sampling a fixed window
    at the bounding-box centre, which can land on depth holes or background.

    Returns depth in metres, or None if no valid pixels are found.
    """
    h, w = depth_image.shape[:2]

    # Render contour into a binary mask (same size as depth image)
    contour_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(contour_mask, [contour], -1, 255, thickness=cv2.FILLED)

    # Extract depth values only inside the contour
    depth_vals = depth_image[contour_mask == 255].astype(np.float32)

    # Convert raw units → metres
    depth_vals_m = depth_vals * depth_scale

    # Keep only physically plausible depths for the D435i
    valid = depth_vals_m[(depth_vals_m >= min_depth_m) & (depth_vals_m <= max_depth_m)]

    if valid.size == 0:
        return None

    return float(np.median(valid))


def _sample_depth_fallback(
    depth_image: np.ndarray,
    cx: int,
    cy: int,
    depth_scale: float,
    min_depth_m: float,
    max_depth_m: float,
    window: int = 15,
) -> Optional[float]:
    """
    Fallback: median depth in a window around (cx, cy).
    Used when contour-based sampling returns None (e.g., structured-light shadow).
    """
    hh, ww = depth_image.shape[:2]
    x0, x1 = max(cx - window, 0), min(cx + window, ww - 1)
    y0, y1 = max(cy - window, 0), min(cy + window, hh - 1)
    region = depth_image[y0:y1, x0:x1].astype(np.float32) * depth_scale
    valid = region[(region >= min_depth_m) & (region <= max_depth_m)]
    return float(np.median(valid)) if valid.size > 0 else None


def _pixel_to_3d(
    px: int, py: int, depth_m: float, intrinsics: CameraIntrinsics
) -> Point3D:
    x = (px - intrinsics.cx) * depth_m / intrinsics.fx
    y = (py - intrinsics.cy) * depth_m / intrinsics.fy
    return Point3D(x=x, y=y, z=depth_m)


def detect_objects(
    color_image: np.ndarray,
    depth_image: np.ndarray,
    color_profiles: List[ColorProfile],
    intrinsics: CameraIntrinsics,
    min_contour_area: float = 500.0,
    depth_scale: float = 0.001,       # 1 mm per raw unit (D435i default)
    min_depth_m: float = 0.1,         # D435i minimum reliable range
    max_depth_m: float = 4.0,         # practical detection limit
) -> List[DetectedObject]:
    """
    Detect red/green/blue objects and measure their 3D distance.

    Depth is sampled from all pixels *inside* the detected contour using the
    aligned depth frame (guaranteed to be pixel-exact with the colour frame).
    A fallback window-median is tried when the contour region has no valid depth.

    Args:
        color_image:      BGR uint8 image from camera.
        depth_image:      uint16 depth image aligned to colour frame (raw units).
        color_profiles:   HSV colour profile definitions.
        intrinsics:       Camera intrinsic parameters from /camera_info.
        min_contour_area: Minimum contour area in px² to accept.
        depth_scale:      Raw-unit → metres multiplier (default 0.001 for mm).
        min_depth_m:      Minimum valid depth in metres.
        max_depth_m:      Maximum valid depth in metres.

    Returns:
        List of DetectedObject instances with accurate per-object distance.
    """
    hsv = cv2.cvtColor(color_image, cv2.COLOR_BGR2HSV)
    results: List[DetectedObject] = []

    for profile in color_profiles:
        mask = _build_mask(hsv, profile.ranges)

        # Morphological clean-up: remove noise, fill small holes
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,   kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_contour_area:
                continue

            bx, by, bw, bh = cv2.boundingRect(contour)
            bbox = BoundingBox(x=bx, y=by, w=bw, h=bh)
            cx, cy = bbox.center

            # Primary: sample depth inside the contour mask
            depth_m = _sample_depth_from_contour(
                depth_image, contour, depth_scale, min_depth_m, max_depth_m
            )

            # Fallback: wider window around centre if contour had no valid depth
            if depth_m is None:
                depth_m = _sample_depth_fallback(
                    depth_image, cx, cy, depth_scale, min_depth_m, max_depth_m
                )

            if depth_m is None:
                continue  # No usable depth for this contour — skip

            position = _pixel_to_3d(cx, cy, depth_m, intrinsics)

            results.append(DetectedObject(
                label=profile.label,
                distance_m=depth_m,
                bbox=bbox,
                position_3d=position,
            ))

    return results

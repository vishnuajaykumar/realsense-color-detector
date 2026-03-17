"""
Detection pipeline use case. Orchestrates domain logic.
No ROS imports allowed here.
"""
from typing import List, Optional
import numpy as np

from ..domain.color_detector import detect_objects
from ..domain.models import (
    CameraIntrinsics,
    ColorProfile,
    DetectedObject,
    HsvRange,
)


def build_default_color_profiles() -> List[ColorProfile]:
    """Returns default HSV color profiles for red, green, and blue."""
    return [
        ColorProfile(
            label="red",
            ranges=[
                HsvRange(h_low=0,   h_high=10,  s_low=100, s_high=255, v_low=100, v_high=255),
                HsvRange(h_low=160, h_high=180, s_low=100, s_high=255, v_low=100, v_high=255),
            ],
        ),
        ColorProfile(
            label="green",
            ranges=[
                HsvRange(h_low=40, h_high=80, s_low=80, s_high=255, v_low=80, v_high=255),
            ],
        ),
        ColorProfile(
            label="blue",
            ranges=[
                HsvRange(h_low=100, h_high=130, s_low=80, s_high=255, v_low=80, v_high=255),
            ],
        ),
    ]


class DetectionPipeline:
    """
    Stateless use case: given a colour image, depth image, intrinsics, and params,
    returns a list of DetectedObject instances with calibrated 3D distances.
    """

    def __init__(
        self,
        color_profiles: Optional[List[ColorProfile]] = None,
        min_contour_area: float = 500.0,
        depth_scale: float = 0.001,   # mm → m (D435i default)
        min_depth_m: float = 0.1,     # D435i minimum reliable range
        max_depth_m: float = 4.0,     # practical detection limit
    ):
        self.color_profiles = color_profiles or build_default_color_profiles()
        self.min_contour_area = min_contour_area
        self.depth_scale = depth_scale
        self.min_depth_m = min_depth_m
        self.max_depth_m = max_depth_m

    def run(
        self,
        color_image: np.ndarray,
        depth_image: np.ndarray,
        intrinsics: CameraIntrinsics,
    ) -> List[DetectedObject]:
        return detect_objects(
            color_image=color_image,
            depth_image=depth_image,
            color_profiles=self.color_profiles,
            intrinsics=intrinsics,
            min_contour_area=self.min_contour_area,
            depth_scale=self.depth_scale,
            min_depth_m=self.min_depth_m,
            max_depth_m=self.max_depth_m,
        )

    def update_profile_ranges(self, label: str, ranges: List[HsvRange]) -> None:
        for profile in self.color_profiles:
            if profile.label == label:
                profile.ranges = ranges
                return

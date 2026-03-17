"""
Domain data classes. No ROS imports allowed here.
"""
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class BoundingBox:
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)


@dataclass
class Point3D:
    x: float
    y: float
    z: float


@dataclass
class DetectedObject:
    label: str          # "red" | "green" | "blue"
    distance_m: float   # distance in meters
    bbox: BoundingBox
    position_3d: Point3D


@dataclass
class CameraIntrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int


@dataclass
class HsvRange:
    h_low: int
    h_high: int
    s_low: int
    s_high: int
    v_low: int
    v_high: int


@dataclass
class ColorProfile:
    label: str
    ranges: List[HsvRange] = field(default_factory=list)

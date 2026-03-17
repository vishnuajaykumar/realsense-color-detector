"""
Natural language query parsing. No ROS imports allowed here.
"""
from typing import List, Optional
from .models import DetectedObject

KNOWN_COLORS = ["red", "green", "blue"]


def parse_color_from_question(question: str) -> Optional[str]:
    q = question.lower()
    for color in KNOWN_COLORS:
        if color in q:
            return color
    return None


def answer_query(question: str, detections: List[DetectedObject]) -> str:
    color = parse_color_from_question(question)

    if color is None:
        # Generic: report everything visible
        if not detections:
            return "I don't see any colored objects right now."
        summary = ", ".join(
            f"a {d.label} cube at {d.distance_m:.2f}m" for d in detections
        )
        return f"I can see: {summary}."

    matches = [d for d in detections if d.label == color]

    if not matches:
        return f"No {color} cubes are currently detected."

    if len(matches) == 1:
        d = matches[0]
        return (
            f"Yes, I can see a {color} cube at {d.distance_m:.2f} meters "
            f"(3D position: x={d.position_3d.x:.3f}m, y={d.position_3d.y:.3f}m, z={d.position_3d.z:.3f}m)."
        )

    closest = min(matches, key=lambda d: d.distance_m)
    return (
        f"Yes, I can see {len(matches)} {color} cubes. "
        f"The closest is at {closest.distance_m:.2f} meters."
    )

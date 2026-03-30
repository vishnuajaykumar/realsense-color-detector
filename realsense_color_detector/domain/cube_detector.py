"""
YOLOv8-based cube detector.
Loads a trained YOLOv8n model and returns detected red/green/blue cubes
with their bounding boxes. Depth sampling is handled separately by the pipeline.
No ROS imports allowed here.
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np

# ultralytics is imported lazily so the node can start before the model loads
_yolo_cls = None


def _get_yolo():
    global _yolo_cls
    if _yolo_cls is None:
        import torch
        torch.set_num_threads(2)
        from ultralytics import YOLO  # type: ignore
        _yolo_cls = YOLO
    return _yolo_cls


# Maps model class names → our canonical labels
_CLASS_MAP = {
    'bluecube':  'blue',
    'blue cube': 'blue',
    'green cube': 'green',
    'greencube': 'green',
    'red cube':  'red',
    'redcube':   'red',
}


class CubeDetector:
    """
    Wraps a trained YOLOv8 model.  Call detect() with a BGR numpy array.
    """

    def __init__(self, model_path: str, confidence: float = 0.40):
        """
        Args:
            model_path:  Path to best.pt produced by YOLOv8 training.
            confidence:  Minimum detection confidence (0–1).
        """
        YOLO = _get_yolo()
        self._model = YOLO(model_path)
        if "world" in model_path.lower():
            # For YOLO-World models, we must set the classes to trigger zero-shot mode
            try:
                self._model.set_classes(["red cube", "green cube", "blue cube", "cube", "box", "block"])
            except Exception as e:
                print(f"[WARN] Could not set_classes on {model_path}: {e}")
        self.confidence_threshold = confidence

    def detect(
        self,
        bgr_image: np.ndarray,
        imgsz: int = 416,
    ) -> List[Tuple[str, float, int, int, int, int]]:
        """
        Run inference on a BGR image.

        Returns:
            List of (label, confidence, x, y, w, h) tuples where
            x, y is the top-left corner and w, h are width/height in pixels.
        """
        results = self._model(
            bgr_image,
            imgsz=imgsz,
            conf=self.confidence_threshold,
            device='cpu',
            verbose=False,
        )

        detections = []
        for r in results:
            if r.boxes is None:
                continue
            names = r.names
            for box in r.boxes:
                raw_cls = int(box.cls.item())
                cls_name = names[raw_cls].lower()
                conf = float(box.conf.item())
                
                # Use the model's native name for the class
                label = names.get(raw_cls, f"Class_{raw_cls}")
                label = label.title().replace("_", " ")

                if conf >= self.confidence_threshold:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    x, y = int(x1), int(y1)
                    w, h = int(x2 - x1), int(y2 - y1)
                    detections.append((label, conf, x, y, w, h))

        return detections

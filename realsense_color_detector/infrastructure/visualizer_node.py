"""
visualizer_node: Subscribes to /detections + synced colour + depth images.
Publishes:
  /detection_image   — colour image annotated with bounding boxes, labels, distance
  /detection_depth   — false-colour depth image with detections overlaid
  /detection_markers — visualization_msgs/MarkerArray (3D cubes) for RViz
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from visualization_msgs.msg import Marker, MarkerArray
from cv_bridge import CvBridge
import cv2
import numpy as np
from builtin_interfaces.msg import Duration
from message_filters import ApproximateTimeSynchronizer, Subscriber

from realsense_color_detector_msgs.msg import DetectedObjectArray


SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)

# BGR colours for drawing on colour image
COLOR_MAP = {
    'red':   (0,   0,   255),
    'green': (0,   220, 0  ),
    'blue':  (255, 80,  0  ),
}

# Normalised RGB for RViz markers
MARKER_COLOR_MAP = {
    'red':   (1.0, 0.0, 0.0),
    'green': (0.0, 1.0, 0.0),
    'blue':  (0.0, 0.4, 1.0),
}


def _colorize_depth(depth_img: np.ndarray, max_depth_mm: float = 4000.0) -> np.ndarray:
    """Convert raw uint16 depth (mm) to a false-colour BGR image."""
    depth_f = depth_img.astype(np.float32)
    depth_f = np.clip(depth_f, 0, max_depth_mm)
    depth_norm = (depth_f / max_depth_mm * 255).astype(np.uint8)
    # COLORMAP_JET: blue=close, red=far — intuitive for depth
    return cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)


class VisualizerNode(Node):
    def __init__(self):
        super().__init__('visualizer_node')

        self._bridge = CvBridge()
        self._latest_detections: DetectedObjectArray = None
        self._latest_depth_msg: Image = None

        # Subscribe to detections
        self._detections_sub = self.create_subscription(
            DetectedObjectArray, '/detections', self._on_detections, 10
        )

        # Async subscriptions instead of ApproximateTimeSynchronizer to prevent CPU starvation on LattePanda
        self._depth_sub = self.create_subscription(Image, '/camera/aligned_depth_to_color/image_raw', self._on_depth, SENSOR_QOS)
        self._color_sub = self.create_subscription(Image, '/camera/color/image_raw', self._on_color, SENSOR_QOS)

        self._image_pub   = self.create_publisher(Image,       '/detection_image',   10)
        self._depth_pub   = self.create_publisher(Image,       '/detection_depth',   10)
        self._markers_pub = self.create_publisher(MarkerArray, '/detection_markers', 10)

        self.get_logger().info('VisualizerNode ready.')

    def _on_detections(self, msg: DetectedObjectArray):
        self._latest_detections = msg
        self._publish_markers(msg)

    def _on_depth(self, msg: Image):
        self._latest_depth_msg = msg

    def _on_color(self, color_msg: Image):
        if self._latest_detections is None or self._latest_depth_msg is None:
            return

        color_cv = self._bridge.imgmsg_to_cv2(color_msg, desired_encoding='bgr8').copy()
        depth_cv = self._bridge.imgmsg_to_cv2(self._latest_depth_msg, desired_encoding='passthrough')

        # --- Annotated colour image ---
        self._draw_detections(color_cv, self._latest_detections)
        out_color = self._bridge.cv2_to_imgmsg(color_cv, encoding='bgr8')
        out_color.header = color_msg.header
        self._image_pub.publish(out_color)

        # --- False-colour depth image with detection overlays ---
        depth_bgr = _colorize_depth(depth_cv)
        self._draw_depth_overlays(depth_bgr, self._latest_detections)
        out_depth = self._bridge.cv2_to_imgmsg(depth_bgr, encoding='bgr8')
        out_depth.header = self._latest_depth_msg.header
        self._depth_pub.publish(out_depth)

    def _draw_detections(self, img: np.ndarray, detections: DetectedObjectArray):
        for obj in detections.objects:
            color = COLOR_MAP.get(obj.label, (255, 255, 255))
            x, y, w, h = obj.bbox_x, obj.bbox_y, obj.bbox_w, obj.bbox_h

            # Bounding box
            cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)

            # Crosshair at depth sample centre
            cx, cy = x + w // 2, y + h // 2
            cv2.drawMarker(img, (cx, cy), color,
                           markerType=cv2.MARKER_CROSS, markerSize=14,
                           thickness=2, line_type=cv2.LINE_AA)

            # Label: colour name + distance in metres and centimetres
            dist_cm = obj.distance_m * 100.0
            label_line1 = f'{obj.label.upper()}'
            label_line2 = f'{obj.distance_m:.2f} m  ({dist_cm:.0f} cm)'

            # Filled black background pill for maximum readability
            bg_color = (0, 0, 0)
            font       = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.55
            thickness  = 2
            (tw1, th1), _ = cv2.getTextSize(label_line1, font, font_scale, thickness)
            (tw2, th2), _ = cv2.getTextSize(label_line2, font, font_scale, thickness)
            box_w  = max(tw1, tw2) + 8
            box_h  = th1 + th2 + 14
            top_y  = max(y - box_h - 4, 0)
            cv2.rectangle(img, (x, top_y), (x + box_w, top_y + box_h), bg_color, cv2.FILLED)

            # White text on black background
            cv2.putText(img, label_line1, (x + 4, top_y + th1 + 4),
                        font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
            cv2.putText(img, label_line2, (x + 4, top_y + th1 + th2 + 10),
                        font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    def _draw_depth_overlays(self, depth_bgr: np.ndarray, detections: DetectedObjectArray):
        """Draw bounding boxes + distance text on the false-colour depth image."""
        for obj in detections.objects:
            x, y, w, h = obj.bbox_x, obj.bbox_y, obj.bbox_w, obj.bbox_h
            cv2.rectangle(depth_bgr, (x, y), (x + w, y + h), (255, 255, 255), 2)
            label = f'{obj.label[0].upper()} {obj.distance_m:.2f}m'
            cv2.putText(depth_bgr, label, (x + 2, max(y - 6, 0)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    def _publish_markers(self, detections: DetectedObjectArray):
        marker_array = MarkerArray()

        # Clear all previous markers
        delete_all = Marker()
        delete_all.action = Marker.DELETEALL
        marker_array.markers.append(delete_all)

        for idx, obj in enumerate(detections.objects):
            m = Marker()
            m.header    = detections.header
            m.ns        = 'detections'
            m.id        = idx
            m.type      = Marker.CUBE
            m.action    = Marker.ADD

            m.pose.position.x    = obj.position_3d.x
            m.pose.position.y    = obj.position_3d.y
            m.pose.position.z    = obj.position_3d.z
            m.pose.orientation.w = 1.0

            # Approximate cube side = 5 cm
            m.scale.x = 0.05
            m.scale.y = 0.05
            m.scale.z = 0.05

            r, g, b = MARKER_COLOR_MAP.get(obj.label, (1.0, 1.0, 1.0))
            m.color.r = r
            m.color.g = g
            m.color.b = b
            m.color.a = 0.85

            # 0.5 s lifetime so stale markers auto-disappear
            m.lifetime = Duration(sec=0, nanosec=500_000_000)

            marker_array.markers.append(m)

            # Text marker floating above the cube showing label + distance
            t = Marker()
            t.header    = detections.header
            t.ns        = 'detection_labels'
            t.id        = idx
            t.type      = Marker.TEXT_VIEW_FACING
            t.action    = Marker.ADD

            t.pose.position.x    = obj.position_3d.x
            t.pose.position.y    = obj.position_3d.y - 0.08   # float above cube
            t.pose.position.z    = obj.position_3d.z
            t.pose.orientation.w = 1.0

            t.scale.z = 0.04   # text height in metres
            t.color.r = r
            t.color.g = g
            t.color.b = b
            t.color.a = 1.0
            t.text    = f"Cube Detected\n{obj.distance_m:.2f} m"
            t.lifetime = Duration(sec=0, nanosec=500_000_000)

            marker_array.markers.append(t)

        self._markers_pub.publish(marker_array)


def main(args=None):
    rclpy.init(args=args)
    node = VisualizerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

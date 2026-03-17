"""
visualizer_node: Subscribes to /detections + /sync/color/image_raw.
Publishes:
  /detection_image   (sensor_msgs/Image) — annotated image
  /detection_markers (visualization_msgs/MarkerArray) — 3D cubes in RViz
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

from realsense_color_detector_msgs.msg import DetectedObjectArray


SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)

COLOR_MAP = {
    'red':   (0,   0,   255),
    'green': (0,   255, 0  ),
    'blue':  (255, 0,   0  ),
}

MARKER_COLOR_MAP = {
    'red':   (1.0, 0.0, 0.0),
    'green': (0.0, 1.0, 0.0),
    'blue':  (0.0, 0.4, 1.0),
}


class VisualizerNode(Node):
    def __init__(self):
        super().__init__('visualizer_node')

        self._bridge = CvBridge()
        self._latest_detections: DetectedObjectArray = None

        self.create_subscription(
            DetectedObjectArray, '/detections', self._on_detections, 10
        )
        self.create_subscription(
            Image, '/sync/color/image_raw', self._on_color_image, SENSOR_QOS
        )

        self._image_pub   = self.create_publisher(Image,       '/detection_image',   SENSOR_QOS)
        self._markers_pub = self.create_publisher(MarkerArray, '/detection_markers', 10)

        self.get_logger().info('VisualizerNode ready.')

    def _on_detections(self, msg: DetectedObjectArray):
        self._latest_detections = msg
        self._publish_markers(msg)

    def _on_color_image(self, msg: Image):
        if self._latest_detections is None:
            return
        cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8').copy()
        self._draw_detections(cv_img, self._latest_detections)
        out_msg = self._bridge.cv2_to_imgmsg(cv_img, encoding='bgr8')
        out_msg.header = msg.header
        self._image_pub.publish(out_msg)

    def _draw_detections(self, img: np.ndarray, detections: DetectedObjectArray):
        for obj in detections.objects:
            color = COLOR_MAP.get(obj.label, (255, 255, 255))
            x, y, w, h = obj.bbox_x, obj.bbox_y, obj.bbox_w, obj.bbox_h
            cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
            label_text = f'{obj.label} {obj.distance_m:.2f}m'
            cv2.putText(
                img, label_text, (x, max(y - 8, 0)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA
            )

    def _publish_markers(self, detections: DetectedObjectArray):
        marker_array = MarkerArray()

        # Delete all old markers first
        delete_marker = Marker()
        delete_marker.action = Marker.DELETEALL
        marker_array.markers.append(delete_marker)

        for idx, obj in enumerate(detections.objects):
            m = Marker()
            m.header = detections.header
            m.ns = 'detections'
            m.id = idx
            m.type = Marker.CUBE
            m.action = Marker.ADD

            m.pose.position.x = obj.position_3d.x
            m.pose.position.y = obj.position_3d.y
            m.pose.position.z = obj.position_3d.z
            m.pose.orientation.w = 1.0

            # Approximate cube size (0.05m = 5cm)
            m.scale.x = 0.05
            m.scale.y = 0.05
            m.scale.z = 0.05

            r, g, b = MARKER_COLOR_MAP.get(obj.label, (1.0, 1.0, 1.0))
            m.color.r = r
            m.color.g = g
            m.color.b = b
            m.color.a = 0.8

            lifetime = Duration()
            lifetime.sec = 0
            lifetime.nanosec = 500_000_000  # 0.5s
            m.lifetime = lifetime

            marker_array.markers.append(m)

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

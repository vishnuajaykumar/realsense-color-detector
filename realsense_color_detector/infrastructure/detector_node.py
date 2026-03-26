"""
detector_node: Receives color+depth images, runs YOLO cube detection,
publishes DetectedObjectArray on /detections.
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge

from realsense_color_detector_msgs.msg import DetectedObject as DetectedObjectMsg
from realsense_color_detector_msgs.msg import DetectedObjectArray
from geometry_msgs.msg import Point

from ..application.detection_pipeline import DetectionPipeline
from ..domain.models import CameraIntrinsics


SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)


class DetectorNode(Node):
    def __init__(self):
        super().__init__('detector_node')

        model_path  = self.declare_parameter(
            'model_path',
            '/ros2_ws/yolov8s-world.pt',
        ).value
        self.get_logger().info(f'Resolved model_path: {model_path}')
        confidence  = self.declare_parameter('confidence',  0.15).value # Lowered for zero-shot text
        depth_scale = self.declare_parameter('depth_scale', 0.001).value
        min_depth   = self.declare_parameter('min_depth_m', 0.1).value
        max_depth   = self.declare_parameter('max_depth_m', 4.0).value

        color_topic = self.declare_parameter('color_topic', '/camera/color/image_raw').value
        depth_topic = self.declare_parameter('depth_topic', '/camera/aligned_depth_to_color/image_raw').value
        info_topic  = self.declare_parameter('info_topic',  '/camera/color/camera_info').value
        imgsz       = self.declare_parameter('imgsz', 416).value

        self.get_logger().info(f'Loading model from: {model_path}')
        self._pipeline = DetectionPipeline(
            model_path=model_path,
            confidence=confidence,
            depth_scale=depth_scale,
            min_depth_m=min_depth,
            max_depth_m=max_depth,
            imgsz=imgsz,
        )
        self.get_logger().info('Model loaded.')

        self._bridge = CvBridge()
        self._intrinsics: CameraIntrinsics = None
        self._latest_depth_msg: Image = None

        self._info_sub  = self.create_subscription(CameraInfo, info_topic,  self._on_camera_info, SENSOR_QOS)
        self._depth_sub = self.create_subscription(Image,      depth_topic, self._on_depth,       SENSOR_QOS)
        self._color_sub = self.create_subscription(Image,      color_topic, self._on_color,       SENSOR_QOS)

        self._detections_pub = self.create_publisher(DetectedObjectArray, '/detections', 10)

        self.get_logger().info(
            f'DetectorNode ready. color={color_topic} depth={depth_topic}'
        )

    def _on_camera_info(self, msg: CameraInfo):
        if self._intrinsics is None:
            k = msg.k
            self._intrinsics = CameraIntrinsics(
                fx=k[0], fy=k[4], cx=k[2], cy=k[5],
                width=msg.width, height=msg.height,
            )
            self.get_logger().info(
                f'Intrinsics: fx={k[0]:.1f} fy={k[4]:.1f} cx={k[2]:.1f} cy={k[5]:.1f}'
            )

    def _on_depth(self, msg: Image):
        self._latest_depth_msg = msg

    def _on_color(self, color_msg: Image):
        if self._intrinsics is None:
            self.get_logger().info('Waiting for intrinsics...', throttle_duration_sec=7.0)
            return
        if self._latest_depth_msg is None:
            self.get_logger().info('Waiting for first depth message...', throttle_duration_sec=7.0)
            return

        self.get_logger().info(f'Processing frame ({self._pipeline._imgsz}x{self._pipeline._imgsz})...', throttle_duration_sec=3.0)

        try:
            color_cv = self._bridge.imgmsg_to_cv2(color_msg, desired_encoding='bgr8')
            depth_cv = self._bridge.imgmsg_to_cv2(
                self._latest_depth_msg, desired_encoding='passthrough'
            )

            detections = self._pipeline.run(color_cv, depth_cv, self._intrinsics)

            array_msg = DetectedObjectArray()
            array_msg.header = color_msg.header
            for d in detections:
                obj = DetectedObjectMsg()
                obj.label      = d.label
                obj.distance_m = d.distance_m
                obj.bbox_x     = d.bbox.x
                obj.bbox_y     = d.bbox.y
                obj.bbox_w     = d.bbox.w
                obj.bbox_h     = d.bbox.h
                pt = Point()
                pt.x = d.position_3d.x
                pt.y = d.position_3d.y
                pt.z = d.position_3d.z
                obj.position_3d = pt
                array_msg.objects.append(obj)

            self._detections_pub.publish(array_msg)

            if array_msg.objects:
                self.get_logger().info(
                    f'Detected {len(array_msg.objects)} object(s)',
                    throttle_duration_sec=3.0,
                )

        except Exception as exc:
            self.get_logger().error(f'detector error: {exc}', throttle_duration_sec=2.0)


def main(args=None):
    rclpy.init(args=args)
    node = DetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

"""
detector_node: Receives synced color+depth images, runs HSV detection pipeline,
publishes DetectedObjectArray on /detections.
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
from message_filters import ApproximateTimeSynchronizer, Subscriber

from realsense_color_detector_msgs.msg import DetectedObject as DetectedObjectMsg
from realsense_color_detector_msgs.msg import DetectedObjectArray
from geometry_msgs.msg import Point

from ..application.detection_pipeline import DetectionPipeline
from ..domain.models import CameraIntrinsics, HsvRange


SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)


class DetectorNode(Node):
    def __init__(self):
        super().__init__('detector_node')

        self._declare_hsv_params()
        min_area = self.declare_parameter('min_contour_area', 500.0).value

        self._pipeline = DetectionPipeline(min_contour_area=min_area)
        self._bridge = CvBridge()
        self._intrinsics: CameraIntrinsics = None

        self.create_subscription(CameraInfo, '/sync/color/camera_info', self._on_camera_info, SENSOR_QOS)

        self._color_sub = Subscriber(self, Image, '/sync/color/image_raw', qos_profile=SENSOR_QOS)
        self._depth_sub = Subscriber(self, Image, '/sync/depth/image_raw', qos_profile=SENSOR_QOS)
        self._sync = ApproximateTimeSynchronizer(
            [self._color_sub, self._depth_sub], queue_size=10, slop=0.05
        )
        self._sync.registerCallback(self._on_images)

        self._detections_pub = self.create_publisher(DetectedObjectArray, '/detections', 10)

        self.get_logger().info('DetectorNode ready.')

    def _declare_hsv_params(self):
        # Red (two ranges for hue wraparound)
        self.declare_parameter('red.h_low1',  0)
        self.declare_parameter('red.h_high1', 10)
        self.declare_parameter('red.h_low2',  160)
        self.declare_parameter('red.h_high2', 180)
        self.declare_parameter('red.s_low',   100)
        self.declare_parameter('red.s_high',  255)
        self.declare_parameter('red.v_low',   100)
        self.declare_parameter('red.v_high',  255)
        # Green
        self.declare_parameter('green.h_low',  40)
        self.declare_parameter('green.h_high', 80)
        self.declare_parameter('green.s_low',  80)
        self.declare_parameter('green.s_high', 255)
        self.declare_parameter('green.v_low',  80)
        self.declare_parameter('green.v_high', 255)
        # Blue
        self.declare_parameter('blue.h_low',  100)
        self.declare_parameter('blue.h_high', 130)
        self.declare_parameter('blue.s_low',  80)
        self.declare_parameter('blue.s_high', 255)
        self.declare_parameter('blue.v_low',  80)
        self.declare_parameter('blue.v_high', 255)

    def _build_profiles_from_params(self):
        from ..domain.models import ColorProfile
        g = self.get_parameter

        red = ColorProfile(label='red', ranges=[
            HsvRange(g('red.h_low1').value,  g('red.h_high1').value,
                     g('red.s_low').value,   g('red.s_high').value,
                     g('red.v_low').value,   g('red.v_high').value),
            HsvRange(g('red.h_low2').value,  g('red.h_high2').value,
                     g('red.s_low').value,   g('red.s_high').value,
                     g('red.v_low').value,   g('red.v_high').value),
        ])
        green = ColorProfile(label='green', ranges=[
            HsvRange(g('green.h_low').value, g('green.h_high').value,
                     g('green.s_low').value, g('green.s_high').value,
                     g('green.v_low').value, g('green.v_high').value),
        ])
        blue = ColorProfile(label='blue', ranges=[
            HsvRange(g('blue.h_low').value,  g('blue.h_high').value,
                     g('blue.s_low').value,  g('blue.s_high').value,
                     g('blue.v_low').value,  g('blue.v_high').value),
        ])
        return [red, green, blue]

    def _on_camera_info(self, msg: CameraInfo):
        if self._intrinsics is None:
            k = msg.k
            self._intrinsics = CameraIntrinsics(
                fx=k[0], fy=k[4], cx=k[2], cy=k[5],
                width=msg.width, height=msg.height,
            )
            self.get_logger().info(
                f'Camera intrinsics received: fx={k[0]:.1f} fy={k[4]:.1f} cx={k[2]:.1f} cy={k[5]:.1f}'
            )

    def _on_images(self, color_msg: Image, depth_msg: Image):
        if self._intrinsics is None:
            return

        color_cv = self._bridge.imgmsg_to_cv2(color_msg, desired_encoding='bgr8')
        depth_cv = self._bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')

        # Refresh profiles from live params (allows runtime tuning)
        self._pipeline.color_profiles = self._build_profiles_from_params()

        detections = self._pipeline.run(color_cv, depth_cv, self._intrinsics)

        array_msg = DetectedObjectArray()
        array_msg.header = color_msg.header
        for d in detections:
            obj = DetectedObjectMsg()
            obj.label = d.label
            obj.distance_m = d.distance_m
            obj.bbox_x = d.bbox.x
            obj.bbox_y = d.bbox.y
            obj.bbox_w = d.bbox.w
            obj.bbox_h = d.bbox.h
            pt = Point()
            pt.x = d.position_3d.x
            pt.y = d.position_3d.y
            pt.z = d.position_3d.z
            obj.position_3d = pt
            array_msg.objects.append(obj)

        self._detections_pub.publish(array_msg)


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

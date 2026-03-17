"""
camera_node: Subscribes to RealSense color + aligned depth topics,
republishes synchronized pairs and caches the latest camera_info.
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image, CameraInfo
from message_filters import ApproximateTimeSynchronizer, Subscriber


SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)


class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')

        color_topic = self.declare_parameter('color_topic', '/camera/color/image_raw').value
        depth_topic = self.declare_parameter('depth_topic', '/camera/aligned_depth_to_color/image_raw').value
        info_topic  = self.declare_parameter('info_topic',  '/camera/color/camera_info').value

        self._color_pub = self.create_publisher(Image, '/sync/color/image_raw', SENSOR_QOS)
        self._depth_pub = self.create_publisher(Image, '/sync/depth/image_raw', SENSOR_QOS)
        self._info_pub  = self.create_publisher(CameraInfo, '/sync/color/camera_info', SENSOR_QOS)

        self._color_sub = Subscriber(self, Image, color_topic, qos_profile=SENSOR_QOS)
        self._depth_sub = Subscriber(self, Image, depth_topic, qos_profile=SENSOR_QOS)

        self._sync = ApproximateTimeSynchronizer(
            [self._color_sub, self._depth_sub],
            queue_size=10,
            slop=0.05,
        )
        self._sync.registerCallback(self._on_synced)

        self.create_subscription(CameraInfo, info_topic, self._on_camera_info, SENSOR_QOS)

        self.get_logger().info(f'CameraNode ready. color={color_topic} depth={depth_topic}')

    def _on_synced(self, color_msg: Image, depth_msg: Image):
        self._color_pub.publish(color_msg)
        self._depth_pub.publish(depth_msg)

    def _on_camera_info(self, msg: CameraInfo):
        self._info_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

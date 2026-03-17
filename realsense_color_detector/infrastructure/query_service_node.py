"""
query_service_node: Maintains a cache of latest detections.
Exposes /query_objects service (QueryObjects.srv) for NL queries via MCP.
"""
import rclpy
from rclpy.node import Node

from realsense_color_detector_msgs.msg import DetectedObjectArray
from realsense_color_detector_msgs.srv import QueryObjects
from ..domain.models import DetectedObject as DomainDetectedObject, BoundingBox, Point3D
from ..domain.query_parser import answer_query


class QueryServiceNode(Node):
    def __init__(self):
        super().__init__('query_service_node')

        self._latest: list[DomainDetectedObject] = []

        self.create_subscription(
            DetectedObjectArray, '/detections', self._on_detections, 10
        )
        self.create_service(QueryObjects, '/query_objects', self._handle_query)

        self.get_logger().info('QueryServiceNode ready. Service: /query_objects')

    def _on_detections(self, msg: DetectedObjectArray):
        self._latest = []
        for obj in msg.objects:
            self._latest.append(DomainDetectedObject(
                label=obj.label,
                distance_m=obj.distance_m,
                bbox=BoundingBox(
                    x=obj.bbox_x, y=obj.bbox_y,
                    w=obj.bbox_w, h=obj.bbox_h,
                ),
                position_3d=Point3D(
                    x=obj.position_3d.x,
                    y=obj.position_3d.y,
                    z=obj.position_3d.z,
                ),
            ))

    def _handle_query(
        self,
        request: QueryObjects.Request,
        response: QueryObjects.Response,
    ) -> QueryObjects.Response:
        self.get_logger().info(f'Query received: "{request.question}"')
        response.answer = answer_query(request.question, self._latest)
        self.get_logger().info(f'Answer: "{response.answer}"')
        return response


def main(args=None):
    rclpy.init(args=args)
    node = QueryServiceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

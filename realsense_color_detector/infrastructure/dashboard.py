import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import threading
from flask import Flask, render_template, Response, jsonify
import time

app = Flask(__name__)

class DashboardNode(Node):
    def __init__(self):
        super().__init__('dashboard_node')
        self.bridge = CvBridge()
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        
        # Subscribing to the annotated image from visualizer_node
        self.subscription = self.create_subscription(
            Image,
            '/detection_image',
            self.image_callback,
            10
        )
        self.get_logger().info('DashboardNode initialized, subscribing to /detection_image')

    def image_callback(self, msg):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            with self.frame_lock:
                self.latest_frame = cv_image
        except Exception as e:
            self.get_logger().error(f'Error in image_callback: {str(e)}')

def generate_frames(node):
    while True:
        with node.frame_lock:
            if node.latest_frame is None:
                # Placeholder if no frame received
                frame = None
            else:
                ret, buffer = cv2.imencode('.jpg', node.latest_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                frame = buffer.tobytes()

        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            # Short sleep to prevent CPU spin
            time.sleep(0.1)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(global_node),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({"status": "ok", "camera_active": global_node.latest_frame is not None})

def ros_spin(node):
    rclpy.spin(node)

if __name__ == '__main__':
    rclpy.init()
    global_node = DashboardNode()
    
    # Start ROS spinning in a separate thread
    threading.Thread(target=ros_spin, args=(global_node,), daemon=True).start()
    
    # Start Flask server
    # Note: host='0.0.0.0' is critical for Docker
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

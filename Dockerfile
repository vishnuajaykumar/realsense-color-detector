FROM ros:foxy-ros-base

ARG DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    libusb-1.0-0 \
    udev \
    ros-foxy-realsense2-camera \
    ros-foxy-rosbridge-suite \
    ros-foxy-rviz2 \
    ros-foxy-cv-bridge \
    ros-foxy-vision-opencv \
    ros-foxy-image-transport \
    ros-foxy-message-filters \
    ros-foxy-rqt-image-view \
    ros-foxy-rqt-gui \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
RUN pip3 install --no-cache-dir "setuptools<60" "importlib-metadata<5.0" "numpy>=1.20" "typing-extensions<4.10.0" "matplotlib<3.8" && \
    pip3 install --no-cache-dir \
    pyrealsense2 \
    opencv-python-headless \
    torch==2.0.1 torchvision==0.15.2 --extra-index-url https://download.pytorch.org/whl/cpu \
    ultralytics

# Copy both packages into the workspace
# Build context is ~/ros2_ws/src/ (set in docker-compose.yml)
WORKDIR /ros2_ws
COPY realsense_color_detector/yolov8s-world.pt /ros2_ws/yolov8s-world.pt
COPY realsense_color_detector_msgs/ /ros2_ws/src/realsense_color_detector_msgs/
COPY realsense_color_detector/     /ros2_ws/src/realsense_color_detector/

# Build msgs package first, then main package
RUN /bin/bash -c "\
    source /opt/ros/foxy/setup.bash && \
    colcon build --packages-select realsense_color_detector_msgs && \
    source /ros2_ws/install/setup.bash && \
    colcon build --packages-select realsense_color_detector"

# Entrypoint
RUN echo '#!/bin/bash\nset -e\nsource /opt/ros/foxy/setup.bash\nsource /ros2_ws/install/setup.bash\nexec "$@"' \
    > /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["ros2", "launch", "realsense_color_detector", "detector.launch.py"]

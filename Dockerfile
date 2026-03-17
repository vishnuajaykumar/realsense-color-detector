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
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
RUN pip3 install --no-cache-dir \
    pyrealsense2 \
    opencv-python-headless \
    numpy

# Copy both packages into the workspace
# Build context is ~/ros2_ws/src/ (set in docker-compose.yml)
WORKDIR /ros2_ws
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

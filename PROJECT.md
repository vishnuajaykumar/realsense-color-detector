# RealSense Color Detector

> Single source of truth. Update this file after every significant change.

**GitHub:** https://github.com/vishnuajaykumar/realsense-color-detector
**Maintainer:** Vishnu Ajaykumar <vishnuajaykumar@gmail.com>

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     LattePanda Host / Docker                     │
│                                                                   │
│  ┌──────────────────┐        ┌──────────────────────────────┐   │
│  │  Intel RealSense │        │       ROS2 Foxy Stack         │   │
│  │     D435i        │─USB───▶│                               │   │
│  └──────────────────┘        │  realsense2_camera node       │   │
│                               │    /camera/color/image_raw   │   │
│                               │    /camera/aligned_depth_... │   │
│                               │    /camera/color/camera_info │   │
│                               │    /camera/depth/color/points│   │
│                               │         │                    │   │
│                               │  camera_node (sync)          │   │
│                               │    /sync/color/image_raw     │   │
│                               │    /sync/depth/image_raw     │   │
│                               │    /sync/color/camera_info   │   │
│                               │         │                    │   │
│                               │  detector_node (HSV+depth)   │   │
│                               │    /detections               │   │
│                               │         │                    │   │
│                               │  ┌──────┴──────┐            │   │
│                               │  │             │            │   │
│                               │  visualizer   query_service │   │
│                               │  /detection_  /query_objects│   │
│                               │  _image       (ROS2 srv)    │   │
│                               │  /detection_               │   │
│                               │  _markers                   │   │
│                               │             │               │   │
│                               │      rosbridge_websocket    │   │
│                               │         ws://localhost:9090 │   │
│                               └──────────────────────────────┘   │
│                                           │                       │
│                               ┌───────────▼──────────┐           │
│                               │   ros-mcp-server      │           │
│                               │  (Python, standalone) │           │
│                               └───────────┬──────────┘           │
│                                           │ MCP protocol          │
│                               ┌───────────▼──────────┐           │
│                               │    Claude Desktop     │           │
│                               │  "Do you see a red   │           │
│                               │   cube? How far?"     │           │
│                               └──────────────────────┘           │
│                                                                   │
│  RViz2 ◀── /detection_markers, /detection_image, /camera/...    │
└─────────────────────────────────────────────────────────────────┘
```

---

## ROS2 Topics & Services

| Topic / Service | Type | Direction | Description |
|---|---|---|---|
| `/camera/color/image_raw` | `sensor_msgs/Image` | IN | Raw color stream from RealSense |
| `/camera/aligned_depth_to_color/image_raw` | `sensor_msgs/Image` | IN | Depth aligned to color frame |
| `/camera/color/camera_info` | `sensor_msgs/CameraInfo` | IN | Intrinsics |
| `/camera/depth/color/points` | `sensor_msgs/PointCloud2` | IN | Point cloud (optional) |
| `/sync/color/image_raw` | `sensor_msgs/Image` | PUB | Time-synced color |
| `/sync/depth/image_raw` | `sensor_msgs/Image` | PUB | Time-synced depth |
| `/sync/color/camera_info` | `sensor_msgs/CameraInfo` | PUB | Re-published camera info |
| `/detections` | `DetectedObjectArray` | PUB | Per-frame detections |
| `/detection_image` | `sensor_msgs/Image` | PUB | Annotated color image |
| `/detection_markers` | `visualization_msgs/MarkerArray` | PUB | 3D cube markers for RViz |
| `/query_objects` | `QueryObjects.srv` | SERVICE | NL query → NL answer |

---

## Package Layout

```
ros2_ws/
└── src/
    ├── realsense_color_detector_msgs/   # Custom interfaces (ament_cmake)
    │   ├── msg/
    │   │   ├── DetectedObject.msg
    │   │   └── DetectedObjectArray.msg
    │   ├── srv/
    │   │   └── QueryObjects.srv
    │   ├── CMakeLists.txt
    │   └── package.xml
    │
    └── realsense_color_detector/        # Main package (ament_python)
        ├── realsense_color_detector/
        │   ├── domain/
        │   │   ├── models.py            # Data classes (no ROS)
        │   │   ├── color_detector.py    # HSV segmentation (no ROS)
        │   │   └── query_parser.py      # NL query logic (no ROS)
        │   ├── application/
        │   │   └── detection_pipeline.py  # Use case orchestration
        │   └── infrastructure/
        │       ├── camera_node.py
        │       ├── detector_node.py
        │       ├── visualizer_node.py
        │       └── query_service_node.py
        ├── presentation/
        │   ├── launch/detector.launch.py
        │   ├── config/detector_params.yaml
        │   └── rviz/detector.rviz
        ├── scripts/
        │   └── install_udev.sh
        ├── Dockerfile
        ├── docker-compose.yml
        ├── docker-entrypoint.sh
        ├── setup.py
        ├── package.xml
        └── PROJECT.md
```

---

## Dependencies

| Dependency | Source | Version / Notes |
|---|---|---|
| ROS2 Foxy | System | Ubuntu 20.04 |
| ros-foxy-realsense2-camera | apt | installed |
| ros-foxy-realsense2-camera-msgs | apt | installed |
| ros-foxy-rosbridge-suite | apt | rosbridge_websocket |
| ros-foxy-rviz2 | apt | visualization |
| ros-foxy-cv-bridge | apt | image conversion |
| ros-foxy-vision-opencv | apt | |
| ros-foxy-image-transport | apt | |
| ros-foxy-message-filters | apt | ApproximateTimeSynchronizer |
| opencv-python-headless | pip | HSV processing |
| numpy | pip | array ops |
| pyrealsense2 | pip | optional (direct SDK) |

---

## Build & Run (Native colcon)

```bash
# 1. Source ROS2
source /opt/ros/foxy/setup.bash

# 2. Build msgs first
cd ~/ros2_ws
colcon build --packages-select realsense_color_detector_msgs

# 3. Source generated interfaces
source install/setup.bash

# 4. Build main package
colcon build --packages-select realsense_color_detector

# 5. Source again
source install/setup.bash

# 6. Launch
ros2 launch realsense_color_detector detector.launch.py
```

---

## Build & Run (Docker)

```bash
# Install udev rules ONCE on host
cd ~/ros2_ws/src/realsense_color_detector
chmod +x scripts/install_udev.sh
./scripts/install_udev.sh

# Allow Docker to use display
xhost +local:docker

# Build image
docker compose build

# Run full stack
docker compose up

# Run only detector (no MCP server)
docker compose up detector

# Rebuild after code changes
docker compose build --no-cache && docker compose up

# Test NL query service
ros2 service call /query_objects realsense_color_detector_msgs/srv/QueryObjects "{question: 'Do you see a red cube?'}"
```

---

## Docker Troubleshooting

| Issue | Fix |
|---|---|
| RealSense not found | Run `scripts/install_udev.sh` on host, then reconnect camera |
| RViz blank / no display | `xhost +local:docker` then `export DISPLAY=:0` |
| ROS2 DDS discovery fails | Ensure `network_mode: host` in docker-compose.yml |
| `/detections` not publishing | Check camera_info arrives: `ros2 topic echo /sync/color/camera_info` |
| ROS_DOMAIN_ID conflict | Set same `ROS_DOMAIN_ID` on host and in container |
| rosbridge not reachable | `ss -tlnp | grep 9090` — should show LISTEN |

---

## HSV Tuning Guide

Edit `presentation/config/detector_params.yaml` and restart detector_node, OR use live param set:

```bash
# Example: tighten blue detection
ros2 param set /detector_node blue.h_low 105
ros2 param set /detector_node blue.h_high 125

# Check what's being detected
ros2 topic echo /detections

# View annotated image
ros2 run rqt_image_view rqt_image_view /detection_image
```

Red requires two HSV ranges because hue wraps at 180°. Adjust `red.h_low1/h_high1` (lower red) and `red.h_low2/h_high2` (upper red) independently.

---

## MCP Server Setup

### 1. Clone ros-mcp-server (already done)

```bash
# Already cloned to ~/ros_mcp_server
# Already installed in ~/ros_mcp_server/.venv (Python 3.10)
```

### 2. Start rosbridge (already in launch file)

rosbridge_websocket listens on `ws://localhost:9090` by default.

### 3. Claude Desktop config

Add to `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ros2": {
      "command": "/home/vish/ros_mcp_server/.venv/bin/python",
      "args": ["/home/vish/ros_mcp_server/server.py"],
      "env": {
        "ROSBRIDGE_IP": "127.0.0.1",
        "ROSBRIDGE_PORT": "9090"
      }
    }
  }
}
```

> Note: `server.py` uses stdio transport (default). Claude Desktop spawns it as a subprocess.
> Ensure rosbridge is running (`docker compose up detector`) before opening Claude Desktop.

### 4. Sample NL queries that work

- "Do you see a red cube?"
- "How far away is the blue cube?"
- "What objects can you see right now?"
- "Is there a green cube and how far is it?"

The `query_service_node` handles these via `/query_objects` service and returns plain English answers.

---

## GitHub Repo & Branches

| Branch | Purpose |
|---|---|
| `main` | Stable, end-to-end tested |
| `dev` | Active development |
| `feature/<name>` | Feature branches |

**Commit conventions (conventional commits):**
```
feat: add HSV color detection domain logic
fix: correct depth sampling at bbox center
docs: update PROJECT.md with MCP config steps
chore: add .dockerignore and docker-compose.yml
```

---

## LattePanda-Specific Notes

- **USB power:** RealSense D435i draws ~0.9W. Use a powered USB hub or the top-mounted USB 3.0 port.
- **CPU:** LattePanda 3 Delta has 4 cores. Detection runs at ~15Hz; set `min_contour_area: 1000` if CPU is saturated.
- **udev rules:** Must be installed on the host, not inside the container.
- **Display:** If running headless, use VNC or forward X11 via SSH (`ssh -X`). Set `DISPLAY=:0` if using a local display.

---

## Known Issues & Workarounds

| Issue | Workaround |
|---|---|
| `message_filters` ApproximateTimeSynchronizer: no messages synced | Check that both topics publish at similar rates. Enable `enable_depth=true` and `align_depth.enable=true` in rs_launch |
| camera_info never arrives | Confirm realsense2_camera is publishing: `ros2 topic list | grep camera_info` |
| Depth returns 0 at bbox center | Object too close (<0.1m) or too far (>4m) for D435i. Check with `depth_window=10` |
| RViz MarkerArray not visible | Check fixed frame is `camera_color_optical_frame`, not `map` or `base_link` |

---

## Implementation Status

- [x] Package scaffolding (realsense_color_detector_msgs + realsense_color_detector)
- [x] Custom interfaces: DetectedObject.msg, DetectedObjectArray.msg, QueryObjects.srv
- [x] Domain layer: models, color_detector, query_parser
- [x] Application layer: DetectionPipeline use case
- [x] Infrastructure: camera_node, detector_node, visualizer_node, query_service_node
- [x] Launch file: detector.launch.py
- [x] Parameter YAML: detector_params.yaml
- [x] RViz config: detector.rviz
- [x] Dockerfile + docker-entrypoint.sh
- [x] docker-compose.yml
- [x] .dockerignore + .gitignore
- [x] scripts/install_udev.sh
- [x] PROJECT.md
- [x] colcon build verified (msgs + main package, Foxy, 2026-03-17)
- [x] Docker image builds cleanly (2026-03-17)
- [x] ros-mcp-server cloned + installed in ~/ros_mcp_server/.venv Python 3.10 (2026-03-17)
- [x] Push to GitHub dev branch (2026-03-17) — https://github.com/vishnuajaykumar/realsense-color-detector
- [ ] Live camera test: /detections publishes
- [ ] RViz visualization confirmed
- [ ] /query_objects service tested
- [ ] MCP server connected to Claude Desktop

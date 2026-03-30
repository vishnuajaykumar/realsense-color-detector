import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, ExecuteProcess, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('realsense_color_detector')
    params_file = os.path.join(pkg_share, 'config', 'detector_params.yaml')
    rviz_config = os.path.join(pkg_share, 'rviz', 'detector.rviz')

    rs_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(
                get_package_share_directory('realsense2_camera'),
                'launch', 'rs_launch.py'
            )
        ]),
        launch_arguments={
            'enable_color':       'true',
            'enable_depth':       'true',
            'align_depth.enable': 'true',
            'enable_pointcloud':  'false',
            'depth_module.profile': '424,240,6',
            'rgb_camera.profile':   '424,240,6',
            'initial_reset':        'true',
        }.items(),
    )

    detector_node = Node(
        package='realsense_color_detector',
        executable='detector_node',
        name='detector_node',
        parameters=[
            params_file,
            {'model_path': '/ros2_ws/yolov8s-world.pt', 'imgsz': 320}
        ],
        output='screen',
    )

    visualizer_node = Node(
        package='realsense_color_detector',
        executable='visualizer_node',
        name='visualizer_node',
        output='screen',
    )

    query_service_node = Node(
        package='realsense_color_detector',
        executable='query_service_node',
        name='query_service_node',
        output='screen',
    )

    rosbridge_node = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        parameters=[{'port': 9090}],
        output='screen',
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        output='screen',
    )

    return LaunchDescription([
        rs_launch,
        detector_node,
        visualizer_node,
        query_service_node,
        rosbridge_node,
        TimerAction(
            period=2.0,
            actions=[rviz_node]
        ),
    ])

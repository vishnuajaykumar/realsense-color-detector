from setuptools import setup
import os
from glob import glob

package_name = 'realsense_color_detector'

setup(
    name=package_name,
    version='0.1.0',
    packages=[
        package_name,
        f'{package_name}.domain',
        f'{package_name}.application',
        f'{package_name}.infrastructure',
    ],
    data_files=[
        ('share/ament_index/resource_index/packages', [f'resource/{package_name}']),
        (f'share/{package_name}', ['package.xml']),
        (f'share/{package_name}/launch', glob('presentation/launch/*.py')),
        (f'share/{package_name}/config', glob('presentation/config/*.yaml')),
        (f'share/{package_name}/rviz', glob('presentation/rviz/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Vishnu Ajaykumar',
    maintainer_email='vishnuajaykumar@gmail.com',
    description='RealSense D435i color object detection with RViz and MCP',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'camera_node = realsense_color_detector.infrastructure.camera_node:main',
            'detector_node = realsense_color_detector.infrastructure.detector_node:main',
            'visualizer_node = realsense_color_detector.infrastructure.visualizer_node:main',
            'query_service_node = realsense_color_detector.infrastructure.query_service_node:main',
        ],
    },
)

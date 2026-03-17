#!/bin/bash
# Run this ONCE on the LattePanda host before launching Docker.
# Installs Intel RealSense udev rules so the camera is accessible via USB.

set -e

RULES_URL="https://raw.githubusercontent.com/IntelRealSense/librealsense/master/config/99-realsense-libusb.rules"
RULES_FILE="/etc/udev/rules.d/99-realsense-libusb.rules"

echo "[install_udev] Downloading RealSense udev rules..."
sudo curl -fsSL "$RULES_URL" -o "$RULES_FILE"

echo "[install_udev] Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "[install_udev] Done. Reconnect the RealSense camera if it was already plugged in."

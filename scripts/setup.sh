#!/bin/bash
set -e

echo "=========================================="
echo " DVD Ripping Appliance - Setup Script"
echo " Raspberry Pi 4/5"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo bash setup.sh)"
    exit 1
fi

# Check if Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "WARNING: This does not appear to be a Raspberry Pi."
    echo "The script will continue, but compatibility is not guaranteed."
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "[1/8] Updating package lists..."
apt-get update -y

echo "[2/8] Installing system dependencies..."
apt-get install -y \
    ffmpeg \
    lsdvd \
    libdvd-pkg \
    python3 \
    python3-pip \
    python3-venv \
    exfat-fuse \
    exfatprogs \
    ntfs-3g \
    usbutils \
    curl \
    sudo

echo "[3/8] Configuring libdvd-pkg (DVD decryption)..."
# Non-interactive libdvd-pkg setup
export DEBIAN_FRONTEND=noninteractive
dpkg-reconfigure -f noninteractive libdvd-pkg 2>/dev/null || true

echo "[4/8] Setting up Python virtual environment..."
INSTALL_DIR="/opt/dvd-ripper"
mkdir -p "$INSTALL_DIR"

# Copy project files
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"

# Create venv
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

echo "[5/8] Installing Python dependencies..."
pip install --upgrade pip
pip install flask

echo "[6/8] Creating directories..."
mkdir -p /tmp/dvd-ripper
mkdir -p /media/usb/RIPS
chmod 777 /tmp/dvd-ripper
chmod 777 /media/usb/RIPS

echo "[7/8] Installing systemd service..."
cp "$INSTALL_DIR/services/dvd-ripper.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable dvd-ripper

echo "[8/8] Starting service..."
systemctl start dvd-ripper

echo ""
echo "=========================================="
echo " Setup Complete!"
echo "=========================================="
echo ""
echo "The DVD Ripping Appliance is now running."
echo ""
echo "Access the web interface at:"
echo "  http://$(hostname -I | awk '{print $1}'):5000"
echo "  or"
echo "  http://raspberrypi.local:5000"
echo ""
echo "To check status:"
echo "  sudo systemctl status dvd-ripper"
echo ""
echo "To view logs:"
echo "  journalctl -u dvd-ripper -f"
echo ""
echo "To stop:"
echo "  sudo systemctl stop dvd-ripper"
echo ""
echo "To restart:"
echo "  sudo systemctl restart dvd-ripper"
echo ""

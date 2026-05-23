# Quick Start Guide

## For Users Without a PC

### What You Need
1. Raspberry Pi 4 or 5 (any model with 2GB+ RAM)
2. 16GB+ microSD card
3. USB DVD drive
4. USB flash drive or external HDD (for output)
5. Power supply
6. Network connection (Ethernet or WiFi)

### Step 1: Prepare the Pi
1. Download **Raspberry Pi Imager**: https://www.raspberrypi.com/software/
2. Flash **Raspberry Pi OS Lite (64-bit)** to your microSD card
3. Enable SSH (click the gear icon in Raspberry Pi Imager)
4. Insert the SD card into your Pi and boot it up

### Step 2: Connect to the Pi
1. Find your Pi's IP address (check your router's device list)
2. SSH into it from any device:
   ```
   ssh pi@<your-pi-ip>
   ```
   (default password: `raspberry`)

### Step 3: Install
```bash
# Download the project
git clone https://github.com/YOUR_USERNAME/dvd-ripping-appliance.git
cd dvd-ripping-appliance

# Run the setup script
sudo bash scripts/setup.sh
```

### Step 4: Use
1. Plug in your USB DVD drive
2. Plug in your USB output drive (formatted as exFAT)
3. Insert a DVD
4. On your phone, tablet, or any device on the same network, open:
   ```
   http://<your-pi-ip>:5000
   ```
5. Enter a disc name, choose settings, and click "Start Ripping"
6. Wait for completion (30-90 minutes typical)
7. Remove the USB drive and play the MP4 on your TV/console

## For Advanced Users

### CLI Mode
```bash
# Scan a DVD
dvd-rip scan

# Rip with defaults
dvd-rip rip --name "My Show"

# Rip with custom settings
dvd-rip rip --name "Show S01" --encoder x264_slow --quality 18 --upscale 720p
```

### Manual Install (without git)
```bash
# Download the zip from Internet Archive
# Extract to /opt/dvd-ripper
cd /opt/dvd-ripper
sudo bash scripts/setup.sh
```

### Troubleshooting

**Web UI won't load**
```bash
sudo systemctl status dvd-ripper
sudo journalctl -u dvd-ripper -f
```

**DVD not detected**
```bash
ls -la /dev/sr0
lsdvd /dev/sr0
```

**USB drive not showing**
```bash
lsblk
df -h
sudo mount /dev/sda1 /media/usb
```

**Not enough space**
- Use a larger USB drive
- Delete old rips: `rm /media/usb/RIPS/*.mp4`

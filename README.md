# DVD Ripping Appliance for Raspberry Pi

A turnkey DVD ripping solution for Raspberry Pi 4/5. Insert a DVD, open a web browser, and get MP4 files on your USB drive. No PC required.

## What It Does

- **Auto-detects** inserted DVDs and USB drives
- **Rips** each episode/title from the DVD
- **Detects duplicates** and removes them
- **Merges** episodes chronologically into a single file
- **Encodes** to MP4 with deinterlacing and cleanup
- **Saves** to USB drive automatically
- **Web UI** accessible from any device on your network

## Hardware Requirements

- **Raspberry Pi 4 or 5** (2GB+ RAM recommended)
- **USB DVD Drive** (any standard USB DVD-ROM)
- **USB Drive or External HDD** (for output, formatted as exFAT or NTFS for files >4GB)
- **MicroSD Card** (16GB+ for Raspberry Pi OS)
- **Power Supply** (official USB-C recommended for Pi 4/5)
- **Network** (Ethernet or WiFi for web UI access)

## Quick Start

### 1. Flash Raspberry Pi OS

Download and flash **Raspberry Pi OS Lite (64-bit)** to your microSD card:
https://www.raspberrypi.com/software/

### 2. Install

SSH into your Pi (or connect a monitor/keyboard), then run:

```bash
curl -L https://github.com/CyDragonReborn/dvd-ripping-appliance/raw/main/scripts/setup.sh | bash
```

Or manually:

```bash
git clone https://github.com/CyDragonReborn/dvd-ripping-appliance.git
cd dvd-ripping-appliance
sudo bash scripts/setup.sh
```

### 3. Use

1. Plug in your USB DVD drive and USB output drive
2. Insert a DVD
3. On any device on your network, open: `http://raspberrypi.local:5000`
4. Click "Start Ripping"
5. Wait for completion (typically 30-90 minutes per disc)
6. Remove USB drive, plug into TV/console/device, and play

## Web UI

The web interface provides:
- **Dashboard**: Shows connected drives, disc info, and ripping status
- **Disc Scan**: Reads DVD titles, durations, and chapters
- **Rip Progress**: Real-time progress bar and ETA
- **Settings**: Encoder quality, output resolution, subtitle options
- **History**: Log of completed rips

## CLI Usage

For advanced users, a CLI is also available:

```bash
# Scan a DVD
dvd-rip scan /dev/sr0

# Rip with defaults
dvd-rip rip /dev/sr0

# Rip with custom name and encoder
dvd-rip rip /dev/sr0 --name "Show S01" --encoder x264 --quality 22

# Rip from ISO
dvd-rip rip /path/to/dvd.iso --name "Show S01"

# Play All mode (all titles merged)
dvd-rip rip /dev/sr0 --play-all
```

## Encoder Options

| Encoder | Speed | Quality | Notes |
|---------|-------|---------|-------|
| `x264` | Medium | Best | CPU-based, recommended |
| `x264_fast` | Fast | Good | Faster, larger files |
| `x264_slow` | Slow | Best | Slowest, smallest files |

The Pi 4/5 uses the ARM CPU for encoding. No hardware GPU encoding is available, so expect:
- **Pi 4**: ~0.5-1x real-time for 480p->480p
- **Pi 5**: ~1-2x real-time for 480p->480p

A typical 2-hour DVD takes 2-4 hours to rip + encode on Pi 4, 1-2 hours on Pi 5.

## USB Drive Support

The appliance auto-detects USB drives and mounts them for output:

| Format | Support | Notes |
|--------|---------|-------|
| **exFAT** | Yes | Recommended, no 4GB limit |
| **NTFS** | Yes | Windows compatible |
| **ext4** | Yes | Linux only |
| **FAT32** | Warned | 4GB file size limit |

## Troubleshooting

### DVD Not Detected
- Ensure the USB DVD drive is plugged in directly (not through a hub)
- Check `dmesg | grep sr0` for drive detection
- Try `lsblk` to see if `/dev/sr0` appears

### USB Drive Not Showing
- Format as exFAT: `sudo mkfs.exfat -n RIPS /dev/sda1`
- Check `lsblk` and `df -h` for mounted drives
- Ensure the drive has sufficient free space

### Ripping Fails
- Encrypted DVDs require `libdvd-pkg` setup (handled by install script)
- Check logs: `journalctl -u dvd-ripper -f`
- Scratched discs may fail on specific titles

### Web UI Not Accessible
- Check Pi IP: `hostname -I`
- Ensure the service is running: `sudo systemctl status dvd-ripper`
- Check firewall: `sudo ufw status`

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Web Browser                       │
│              (any device on network)                 │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────┐
│              Flask Web Server (:5000)                │
│  ┌───────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Dashboard │  │ Settings │  │ Progress/Status  │  │
│  └───────────┘  └──────────┘  └──────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                  Ripper Engine                       │
│  ┌──────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐  │
│  │Scan  │→ │  Rip    │→ │ Dedupe  │→ │  Merge   │  │
│  │DVD   │  │ Titles  │  │         │  │          │  │
│  └──────┘  └─────────┘  └─────────┘  └──────────┘  │
│                                                    │
│  ┌──────────┐  ┌──────────┐                        │
│  │ Encode   │→ │  Save    │                        │
│  │ (x264)   │  │ to USB   │                        │
│  └──────────┘  └──────────┘                        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                  Hardware                            │
│  ┌──────────────┐  ┌──────────────────────────┐     │
│  │ USB DVD Drive│  │ USB Drive / External HDD │     │
│  │   /dev/sr0   │  │   /media/usb/RIPS/       │     │
│  └──────────────┘  └──────────────────────────┘     │
└─────────────────────────────────────────────────────┘
```

## License

MIT License - see LICENSE file

## Credits

Built with:
- **FFmpeg** - Video processing
- **HandBrake** - Encoding
- **libdvd-pkg** - DVD decryption
- **Flask** - Web interface
- **lsdvd** - DVD title scanning

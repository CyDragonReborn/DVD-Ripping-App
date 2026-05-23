import os
import logging
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class USBDrive:
    device: str
    mount_point: Path
    filesystem: str
    total_gb: float
    free_gb: float
    label: str = ""


def get_mounted_drives() -> list[USBDrive]:
    drives = []
    try:
        result = subprocess.run(
            ["lsblk", "-b", "-o", "NAME,SIZE,FSTYPE,MOUNTPOINT,LABEL,TRAN,RM", "-J"],
            capture_output=True, text=True, timeout=10
        )
        import json
        data = json.loads(result.stdout)

        for block_dev in data.get("blockdevices", []):
            if block_dev.get("tran") != "usb":
                continue
            if not block_dev.get("rm"):
                continue

            mount = block_dev.get("mountpoint")
            if not mount:
                continue

            size_bytes = int(block_dev.get("size", 0))
            size_gb = size_bytes / (1024 ** 3)

            try:
                stat = os.statvfs(mount)
                free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            except OSError:
                free_gb = 0

            drives.append(USBDrive(
                device=f"/dev/{block_dev['name']}",
                mount_point=Path(mount),
                filesystem=block_dev.get("fstype", "unknown") or "unknown",
                total_gb=round(size_gb, 1),
                free_gb=round(free_gb, 1),
                label=block_dev.get("label", "") or "USB Drive",
            ))
    except Exception as e:
        logger.warning("Failed to detect USB drives: %s", e)

    return drives


def get_best_output_path(preferred_dir: Path = None) -> Optional[Path]:
    if preferred_dir and preferred_dir.exists():
        return preferred_dir

    drives = get_mounted_drives()
    if not drives:
        return None

    best = max(drives, key=lambda d: d.free_gb)
    return best.mount_point / "RIPS"


def detect_usb_drives() -> list[USBDrive]:
    return get_mounted_drives()


def check_usb_space(path: Path, required_gb: float = 10.0) -> tuple[bool, float]:
    try:
        stat = os.statvfs(path)
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
        return free_gb >= required_gb, round(free_gb, 1)
    except OSError:
        return False, 0.0


def warn_fat32(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["df", "-T", str(path)],
            capture_output=True, text=True, timeout=5
        )
        return "vfat" in result.stdout.lower()
    except Exception:
        return False

import subprocess
import logging
import re
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = name[:100]
    return name or "untitled"


def find_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required binary not found: {name}")
    return path


def run_cmd(
    cmd: list[str],
    timeout: int = 7200,
    cwd: Optional[str] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    logger.debug("Running: %s", " ".join(str(c) for c in cmd))
    process = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )
    if check and process.returncode != 0:
        error_detail = process.stderr.strip()[-2000:] if process.stderr else "no output"
        raise RuntimeError(f"Command failed (rc={process.returncode}): {error_detail}")
    return process


def validate_dependencies(config) -> list[str]:
    missing = []
    for name, attr in [
        ("ffmpeg", "ffmpeg_bin"),
        ("ffprobe", "ffprobe_bin"),
        ("lsdvd", "lsdvd_bin"),
    ]:
        try:
            find_binary(getattr(config, attr))
        except RuntimeError:
            missing.append(name)
    return missing


def resolve_input_path(input_path: str, config) -> tuple[str, Optional[str]]:
    path = Path(input_path)

    if path.is_file() and path.suffix.lower() == ".iso":
        mount_dir = Path("/mnt/dvd-iso")
        mount_dir.mkdir(parents=True, exist_ok=True)
        run_cmd(["sudo", "mount", "-o", "loop,ro", str(path), str(mount_dir)])
        return str(mount_dir), str(mount_dir)

    return input_path, None


def unmount_iso(mount_dir: str) -> None:
    try:
        run_cmd(["sudo", "umount", mount_dir], check=False)
    except Exception as e:
        logger.warning("Failed to unmount ISO: %s", e)


def get_dvd_device() -> Optional[str]:
    for device in ["/dev/sr0", "/dev/sr1", "/dev/cdrom"]:
        if os.path.exists(device):
            return device
    return None


def is_dvd_inserted(device: str = "/dev/sr0") -> bool:
    try:
        result = subprocess.run(
            ["lsdvd", device],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0 and "Title:" in result.stdout
    except Exception:
        return False


import shutil

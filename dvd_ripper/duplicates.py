import logging
import subprocess
import hashlib
from pathlib import Path
from typing import Optional

from .config import Config
from .utils import run_cmd

logger = logging.getLogger(__name__)


def get_content_hash(file_path: Path, config: Config) -> Optional[str]:
    try:
        result = run_cmd([
            config.ffmpeg_bin,
            "-i", str(file_path),
            "-f", "md5",
            "-t", "60",
            "-v", "quiet",
            "pipe:",
        ], timeout=120)
        return result.stdout.strip()
    except Exception as e:
        logger.warning("Failed to hash %s: %s", file_path, e)
        return None


def get_file_duration(file_path: Path, config: Config) -> Optional[float]:
    try:
        result = run_cmd([
            config.ffprobe_bin,
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(file_path),
        ], timeout=30)
        return float(result.stdout.strip())
    except Exception:
        return None


def files_are_similar(
    file1: Path,
    file2: Path,
    config: Config,
    duration_threshold: float = 30.0,
) -> bool:
    dur1 = get_file_duration(file1, config)
    dur2 = get_file_duration(file2, config)

    if dur1 is None or dur2 is None:
        return False

    if abs(dur1 - dur2) > duration_threshold:
        return False

    hash1 = get_content_hash(file1, config)
    hash2 = get_content_hash(file2, config)

    if hash1 and hash2:
        return hash1 == hash2

    return False


def deduplicate_files(
    config: Config,
    files: list[Path],
) -> list[Path]:
    if len(files) <= 1:
        return list(files)

    logger.info("Checking %d files for duplicates", len(files))

    unique = []
    skipped = []

    for i, f in enumerate(files):
        is_dup = False
        for u in unique:
            if files_are_similar(f, u, config):
                logger.info("Duplicate detected: %s matches %s", f.name, u.name)
                is_dup = True
                skipped.append(f)
                break
        if not is_dup:
            unique.append(f)

    if skipped:
        logger.info("Removed %d duplicates, %d unique files remain", len(skipped), len(unique))
    else:
        logger.info("No duplicates found")

    return unique

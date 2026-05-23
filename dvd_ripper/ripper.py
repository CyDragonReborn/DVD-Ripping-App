import subprocess
import logging
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from .config import Config
from .utils import run_cmd, sanitize_filename

logger = logging.getLogger(__name__)


@dataclass
class DVDTitle:
    number: int
    duration_sec: float
    chapters: int
    audio_tracks: int
    subtitle_tracks: int
    name: str = ""
    vts: int = 0
    is_play_all: bool = False


@dataclass
class DVDInfo:
    all_titles: list[DVDTitle] = field(default_factory=list)
    episodic_titles: list[DVDTitle] = field(default_factory=list)
    play_all_title: Optional[DVDTitle] = None
    play_all_titles: list[DVDTitle] = field(default_factory=list)
    longest_track_num: Optional[int] = None
    has_single_track_play_all: bool = False


def parse_lsdvd_output(output: str) -> list[DVDTitle]:
    titles = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("Title: "):
            continue
        title_match = re.match(r"Title:\s+(\d+),\s*Length:\s+([\d:.]+)\s*Chapters:\s+(\d+)", line)
        if not title_match:
            continue
        number = int(title_match.group(1))
        dur_str = title_match.group(2).strip()
        chapters = int(title_match.group(3))
        parts = dur_str.split(":")
        if len(parts) == 3:
            duration_sec = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            duration_sec = float(parts[0]) * 60 + float(parts[1])
        else:
            duration_sec = 0.0
        audio_match = re.search(r"Audio streams:\s+(\d+)", line)
        sub_match = re.search(r"Subpictures:\s+(\d+)", line)
        titles.append(DVDTitle(
            number=number,
            duration_sec=duration_sec,
            chapters=chapters,
            audio_tracks=int(audio_match.group(1)) if audio_match else 0,
            subtitle_tracks=int(sub_match.group(1)) if sub_match else 0,
        ))
    return titles


def get_dvd_titles(config: Config, input_path: str) -> list[DVDTitle]:
    logger.info("Scanning DVD titles from: %s", input_path)
    result = run_cmd([config.lsdvd_bin, input_path])
    titles = parse_lsdvd_output(result.stdout)
    if not titles:
        raise RuntimeError("No titles found on DVD. Check disc or path.")
    logger.info("Found %d titles on DVD", len(titles))
    return titles


def scan_dvd(config: Config, input_path: str, min_duration_sec: float = 60.0) -> DVDInfo:
    all_titles = get_dvd_titles(config, input_path)

    longest_track_num = None
    try:
        result = run_cmd([config.lsdvd_bin, input_path])
        for line in result.stdout.splitlines():
            if line.startswith("Longest Track:"):
                match = re.match(r"Longest Track:\s+(\d+)", line)
                if match:
                    longest_track_num = int(match.group(1))
    except Exception:
        pass

    episodic = [
        t for t in all_titles
        if t.duration_sec >= min_duration_sec and t.chapters > 0
    ]
    episodic.sort(key=lambda t: t.duration_sec)

    play_all_titles = list(episodic)

    return DVDInfo(
        all_titles=all_titles,
        episodic_titles=episodic,
        play_all_titles=play_all_titles,
        longest_track_num=longest_track_num,
    )


def select_episodic_titles(
    config: Config,
    input_path: str,
    min_duration_sec: float = 300.0,
    max_duration_sec: float = 7200.0,
) -> list[DVDTitle]:
    info = scan_dvd(config, input_path, min_duration_sec=60.0)
    return [t for t in info.episodic_titles if min_duration_sec <= t.duration_sec <= max_duration_sec]


def select_play_all_titles(
    config: Config,
    input_path: str,
    min_duration_sec: float = 300.0,
    max_duration_sec: float = 7200.0,
) -> list[DVDTitle]:
    info = scan_dvd(config, input_path, min_duration_sec=60.0)
    return [t for t in info.play_all_titles if min_duration_sec <= t.duration_sec <= max_duration_sec]


def rip_title(
    config: Config,
    input_path: str,
    title: DVDTitle,
    output_dir: Path,
    disc_name: str,
) -> Path:
    outfile = output_dir / f"{sanitize_filename(disc_name)}_title{title.number:02d}.mkv"

    if outfile.exists():
        logger.info("Output already exists, skipping: %s", outfile)
        return outfile

    logger.info("Ripping title %d (%.1f sec, %d chapters) -> %s",
                title.number, title.duration_sec, title.chapters, outfile)

    cmd = [
        config.ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-v", "warning",
        "-stats",
        "-f", "dvdvideo",
        "-title", str(title.number),
        "-i", input_path,
        "-map", "0",
        "-c", "copy",
        "-y",
        str(outfile),
    ]

    run_cmd(cmd, timeout=int(title.duration_sec * 2 + 600))

    if not outfile.exists():
        raise RuntimeError(f"Rip failed: output file not created for title {title.number}")

    size_mb = outfile.stat().st_size / (1024 * 1024)
    logger.info("Ripped title %d successfully (%.1f MB)", title.number, size_mb)
    return outfile


def rip_all_titles(
    config: Config,
    input_path: str,
    output_dir: Path,
    disc_name: str,
    titles: Optional[list[DVDTitle]] = None,
) -> list[Path]:
    if not titles:
        titles = select_episodic_titles(config, input_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for title in titles:
        try:
            path = rip_title(config, input_path, title, output_dir, disc_name)
            results.append(path)
        except Exception as e:
            logger.error("Failed to rip title %d: %s", title.number, e)

    return results

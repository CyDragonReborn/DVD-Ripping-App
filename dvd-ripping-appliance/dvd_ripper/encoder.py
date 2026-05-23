import logging
import subprocess
from pathlib import Path

from .config import Config, ENCODER_PRESETS
from .utils import find_binary

logger = logging.getLogger(__name__)


def check_ffmpeg_available() -> bool:
    try:
        find_binary("ffmpeg")
        return True
    except RuntimeError:
        return False


def get_available_encoders() -> list[str]:
    return ["x264", "x264_fast", "x264_slow"]


def build_encode_cmd(config: Config, input_path: Path, output_path: Path) -> list[str]:
    preset = config.get_encoder_preset()
    encoder = preset["encoder"]
    x264_preset = preset["preset"]
    crf = preset["crf"]

    cmd = [
        config.ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-i", str(input_path),
        "-c:v", encoder,
        "-preset", x264_preset,
        "-crf", crf,
        "-c:a", "copy",
        "-movflags", "+faststart",
        "-y",
        str(output_path),
    ]

    if config.handbrake_deinterlace:
        cmd.insert(6, "-vf")
        cmd.insert(7, "yadif=1")

    if config.video_scale:
        scale_filter = f"scale={config.video_scale[0]}:{config.video_scale[1]}:force_original_aspect_ratio=decrease"
        if "-vf" in cmd:
            idx = cmd.index("-vf") + 1
            cmd[idx] = f"{cmd[idx]},{scale_filter}"
        else:
            cmd.insert(6, "-vf")
            cmd.insert(7, scale_filter)

    return cmd


def encode_to_mp4(
    config: Config,
    input_path: Path,
    output_path: Path,
    progress_callback=None,
) -> Path:
    if not check_ffmpeg_available():
        raise RuntimeError("ffmpeg not found")

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    encoder_label = config.get_encoder_label()
    logger.info("Encoding with %s: %s -> %s", encoder_label, input_path, output_path)

    cmd = build_encode_cmd(config, input_path, output_path)
    logger.info("FFmpeg command: %s", " ".join(cmd))

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    duration = None
    current_time = 0.0

    for line in process.stderr:
        if "Duration:" in line and duration is None:
            import re
            match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", line)
            if match:
                h, m, s = match.groups()
                duration = int(h) * 3600 + int(m) * 60 + float(s)
        if "time=" in line:
            import re
            match = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})", line)
            if match:
                h, m, s = match.groups()
                current_time = int(h) * 3600 + int(m) * 60 + float(s)
                if duration and progress_callback:
                    progress = min(current_time / duration * 100, 99)
                    progress_callback(progress)

    process.wait()

    if process.returncode != 0:
        stderr = process.stderr.read() if process.stderr else "no output"
        raise RuntimeError(f"Encoding failed (rc={process.returncode}):\n{stderr[-2000:]}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Encoding failed: output file not created or empty")

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("Encoding complete: %s (%.1f MB)", output_path, size_mb)
    return output_path

import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


ENCODER_PRESETS = {
    "x264": {
        "encoder": "libx264",
        "preset": "medium",
        "crf": "20",
        "label": "x264 (balanced)",
    },
    "x264_fast": {
        "encoder": "libx264",
        "preset": "veryfast",
        "crf": "22",
        "label": "x264 (fast)",
    },
    "x264_slow": {
        "encoder": "libx264",
        "preset": "slow",
        "crf": "18",
        "label": "x264 (high quality)",
    },
}

UPSCALE_PRESETS = {
    "none": None,
    "720p": (1280, 720),
    "1080p": (1920, 1080),
}

SUBTITLE_MODES = {
    "none": "No subtitles",
    "soft": "Soft subtitles (selectable)",
    "burn": "Burned-in subtitles",
}


@dataclass
class Config:
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    lsdvd_bin: str = "lsdvd"
    handbrake_bin: str = "HandBrakeCLI"

    output_dir: Path = field(default_factory=lambda: Path("/media/usb/RIPS"))
    temp_dir: Path = field(default_factory=lambda: Path("/tmp/dvd-ripper"))
    keep_temp_files: bool = False

    handbrake_encoder: str = "x264"
    handbrake_preset: str = "HQ 720p30 Surround"
    handbrake_quality: str = "20"
    handbrake_deinterlace: str = "--decomb"
    handbrake_denoise: str = "--nlmeans=light"

    subtitle_mode: str = "none"
    video_sharpen: str = "none"
    video_scale: Optional[tuple[int, int]] = None
    video_brightness: int = 0
    video_contrast: float = 1.0
    video_saturation: float = 1.0
    video_gamma: float = 1.0

    gpu_optimized: bool = False

    def set_upscale(self, preset: str) -> None:
        if preset in UPSCALE_PRESETS and UPSCALE_PRESETS[preset]:
            self.video_scale = UPSCALE_PRESETS[preset]

    def get_encoder_label(self) -> str:
        return ENCODER_PRESETS.get(self.handbrake_encoder, {}).get("label", self.handbrake_encoder)

    def get_encoder_preset(self) -> dict:
        return ENCODER_PRESETS.get(self.handbrake_encoder, ENCODER_PRESETS["x264"])

    def ensure_dirs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def cleanup_temp(self, work_dir: Path) -> None:
        if self.keep_temp_files:
            return
        if work_dir.exists():
            shutil.rmtree(work_dir)

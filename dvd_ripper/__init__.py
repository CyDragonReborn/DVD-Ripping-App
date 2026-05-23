# DVD Ripping Appliance for Raspberry Pi
"""

from .config import Config
from .ripper import scan_dvd, rip_all_titles, select_play_all_titles
from .duplicates import deduplicate_files
from .merger import merge_to_mkv
from .encoder import encode_to_mp4, get_available_encoders
from .usb import detect_usb_drives, get_best_output_path

__version__ = "1.0.0"
__all__ = [
    "Config",
    "scan_dvd",
    "rip_all_titles",
    "select_play_all_titles",
    "deduplicate_files",
    "merge_to_mkv",
    "encode_to_mp4",
    "get_available_encoders",
    "detect_usb_drives",
    "get_best_output_path",
]

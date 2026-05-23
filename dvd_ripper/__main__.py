#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dvd_ripper.config import Config
from dvd_ripper.utils import validate_dependencies, sanitize_filename, get_dvd_device, is_dvd_inserted
from dvd_ripper.ripper import scan_dvd, rip_all_titles, select_play_all_titles
from dvd_ripper.duplicates import deduplicate_files
from dvd_ripper.merger import merge_to_mkv
from dvd_ripper.encoder import encode_to_mp4, get_available_encoders
from dvd_ripper.usb import detect_usb_drives, get_best_output_path

logger = logging.getLogger("dvd-rip")


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_scan(args):
    config = Config()
    device = args.device or get_dvd_device()
    if not device:
        print("No DVD drive detected. Specify with --device /dev/sr0")
        sys.exit(1)

    if not is_dvd_inserted(device):
        print(f"No DVD detected in {device}")
        sys.exit(1)

    info = scan_dvd(config, device)
    print(f"\nDVD Titles on {device}:")
    print(f"{'Title':<8} {'Duration':<12} {'Chapters':<10} {'Audio':<8} {'Subs':<8}")
    print("-" * 50)
    for t in info.episodic_titles:
        mins = t.duration_sec / 60
        print(f"{t.number:<8} {mins:<12.1f} {t.chapters:<10} {t.audio_tracks:<8} {t.subtitle_tracks:<8}")
    print(f"\nTotal episodic titles: {len(info.episodic_titles)}")


def cmd_rip(args):
    config = Config()
    config.ensure_dirs()
    config.handbrake_encoder = args.encoder
    config.handbrake_quality = str(args.quality)
    config.handbrake_deinterlace = "--decomb" if not args.no_deinterlace else ""
    config.handbrake_denoise = "--nlmeans=light" if not args.no_denoise else ""
    config.subtitle_mode = args.subtitle
    config.set_upscale(args.upscale)
    if args.keep_temp:
        config.keep_temp_files = True

    device = args.device or get_dvd_device()
    if not device:
        print("No DVD drive detected. Specify with --device /dev/sr0")
        sys.exit(1)

    missing = validate_dependencies(config)
    if missing:
        print(f"Missing: {', '.join(missing)}")
        print("Run: sudo bash scripts/setup.sh")
        sys.exit(1)

    if not is_dvd_inserted(device):
        print(f"No DVD detected in {device}")
        sys.exit(1)

    disc_name = sanitize_filename(args.name or Path(device).stem or "dvd")

    usb_drives = detect_usb_drives()
    if usb_drives:
        best = max(usb_drives, key=lambda d: d.free_gb)
        config.output_dir = best.mount_point / "RIPS"
        config.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output: {config.output_dir} ({best.label}, {best.free_gb}GB free)")

    print(f"\nRipping: {device}")
    print(f"Name: {disc_name}")
    print(f"Encoder: {config.get_encoder_label()}")
    print(f"Quality: CRF {config.handbrake_quality}")
    print()

    info = scan_dvd(config, device)

    if args.play_all:
        titles = select_play_all_titles(config, device)
        print(f"Play All mode: {len(titles)} titles")
    else:
        titles = info.episodic_titles
        print(f"Found {len(titles)} episodic titles")

    rip_dir = config.temp_dir / f"{disc_name}" / "rips"
    ripped = rip_all_titles(config, device, rip_dir, disc_name, titles)
    if not ripped:
        print("No files ripped!")
        sys.exit(1)

    print(f"\nRipped {len(ripped)} files")

    print("Checking duplicates...")
    unique = deduplicate_files(config, ripped)
    print(f"Unique files: {len(unique)}")

    merged = config.temp_dir / f"{disc_name}_merged.mkv"
    print("Merging...")
    if len(unique) == 1:
        import shutil
        shutil.copy2(unique[0], merged)
    else:
        merge_to_mkv(config, unique, merged)

    output = config.output_dir / f"{disc_name}.mp4"
    print(f"Encoding to {output}...")
    encode_to_mp4(config, merged, output)

    if not config.keep_temp_files:
        import shutil
        work_dir = rip_dir.parent
        if work_dir.exists():
            shutil.rmtree(work_dir)
        if merged.exists():
            merged.unlink(missing_ok=True)

    print(f"\nDone! Output: {output}")
    print(f"Size: {output.stat().st_size / (1024*1024):.1f} MB")


def cmd_drives(args):
    drives = detect_usb_drives()
    if not drives:
        print("No USB drives detected")
        return
    for d in drives:
        print(f"{d.device} - {d.label} ({d.filesystem})")
        print(f"  Mount: {d.mount_point}")
        print(f"  Size: {d.total_gb}GB total, {d.free_gb}GB free")
        print()


def main():
    parser = argparse.ArgumentParser(description="DVD Ripping Appliance CLI")
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="Scan DVD for titles")
    scan_parser.add_argument("--device", "-d", help="DVD device (default: auto-detect)")

    rip_parser = subparsers.add_parser("rip", help="Rip a DVD")
    rip_parser.add_argument("--device", "-d", help="DVD device (default: auto-detect)")
    rip_parser.add_argument("--name", "-n", help="Disc name")
    rip_parser.add_argument("--encoder", choices=["x264", "x264_fast", "x264_slow"], default="x264")
    rip_parser.add_argument("--quality", type=int, default=20, help="CRF quality (16-28, lower=better)")
    rip_parser.add_argument("--upscale", choices=["none", "720p", "1080p"], default="none")
    rip_parser.add_argument("--subtitle", choices=["none", "soft", "burn"], default="none")
    rip_parser.add_argument("--play-all", action="store_true", help="Rip all titles")
    rip_parser.add_argument("--no-deinterlace", action="store_true")
    rip_parser.add_argument("--no-denoise", action="store_true")
    rip_parser.add_argument("--keep-temp", action="store_true")

    drives_parser = subparsers.add_parser("drives", help="List USB drives")

    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    setup_logging(args.verbose)

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "rip":
        cmd_rip(args)
    elif args.command == "drives":
        cmd_drives(args)


if __name__ == "__main__":
    main()

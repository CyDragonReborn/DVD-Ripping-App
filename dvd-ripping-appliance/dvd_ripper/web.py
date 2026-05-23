#!/usr/bin/env python3
import os
import sys
import json
import logging
import threading
import time
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request

sys.path.insert(0, str(Path(__file__).parent.parent))

from dvd_ripper.config import Config
from dvd_ripper.utils import validate_dependencies, sanitize_filename, get_dvd_device, is_dvd_inserted
from dvd_ripper.ripper import scan_dvd, rip_all_titles, select_play_all_titles, DVDTitle
from dvd_ripper.duplicates import deduplicate_files
from dvd_ripper.merger import merge_to_mkv
from dvd_ripper.encoder import encode_to_mp4, get_available_encoders
from dvd_ripper.usb import detect_usb_drives, get_best_output_path, check_usb_space, warn_fat32

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dvd-ripper-web")

app = Flask(__name__)

ripper_state = {
    "running": False,
    "step": "",
    "progress": 0,
    "message": "",
    "error": None,
    "complete": False,
    "output_file": None,
    "start_time": None,
    "elapsed": 0,
}
ripper_lock = threading.Lock()
ripper_thread = None


def update_state(step="", progress=None, message="", error=None, complete=False, output_file=None):
    with ripper_lock:
        if step:
            ripper_state["step"] = step
        if progress is not None:
            ripper_state["progress"] = progress
        if message:
            ripper_state["message"] = message
        if error:
            ripper_state["error"] = error
            ripper_state["running"] = False
        if complete:
            ripper_state["complete"] = True
            ripper_state["running"] = False
            ripper_state["progress"] = 100
        if output_file:
            ripper_state["output_file"] = str(output_file)
        if ripper_state["start_time"]:
            ripper_state["elapsed"] = time.time() - ripper_state["start_time"]


def run_rip_pipeline(input_path, config, play_all=False, name=""):
    global ripper_state
    with ripper_lock:
        ripper_state = {
            "running": True,
            "step": "initializing",
            "progress": 0,
            "message": "Starting...",
            "error": None,
            "complete": False,
            "output_file": None,
            "start_time": time.time(),
            "elapsed": 0,
        }

    try:
        missing = validate_dependencies(config)
        if missing:
            update_state(error=f"Missing dependencies: {', '.join(missing)}")
            return

        update_state(step="scanning", progress=5, message="Scanning DVD...")
        disc_name = name or Path(input_path).stem or "dvd"
        disc_name = sanitize_filename(disc_name)

        dvd_info = scan_dvd(config, input_path)
        title_count = len(dvd_info.episodic_titles)
        update_state(
            step="scanning",
            progress=10,
            message=f"Found {title_count} titles on disc",
        )

        update_state(step="ripping", progress=15, message="Ripping titles...")
        rip_dir = config.temp_dir / f"{disc_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}" / "rips"
        rip_dir.mkdir(parents=True, exist_ok=True)

        if play_all:
            titles = select_play_all_titles(config, input_path)
        else:
            titles = dvd_info.episodic_titles

        ripped_files = []
        for i, title in enumerate(titles):
            update_state(
                step="ripping",
                progress=15 + int((i / max(len(titles), 1)) * 40),
                message=f"Ripping title {title.number} ({i+1}/{len(titles)})...",
            )
            try:
                path = rip_title_for_web(config, input_path, title, rip_dir, disc_name)
                ripped_files.append(path)
            except Exception as e:
                logger.error("Failed to rip title %d: %s", title.number, e)

        if not ripped_files:
            update_state(error="No files ripped. The disc may be damaged or unsupported.")
            return

        update_state(step="deduplicating", progress=60, message="Checking for duplicates...")
        unique_files = deduplicate_files(config, ripped_files)

        update_state(step="merging", progress=70, message="Merging episodes...")
        merged_mkv = config.temp_dir / f"{disc_name}_merged.mkv"
        if len(unique_files) == 1:
            import shutil
            shutil.copy2(unique_files[0], merged_mkv)
        else:
            merge_to_mkv(config, unique_files, merged_mkv)

        update_state(step="encoding", progress=80, message="Encoding to MP4...")
        output_path = config.output_dir / f"{disc_name}.mp4"

        def encode_progress(pct):
            update_state(
                step="encoding",
                progress=80 + int(pct * 0.15),
                message=f"Encoding... {int(pct)}%",
            )

        encode_to_mp4(config, merged_mkv, output_path, progress_callback=encode_progress)

        if not config.keep_temp_files:
            import shutil
            work_dir = rip_dir.parent
            if work_dir.exists():
                shutil.rmtree(work_dir)
            if merged_mkv.exists():
                merged_mkv.unlink(missing_ok=True)

        update_state(
            step="complete",
            progress=100,
            message="Done!",
            complete=True,
            output_file=output_path,
        )

    except Exception as e:
        logger.exception("Pipeline failed")
        update_state(error=str(e))


def rip_title_for_web(config, input_path, title, output_dir, disc_name):
    from dvd_ripper.ripper import rip_title
    return rip_title(config, input_path, title, output_dir, disc_name)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    with ripper_lock:
        return jsonify(ripper_state)


@app.route("/api/scan")
def api_scan():
    device = request.args.get("device", "/dev/sr0")
    try:
        config = Config()
        config.ensure_dirs()
        info = scan_dvd(config, device)
        titles = []
        for t in info.episodic_titles:
            titles.append({
                "number": t.number,
                "duration_sec": t.duration_sec,
                "duration_min": round(t.duration_sec / 60, 1),
                "chapters": t.chapters,
                "audio_tracks": t.audio_tracks,
                "subtitle_tracks": t.subtitle_tracks,
            })
        return jsonify({
            "ok": True,
            "device": device,
            "title_count": len(titles),
            "titles": titles,
            "longest_track": info.longest_track_num,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/rip", methods=["POST"])
def api_rip():
    global ripper_thread

    with ripper_lock:
        if ripper_state["running"]:
            return jsonify({"ok": False, "error": "Rip already in progress"})

    data = request.get_json(force=True)
    device = data.get("device", "/dev/sr0")
    name = data.get("name", "")
    encoder = data.get("encoder", "x264")
    quality = data.get("quality", "20")
    play_all = data.get("play_all", False)
    deinterlace = data.get("deinterlace", True)
    upscale = data.get("upscale", "none")
    subtitle = data.get("subtitle", "none")

    config = Config()
    config.ensure_dirs()
    config.handbrake_encoder = encoder
    config.handbrake_quality = str(quality)
    config.handbrake_deinterlace = "--decomb" if deinterlace else ""
    config.handbrake_denoise = "--nlmeans=light" if deinterlace else ""
    config.subtitle_mode = subtitle
    config.set_upscale(upscale)

    usb_drives = detect_usb_drives()
    if usb_drives:
        best = max(usb_drives, key=lambda d: d.free_gb)
        config.output_dir = best.mount_point / "RIPS"
        config.output_dir.mkdir(parents=True, exist_ok=True)

    if not is_dvd_inserted(device):
        return jsonify({"ok": False, "error": f"No DVD detected in {device}"})

    ripper_thread = threading.Thread(
        target=run_rip_pipeline,
        args=(device, config),
        kwargs={"play_all": play_all, "name": name},
        daemon=True,
    )
    ripper_thread.start()

    return jsonify({"ok": True, "message": "Rip started"})


@app.route("/api/drives")
def api_drives():
    drives = detect_usb_drives()
    result = []
    for d in drives:
        is_fat32 = warn_fat32(d.mount_point)
        result.append({
            "device": d.device,
            "mount_point": str(d.mount_point),
            "filesystem": d.filesystem,
            "total_gb": d.total_gb,
            "free_gb": d.free_gb,
            "label": d.label,
            "is_fat32": is_fat32,
        })
    return jsonify({"drives": result})


@app.route("/api/dvd_status")
def api_dvd_status():
    device = request.args.get("device", "/dev/sr0")
    inserted = is_dvd_inserted(device)
    return jsonify({"device": device, "inserted": inserted})


@app.route("/api/encoders")
def api_encoders():
    return jsonify({"encoders": get_available_encoders()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

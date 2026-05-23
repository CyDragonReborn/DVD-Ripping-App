import logging
from pathlib import Path

from .config import Config
from .utils import run_cmd

logger = logging.getLogger(__name__)


def build_concat_file(files: list[Path], concat_file: Path) -> Path:
    with open(concat_file, "w") as f:
        for file_path in files:
            f.write(f"file '{file_path.absolute()}'\n")
    return concat_file


def merge_to_mkv(
    config: Config,
    files: list[Path],
    output_path: Path,
) -> Path:
    if len(files) == 1:
        import shutil
        shutil.copy2(files[0], output_path)
        logger.info("Single file, copied to: %s", output_path)
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    concat_file = output_path.parent / "concat_list.txt"
    build_concat_file(files, concat_file)

    logger.info("Merging %d files -> %s", len(files), output_path)

    cmd = [
        config.ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-v", "warning",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        "-y",
        str(output_path),
    ]

    run_cmd(cmd, timeout=7200)

    if not output_path.exists():
        raise RuntimeError("Merge failed: output file not created")

    concat_file.unlink(missing_ok=True)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("Merge complete: %s (%.1f MB)", output_path, size_mb)
    return output_path

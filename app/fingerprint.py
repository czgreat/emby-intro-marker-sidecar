from __future__ import annotations

from hashlib import sha1
from pathlib import Path
import json
import logging
import subprocess
import struct


LOGGER = logging.getLogger("intro_marker.fingerprint")


def _run(command: list[str]) -> str:
    LOGGER.debug("Running command: %s", " ".join(command))
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def probe_duration_seconds(path: Path) -> float:
    output = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return float(output)


def fingerprint_similarity(left: list[int], right: list[int]) -> float:
    compared = min(len(left), len(right))
    if compared <= 0:
        return 0.0
    diff_bits = 0
    for index in range(compared):
        diff_bits += (left[index] ^ right[index]).bit_count()
    total_bits = compared * 32
    return max(0.0, 1.0 - (diff_bits / total_bits))


def _cache_key(path: Path, start_seconds: float, duration_seconds: float, sample_rate: int, channels: int) -> str:
    stat = path.stat()
    material = f"ffmpeg-raw-v1|{path}|{stat.st_mtime_ns}|{stat.st_size}|{start_seconds:.3f}|{duration_seconds:.3f}|{sample_rate}|{channels}"
    return sha1(material.encode("utf-8")).hexdigest()


def compute_window_fingerprint(
    path: Path,
    start_seconds: float,
    duration_seconds: float,
    cache_dir: Path,
    work_dir: Path,
    sample_rate: int,
    channels: int,
) -> list[int]:
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_file = cache_dir / f"{_cache_key(path, start_seconds, duration_seconds, sample_rate, channels)}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))["fingerprint"]

    work_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            str(path),
            "-t",
            f"{duration_seconds:.3f}",
            "-vn",
            "-ac",
            str(max(1, min(2, channels))),
            "-ar",
            str(sample_rate),
            "-f",
            "chromaprint",
            "-fp_format",
            "raw",
            "-",
        ],
        check=True,
        capture_output=True,
    )

    raw = completed.stdout
    if not raw or len(raw) % 4 != 0:
        raise RuntimeError(f"ffmpeg chromaprint output was malformed for {path}")

    fingerprint = [value[0] for value in struct.iter_unpack("<I", raw)]
    cache_file.write_text(json.dumps({"fingerprint": fingerprint}), encoding="utf-8")
    return fingerprint

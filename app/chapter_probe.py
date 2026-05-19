from __future__ import annotations

from hashlib import sha1
from pathlib import Path
import json
import subprocess


def _cache_key(path: Path) -> str:
    stat = path.stat()
    material = f"chapters-v1|{path}|{stat.st_mtime_ns}|{stat.st_size}"
    return sha1(material.encode("utf-8")).hexdigest()


def load_chapters(path: Path, cache_dir: Path) -> list[dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{_cache_key(path)}.chapters.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_chapters",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    chapters = []
    for chapter in payload.get("chapters", []):
        chapters.append(
            {
                "title": chapter.get("tags", {}).get("title", ""),
                "start": float(chapter["start_time"]),
                "end": float(chapter["end_time"]),
                "duration": float(chapter["end_time"]) - float(chapter["start_time"]),
            }
        )
    cache_file.write_text(json.dumps(chapters, ensure_ascii=True), encoding="utf-8")
    return chapters

from __future__ import annotations

from pathlib import Path
import logging
import os
import re

from .models import EpisodeCandidate, SeasonCandidate


LOGGER = logging.getLogger("intro_marker.discovery")

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".wmv", ".strm"}
SKIP_DIR_NAMES = {"extras", "specials", "featurettes", "trailers", "samples"}
EPISODE_PATTERNS = [
    re.compile(r"S\d{1,2}E(\d{1,3})", re.IGNORECASE),
    re.compile(r"\[(\d{1,3})\](?!.*\[\d{1,3}\])"),
    re.compile(r"(?:第)(\d{1,3})(?:话|集)", re.IGNORECASE),
]


def _episode_number(path: Path) -> int | None:
    name = path.stem
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(name)
        if match:
            return int(match.group(1))
    return None


def _root_name(path: Path, roots: list[Path]) -> str:
    normalized = str(path).replace("\\", "/")
    for root in roots:
        root_text = str(root).replace("\\", "/")
        if normalized.startswith(root_text):
            return root.name
    return "root"


def discover_seasons(roots: list[Path], excluded_roots: list[Path], min_episodes: int) -> list[SeasonCandidate]:
    seasons: list[SeasonCandidate] = []
    excluded = {str(root.resolve()) for root in excluded_roots if root.exists()}

    for root in roots:
        if not root.exists():
            LOGGER.warning("Media root does not exist: %s", root)
            continue

        for directory, dirnames, filenames in os.walk(root):
            season_path = Path(directory)
            if str(season_path.resolve()) in excluded:
                dirnames[:] = []
                continue

            dirnames[:] = [name for name in dirnames if name.lower() not in SKIP_DIR_NAMES]
            media_files = [
                season_path / filename
                for filename in filenames
                if (season_path / filename).suffix.lower() in VIDEO_EXTENSIONS
            ]
            if len(media_files) < min_episodes:
                continue

            media_files.sort(
                key=lambda item: (
                    _episode_number(item) is None,
                    _episode_number(item) or 9999,
                    item.name.lower(),
                )
            )
            episodes = [
                EpisodeCandidate(
                    path=item,
                    series_name=season_path.parent.name,
                    season_name=season_path.name,
                    episode_label=item.stem,
                    episode_number=_episode_number(item),
                    root_name=_root_name(item, roots),
                    extension=item.suffix.lower(),
                    size_bytes=item.stat().st_size,
                )
                for item in media_files
            ]
            seasons.append(
                SeasonCandidate(
                    season_path=season_path,
                    root_name=_root_name(season_path, roots),
                    series_name=season_path.parent.name,
                    season_name=season_path.name,
                    episodes=episodes,
                )
            )

    seasons.sort(
        key=lambda item: (
            item.root_name != "vcb",
            any(episode.extension == ".strm" for episode in item.episodes),
            abs(len(item.episodes) - 12),
            item.series_name.lower(),
            item.season_name.lower(),
        )
    )
    LOGGER.info("Discovered %s season candidates", len(seasons))
    return seasons

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class EpisodeCandidate:
    path: Path
    series_name: str
    season_name: str
    episode_label: str
    episode_number: int | None
    root_name: str
    extension: str
    size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = str(self.path)
        return payload


@dataclass(slots=True)
class SeasonCandidate:
    season_path: Path
    root_name: str
    series_name: str
    season_name: str
    episodes: list[EpisodeCandidate]

    @property
    def season_key(self) -> str:
        return f"{self.series_name}::{self.season_name}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "season_path": str(self.season_path),
            "root_name": self.root_name,
            "series_name": self.series_name,
            "season_name": self.season_name,
            "episode_count": len(self.episodes),
            "episodes": [episode.to_dict() for episode in self.episodes],
        }


@dataclass(slots=True)
class WindowFingerprint:
    episode_path: Path
    zone: str
    start_seconds: float
    duration_seconds: float
    fingerprint: list[int]
    index: int


@dataclass(slots=True)
class ZoneEpisodeMatch:
    episode_path: Path
    marker_start_seconds: float
    marker_end_seconds: float
    anchor_similarity: float
    mean_similarity: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["episode_path"] = str(self.episode_path)
        return payload


@dataclass(slots=True)
class ZoneDetection:
    zone: str
    method: str
    detected: bool
    confidence: float
    support_episodes: int
    required_support: int = 0
    threshold_similarity: float | None = None
    mean_similarity: float | None = None
    min_similarity_observed: float | None = None
    max_similarity_observed: float | None = None
    season_start_seconds: float | None = None
    season_end_seconds: float | None = None
    matched_episodes: list[ZoneEpisodeMatch] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone": self.zone,
            "method": self.method,
            "detected": self.detected,
            "confidence": round(self.confidence, 4),
            "support_episodes": self.support_episodes,
            "required_support": self.required_support,
            "threshold_similarity": self.threshold_similarity,
            "mean_similarity": self.mean_similarity,
            "min_similarity_observed": self.min_similarity_observed,
            "max_similarity_observed": self.max_similarity_observed,
            "season_start_seconds": self.season_start_seconds,
            "season_end_seconds": self.season_end_seconds,
            "matched_episodes": [match.to_dict() for match in self.matched_episodes],
            "notes": self.notes,
        }


@dataclass(slots=True)
class SeasonScanReport:
    season_key: str
    season_path: str
    episode_count: int
    op: ZoneDetection
    ed: ZoneDetection
    selected_by: str
    dry_run: bool
    schema_summary: dict[str, Any] | None = None
    writeback_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "season_key": self.season_key,
            "season_path": self.season_path,
            "episode_count": self.episode_count,
            "selected_by": self.selected_by,
            "dry_run": self.dry_run,
            "op": self.op.to_dict(),
            "ed": self.ed.to_dict(),
            "schema_summary": self.schema_summary,
            "writeback_summary": self.writeback_summary,
        }

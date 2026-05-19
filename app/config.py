from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

import yaml


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw is not None else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw is not None else default


def _load_yaml(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _lookup(config: dict, *keys: str, default=None):
    current = config
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


@dataclass(slots=True)
class Settings:
    time_zone: str
    emby_base_url: str
    emby_api_key: replace-me
    emby_server_id: str
    emby_user_id: str
    include_library_names: list[str]
    emby_db_path: Path
    emby_db_table: str
    sqlite_template_path: Path | None
    media_roots: list[Path]
    excluded_roots: list[Path]
    discovery_min_episodes: int
    status_http_port: int
    run_mode: str
    cron_expression: str
    poll_enabled: bool
    poll_interval_minutes: int
    nightly_enabled: bool
    nightly_hour: int
    nightly_minute: int
    max_parallel_jobs: int
    max_parallel_ffmpeg: int
    detector_mode: str
    chapter_detection_enabled: bool
    chapter_duration_min_seconds: int
    chapter_duration_max_seconds: int
    audio_sample_rate: int
    audio_channels: int
    fingerprint_window_seconds: int
    fingerprint_hop_seconds: int
    min_episode_count: int
    min_cluster_episodes: int
    min_support_ratio: float
    min_similarity: float
    op_search_min_seconds: int
    op_search_max_seconds: int
    ed_search_from_end_seconds: int
    min_marker_seconds: int
    max_marker_seconds: int
    op_position_tolerance_seconds: float
    ed_tail_tolerance_seconds: float
    enable_blackframe_refine: bool
    enable_silence_refine: bool
    blackframe_amount: int
    blackframe_threshold: float
    silence_noise_db: float
    silence_min_seconds: float
    enable_db_backup: bool
    db_busy_timeout_ms: int
    dry_run: bool
    write_ed_as_second_intro_pair: bool
    cache_dir: Path
    work_dir: Path
    report_dir: Path

    @classmethod
    def load(cls) -> "Settings":
        yaml_path = Path(os.environ.get("INTRO_MARKER_CONFIG", "/app/config/detector.yml"))
        config = _load_yaml(yaml_path)

        media_roots_raw = os.environ.get("MEDIA_ROOTS")
        if media_roots_raw:
            media_roots = [Path(part.strip()) for part in media_roots_raw.split(",") if part.strip()]
        else:
            media_roots = [Path(value) for value in _lookup(config, "libraries", "include_roots", default=[])]

        include_library_names_raw = os.environ.get("INCLUDE_LIBRARY_NAMES")
        if include_library_names_raw:
            include_library_names = [part.strip() for part in include_library_names_raw.split(",") if part.strip()]
        else:
            include_library_names = list(_lookup(config, "libraries", "include_library_names", default=["电视剧", "动漫"]))

        excluded_roots = [Path(value) for value in _lookup(config, "libraries", "exclude_roots", default=[])]

        sqlite_template_raw = os.environ.get("SQLITE_TEMPLATE_PATH")
        sqlite_template_path = Path(sqlite_template_raw) if sqlite_template_raw else None

        return cls(
            time_zone=os.environ.get("TZ", _lookup(config, "service", "time_zone", default="Asia/Hong_Kong")),
            emby_base_url=os.environ.get("EMBY_BASE_URL", _lookup(config, "emby", "base_url", default="")).rstrip("/"),
            emby_api_key=os.environ.get("EMBY_API_KEY", ""),
            emby_server_id=os.environ.get("EMBY_SERVER_ID", _lookup(config, "emby", "server_id", default="")),
            emby_user_id=os.environ.get("EMBY_USER_ID", ""),
            include_library_names=include_library_names,
            emby_db_path=Path(os.environ.get("EMBY_DB_PATH", _lookup(config, "emby", "db_path", default="/emby-config/data/library.db"))),
            emby_db_table=os.environ.get("EMBY_DB_TABLE", _lookup(config, "emby", "db_table", default="Chapters3")),
            sqlite_template_path=sqlite_template_path,
            media_roots=media_roots,
            excluded_roots=excluded_roots,
            discovery_min_episodes=_env_int("DISCOVERY_MIN_EPISODES", _lookup(config, "libraries", "discovery_min_episodes", default=1)),
            status_http_port=_env_int("STATUS_HTTP_PORT", _lookup(config, "service", "listen_port", default=8080)),
            run_mode=os.environ.get("RUN_MODE", _lookup(config, "schedule", "mode", default="manual")),
            cron_expression=os.environ.get("CRON_EXPRESSION", _lookup(config, "schedule", "cron", default="30 3 * * *")),
            poll_enabled=_env_bool("POLL_ENABLED", _lookup(config, "schedule", "poll", "enabled", default=True)),
            poll_interval_minutes=_env_int("POLL_INTERVAL_MINUTES", _lookup(config, "schedule", "poll", "interval_minutes", default=30)),
            nightly_enabled=_env_bool("NIGHTLY_ENABLED", _lookup(config, "schedule", "nightly", "enabled", default=True)),
            nightly_hour=_env_int("NIGHTLY_HOUR", _lookup(config, "schedule", "nightly", "hour", default=3)),
            nightly_minute=_env_int("NIGHTLY_MINUTE", _lookup(config, "schedule", "nightly", "minute", default=30)),
            max_parallel_jobs=_env_int("MAX_PARALLEL_JOBS", _lookup(config, "schedule", "max_parallel_jobs", default=1)),
            max_parallel_ffmpeg=_env_int("MAX_PARALLEL_FFMPEG", _lookup(config, "schedule", "max_parallel_ffmpeg", default=1)),
            detector_mode=os.environ.get("DETECTOR_MODE", _lookup(config, "detection", "strategy", default="audio_fingerprint")),
            chapter_detection_enabled=_env_bool("CHAPTER_DETECTION_ENABLED", _lookup(config, "detection", "chapter_heuristic", "enabled", default=True)),
            chapter_duration_min_seconds=_env_int("CHAPTER_DURATION_MIN_SECONDS", _lookup(config, "detection", "chapter_heuristic", "duration_min_seconds", default=85)),
            chapter_duration_max_seconds=_env_int("CHAPTER_DURATION_MAX_SECONDS", _lookup(config, "detection", "chapter_heuristic", "duration_max_seconds", default=120)),
            audio_sample_rate=_env_int("AUDIO_SAMPLE_RATE", _lookup(config, "detection", "audio", "sample_rate", default=11025)),
            audio_channels=_env_int("AUDIO_CHANNELS", _lookup(config, "detection", "audio", "channels", default=1)),
            fingerprint_window_seconds=_env_int("FINGERPRINT_WINDOW_SECONDS", _lookup(config, "detection", "audio", "fingerprint_window_seconds", default=12)),
            fingerprint_hop_seconds=_env_int("FINGERPRINT_HOP_SECONDS", _lookup(config, "detection", "audio", "fingerprint_hop_seconds", default=3)),
            min_episode_count=_env_int("MIN_EPISODE_COUNT", _lookup(config, "detection", "min_episode_count", default=4)),
            min_cluster_episodes=_env_int("MIN_CLUSTER_EPISODES", _lookup(config, "detection", "min_cluster_episodes", default=3)),
            min_support_ratio=_env_float("MIN_SUPPORT_RATIO", _lookup(config, "detection", "min_support_ratio", default=0.50)),
            min_similarity=_env_float("MIN_SIMILARITY", _lookup(config, "detection", "similarity_threshold", default=0.92)),
            op_search_min_seconds=_env_int("OP_SEARCH_MIN_SECONDS", _lookup(config, "detection", "op", "search_min_seconds", default=18)),
            op_search_max_seconds=_env_int("OP_SEARCH_MAX_SECONDS", _lookup(config, "detection", "op", "search_max_seconds", default=480)),
            ed_search_from_end_seconds=_env_int("ED_SEARCH_FROM_END_SECONDS", _lookup(config, "detection", "ed", "search_from_end_seconds", default=360)),
            min_marker_seconds=_env_int("MIN_MARKER_SECONDS", _lookup(config, "detection", "op", "min_duration_seconds", default=45)),
            max_marker_seconds=_env_int("MAX_MARKER_SECONDS", _lookup(config, "detection", "op", "max_duration_seconds", default=150)),
            op_position_tolerance_seconds=_env_float("OP_POSITION_TOLERANCE_SECONDS", _lookup(config, "detection", "op", "position_tolerance_seconds", default=36.0)),
            ed_tail_tolerance_seconds=_env_float("ED_TAIL_TOLERANCE_SECONDS", _lookup(config, "detection", "ed", "tail_tolerance_seconds", default=45.0)),
            enable_blackframe_refine=_env_bool("ENABLE_BLACKFRAME_REFINE", _lookup(config, "detection", "refine", "blackframe", "enabled", default=True)),
            enable_silence_refine=_env_bool("ENABLE_SILENCE_REFINE", _lookup(config, "detection", "refine", "silence", "enabled", default=True)),
            blackframe_amount=_env_int("BLACKFRAME_AMOUNT", _lookup(config, "detection", "refine", "blackframe", "amount", default=98)),
            blackframe_threshold=_env_float("BLACKFRAME_THRESHOLD", _lookup(config, "detection", "refine", "blackframe", "threshold", default=0.20)),
            silence_noise_db=_env_float("SILENCE_NOISE_DB", _lookup(config, "detection", "refine", "silence", "noise_db", default=-35.0)),
            silence_min_seconds=_env_float("SILENCE_MIN_SECONDS", _lookup(config, "detection", "refine", "silence", "min_seconds", default=0.40)),
            enable_db_backup=_env_bool("ENABLE_DB_BACKUP", _lookup(config, "writeback", "backup_before_write", default=True)),
            db_busy_timeout_ms=_env_int("DB_BUSY_TIMEOUT_MS", _lookup(config, "writeback", "busy_timeout_ms", default=5000)),
            dry_run=_env_bool("DRY_RUN", _lookup(config, "writeback", "dry_run", default=True)),
            write_ed_as_second_intro_pair=_env_bool("WRITE_ED_AS_SECOND_INTRO_PAIR", _lookup(config, "detection", "ed", "write_as_second_intro_pair", default=True)),
            cache_dir=Path("/var/lib/intro-marker/cache"),
            work_dir=Path("/var/lib/intro-marker/work"),
            report_dir=Path("/var/log/intro-marker"),
        )

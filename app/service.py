from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import json
import logging
import statistics
from threading import Lock
from typing import Any

from .config import Settings
from .detector import scan_season
from .emby_client import EmbyClient
from .media_discovery import discover_seasons
from .sample_selector import choose_sample_season
from .sqlite_writer import SQLiteWriteback


LOGGER = logging.getLogger("intro_marker.service")


class IntroMarkerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._default_library_names = list(settings.include_library_names)
        self.emby_client = EmbyClient(
            base_url=settings.emby_base_url,
            api_key=settings.emby_api_key,
            user_id=settings.emby_user_id,
        )
        self.sqlite_writer = SQLiteWriteback(settings, self.emby_client)
        self.scheduler = BackgroundScheduler(timezone=settings.time_zone)
        self._lock = Lock()
        self._last_report: dict[str, Any] | None = None
        self._overrides_path = self.settings.work_dir / "runtime_overrides.json"
        self._season_state_path = self.settings.work_dir / "season_state.json"
        self._batch_status_path = self.settings.work_dir / "current_batch_status.json"
        self._batch_log_path = self.settings.work_dir / "current_batch_log.json"
        self._season_state: dict[str, Any] = {}
        self._load_runtime_overrides()
        self._load_season_state()

    def _zone_summary(self, zone_payload: dict[str, Any]) -> dict[str, Any]:
        notes = zone_payload.get("notes") or []
        matched = zone_payload.get("matched_episodes") or []
        return {
            "method": zone_payload.get("method"),
            "detected": zone_payload.get("detected"),
            "support_episodes": zone_payload.get("support_episodes"),
            "required_support": zone_payload.get("required_support"),
            "threshold_similarity": zone_payload.get("threshold_similarity"),
            "mean_similarity": zone_payload.get("mean_similarity"),
            "season_start_seconds": zone_payload.get("season_start_seconds"),
            "season_end_seconds": zone_payload.get("season_end_seconds"),
            "matched_count": len(matched),
            "notes": notes,
            "headline": notes[0] if notes else None,
        }

    def _report_batch_item(self, report: dict[str, Any]) -> dict[str, Any]:
        season_key = str(report.get("season_key") or "")
        series_name, _, season_name = season_key.partition("::")
        return {
            "season_key": season_key,
            "series_name": series_name or None,
            "season_name": season_name or None,
            "season_path": report.get("season_path"),
            "episode_count": report.get("episode_count"),
            "selected_by": report.get("selected_by"),
            "dry_run": report.get("dry_run"),
            "op": self._zone_summary(report.get("op") or {}),
            "ed": self._zone_summary(report.get("ed") or {}),
        }

    def _persist_batch_snapshot(self, *, mode: str, reports: list[dict[str, Any]]) -> None:
        self.settings.work_dir.mkdir(parents=True, exist_ok=True)
        items = [self._report_batch_item(report) for report in reports]
        payload = {
            "status": "completed",
            "mode": mode,
            "started_at": datetime.now().astimezone().isoformat(),
            "updated_at": datetime.now().astimezone().isoformat(),
            "total": len(items),
            "completed": len(items),
            "current": None,
            "results": items,
        }
        self._batch_status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._batch_log_path.write_text(json.dumps(items[-100:], ensure_ascii=False, indent=2), encoding="utf-8")

    def _normalize_library_names(self, value: Any) -> list[str]:
        if isinstance(value, str):
            requested = [part.strip() for part in value.split(",") if part.strip()]
        elif isinstance(value, list):
            requested = [str(part).strip() for part in value if str(part).strip()]
        else:
            requested = []

        try:
            available_names = {folder.get("Name", "") for folder in self.emby_client.list_virtual_folders()}
        except Exception:
            available_names = set(self._default_library_names)

        normalized = [name for name in requested if name in available_names]
        if normalized:
            return normalized
        fallback = [name for name in self._default_library_names if name in available_names] or list(self._default_library_names)
        return fallback

    def start(self) -> None:
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)
        self.settings.work_dir.mkdir(parents=True, exist_ok=True)
        self.settings.report_dir.mkdir(parents=True, exist_ok=True)
        self.configure_scheduler()

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def configure_scheduler(self) -> None:
        if self.scheduler.running:
            self.scheduler.remove_all_jobs()

        if self.settings.run_mode == "scheduled":
            if self.settings.poll_enabled:
                self.scheduler.add_job(
                    self.run_incremental_poll,
                    trigger=IntervalTrigger(minutes=self.settings.poll_interval_minutes, timezone=self.settings.time_zone),
                    id="incremental-poll",
                    replace_existing=True,
                    coalesce=True,
                    max_instances=1,
                )
            if self.settings.nightly_enabled:
                self.scheduler.add_job(
                    self.run_nightly_backfill,
                    trigger=CronTrigger(
                        hour=self.settings.nightly_hour,
                        minute=self.settings.nightly_minute,
                        timezone=self.settings.time_zone,
                    ),
                    id="nightly-backfill",
                    replace_existing=True,
                    coalesce=True,
                    max_instances=1,
                )
            if not self.scheduler.running:
                self.scheduler.start()
            LOGGER.info(
                "Scheduler configured: poll_enabled=%s interval=%sm nightly=%s %02d:%02d",
                self.settings.poll_enabled,
                self.settings.poll_interval_minutes,
                self.settings.nightly_enabled,
                self.settings.nightly_hour,
                self.settings.nightly_minute,
            )
        elif self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def _effective_roots(self) -> list[Path]:
        selected_libraries = self._normalize_library_names(self.settings.include_library_names)
        self.settings.include_library_names = selected_libraries
        try:
            roots = self.emby_client.resolve_library_scan_roots(selected_libraries)
        except Exception as exc:
            LOGGER.warning("Failed to resolve library roots from Emby, falling back to static roots: %s", exc)
            roots = self.settings.media_roots
        return roots or self.settings.media_roots

    def _discover_seasons(self) -> list[dict]:
        return discover_seasons(
            self._effective_roots(),
            self.settings.excluded_roots,
            self.settings.discovery_min_episodes,
        )

    def _season_signature(self, season) -> dict[str, Any]:
        mtimes = [episode.path.stat().st_mtime_ns for episode in season.episodes]
        sizes = [episode.size_bytes for episode in season.episodes]
        return {
            "episode_count": len(season.episodes),
            "latest_mtime_ns": max(mtimes) if mtimes else 0,
            "total_size": sum(sizes),
        }

    def _season_changed(self, season) -> bool:
        signature = self._season_signature(season)
        previous = self._season_state.get(season.season_key)
        return previous != signature

    def _mark_season_processed(self, season) -> None:
        self._season_state[season.season_key] = self._season_signature(season)
        self._persist_season_state()

    def health(self) -> dict[str, Any]:
        info = self.emby_client.system_info()
        return {
            "ok": True,
            "emby_server_name": info.get("ServerName"),
            "emby_version": info.get("Version"),
            "dry_run": self.settings.dry_run,
        }

    def list_seasons(self) -> list[dict[str, Any]]:
        seasons = self._discover_seasons()
        return [season.to_dict() for season in seasons]

    def get_runtime_settings(self) -> dict[str, Any]:
        self.settings.include_library_names = self._normalize_library_names(self.settings.include_library_names)
        return {
            "dry_run": self.settings.dry_run,
            "write_ed_as_second_intro_pair": self.settings.write_ed_as_second_intro_pair,
            "chapter_detection_enabled": self.settings.chapter_detection_enabled,
            "include_library_names": self.settings.include_library_names,
            "min_similarity": self.settings.min_similarity,
            "min_support_ratio": self.settings.min_support_ratio,
            "op_position_tolerance_seconds": self.settings.op_position_tolerance_seconds,
            "ed_tail_tolerance_seconds": self.settings.ed_tail_tolerance_seconds,
            "poll_enabled": self.settings.poll_enabled,
            "poll_interval_minutes": self.settings.poll_interval_minutes,
            "nightly_enabled": self.settings.nightly_enabled,
            "nightly_hour": self.settings.nightly_hour,
            "nightly_minute": self.settings.nightly_minute,
            "discovery_min_episodes": self.settings.discovery_min_episodes,
            "op_search_max_seconds": self.settings.op_search_max_seconds,
            "ed_search_from_end_seconds": self.settings.ed_search_from_end_seconds,
        }

    def get_library_status(self) -> dict[str, Any]:
        folders = self.emby_client.list_virtual_folders()
        selected = self._normalize_library_names(self.settings.include_library_names)
        self.settings.include_library_names = selected
        return {
            "available": [
                {
                    "name": folder.get("Name"),
                    "collection_type": folder.get("CollectionType"),
                    "locations": folder.get("Locations", []),
                }
                for folder in folders
            ],
            "selected": selected,
            "effective_roots": [str(path) for path in self._effective_roots()],
        }

    def get_scheduler_status(self) -> dict[str, Any]:
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                }
            )
        return {"jobs": jobs}

    def update_runtime_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            for key, value in payload.items():
                if not hasattr(self.settings, key):
                    continue
                if key == "include_library_names" and isinstance(value, str):
                    value = self._normalize_library_names(value)
                setattr(self.settings, key, value)
            self._persist_runtime_overrides()
            self.configure_scheduler()
            return self.get_runtime_settings()

    def run_sample_scan(self) -> dict[str, Any]:
        with self._lock:
            seasons = self._discover_seasons()
            sample = choose_sample_season(seasons)
            if sample is None:
                self._last_report = {"error": "No season candidate found."}
                return self._last_report

            report = scan_season(sample, self.settings, selected_by="auto-sample")
            report.schema_summary = self.sqlite_writer.inspect_schema()
            report.writeback_summary = self.sqlite_writer.prepare_writeback_summary(sample, report)
            payload = report.to_dict()
            self._persist_report(payload, prefix="sample_scan")
            self._persist_batch_snapshot(mode="sample_scan", reports=[payload])
            self._last_report = payload
            return payload

    def run_top_n_scan(self, count: int = 3) -> dict[str, Any]:
        with self._lock:
            seasons = self._discover_seasons()
            selected = seasons[: max(1, count)]
            if not selected:
                self._last_report = {"error": "No season candidate found."}
                return self._last_report

            reports: list[dict[str, Any]] = []
            for season in selected:
                report = scan_season(season, self.settings, selected_by=f"top-{count}")
                report.schema_summary = self.sqlite_writer.inspect_schema()
                report.writeback_summary = self.sqlite_writer.prepare_writeback_summary(season, report)
                reports.append(report.to_dict())

            payload = {
                "mode": "top_n_scan",
                "requested_count": count,
                "actual_count": len(reports),
                "dry_run": self.settings.dry_run,
                "reports": reports,
            }
            self._persist_report(payload, prefix=f"top_{count}_scan")
            self._persist_batch_snapshot(mode="top_n_scan", reports=reports)
            self._last_report = payload
            return payload

    def run_incremental_poll(self) -> dict[str, Any]:
        with self._lock:
            seasons = self._discover_seasons()
            candidates = [season for season in seasons if self._season_changed(season)]
            reports = []
            for season in candidates:
                report = scan_season(season, self.settings, selected_by="incremental-poll")
                report.schema_summary = self.sqlite_writer.inspect_schema()
                report.writeback_summary = self.sqlite_writer.prepare_writeback_summary(season, report)
                self._mark_season_processed(season)
                reports.append(report.to_dict())

            payload = {
                "mode": "incremental_poll",
                "candidate_count": len(candidates),
                "processed_count": len(reports),
                "dry_run": self.settings.dry_run,
                "reports": reports,
            }
            self._persist_report(payload, prefix="incremental_poll")
            self._persist_batch_snapshot(mode="incremental_poll", reports=reports)
            self._last_report = payload
            return payload

    def run_nightly_backfill(self) -> dict[str, Any]:
        with self._lock:
            seasons = self._discover_seasons()
            reports = []
            for season in seasons:
                coverage = self.sqlite_writer.season_marker_coverage(season)
                if coverage["empty_count"] == 0 and coverage["partial_count"] == 0:
                    continue
                report = scan_season(season, self.settings, selected_by="nightly-backfill")
                report.schema_summary = self.sqlite_writer.inspect_schema()
                report.writeback_summary = self.sqlite_writer.prepare_writeback_summary(season, report)
                reports.append(report.to_dict())

            payload = {
                "mode": "nightly_backfill",
                "processed_count": len(reports),
                "dry_run": self.settings.dry_run,
                "reports": reports,
            }
            self._persist_report(payload, prefix="nightly_backfill")
            self._persist_batch_snapshot(mode="nightly_backfill", reports=reports)
            self._last_report = payload
            return payload

    def _persist_report(self, payload: dict[str, Any], prefix: str) -> None:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = self.settings.report_dir / f"{prefix}_{stamp}.json"
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        LOGGER.info("Wrote report to %s", path)

    def list_reports(self) -> list[dict[str, Any]]:
        self.settings.report_dir.mkdir(parents=True, exist_ok=True)
        reports = []
        for path in sorted(self.settings.report_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            reports.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size_bytes": path.stat().st_size,
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                }
            )
        return reports

    def read_report(self, name: str) -> dict[str, Any]:
        path = self.settings.report_dir / name
        return json.loads(path.read_text(encoding="utf-8"))

    def get_batch_status(self) -> dict[str, Any]:
        if not self._batch_status_path.exists():
            return {"status": "idle"}
        try:
            payload = json.loads(self._batch_status_path.read_text(encoding="utf-8"))
            total = int(payload.get("total", 0) or 0)
            completed = int(payload.get("completed", 0) or 0)
            payload["percent"] = round((completed / total * 100.0), 2) if total > 0 else 0.0
            results = payload.get("results") or []
            if results:
                payload["summary"] = {
                    "count": len(results),
                    "op_detected": sum(1 for item in results if (item.get("op") or {}).get("detected")),
                    "ed_detected": sum(1 for item in results if (item.get("ed") or {}).get("detected")),
                    "avg_op_support": round(statistics.mean((item.get("op") or {}).get("support_episodes", 0) for item in results), 2),
                    "avg_ed_support": round(statistics.mean((item.get("ed") or {}).get("support_episodes", 0) for item in results), 2),
                }
            return payload
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    def get_batch_log(self) -> dict[str, Any]:
        if not self._batch_log_path.exists():
            return {"items": []}
        try:
            items = json.loads(self._batch_log_path.read_text(encoding="utf-8"))
            return {"items": items[-100:]}
        except Exception as exc:
            return {"items": [], "error": str(exc)}

    def _load_runtime_overrides(self) -> None:
        if not self._overrides_path.exists():
            return
        try:
            payload = json.loads(self._overrides_path.read_text(encoding="utf-8"))
        except Exception as exc:
            LOGGER.warning("Failed to load runtime overrides: %s", exc)
            return
        for key, value in payload.items():
            if hasattr(self.settings, key):
                if key == "include_library_names":
                    value = self._normalize_library_names(value)
                setattr(self.settings, key, value)

    def _persist_runtime_overrides(self) -> None:
        self.settings.work_dir.mkdir(parents=True, exist_ok=True)
        self._overrides_path.write_text(
            json.dumps(self.get_runtime_settings(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _load_season_state(self) -> None:
        if not self._season_state_path.exists():
            self._season_state = {}
            return
        try:
            self._season_state = json.loads(self._season_state_path.read_text(encoding="utf-8"))
        except Exception as exc:
            LOGGER.warning("Failed to load season state: %s", exc)
            self._season_state = {}

    def _persist_season_state(self) -> None:
        self.settings.work_dir.mkdir(parents=True, exist_ok=True)
        self._season_state_path.write_text(
            json.dumps(self._season_state, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    @property
    def last_report(self) -> dict[str, Any] | None:
        return self._last_report

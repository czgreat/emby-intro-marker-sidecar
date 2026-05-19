from __future__ import annotations

from datetime import datetime
from pathlib import Path
import logging
import shutil
import sqlite3

from .config import Settings
from .emby_client import EmbyClient
from .models import SeasonCandidate, SeasonScanReport


LOGGER = logging.getLogger("intro_marker.sqlite")
MIN_DOTNET_TS = -62135596800


class SQLiteWriteback:
    def __init__(self, settings: Settings, emby_client: EmbyClient) -> None:
        self.settings = settings
        self.emby_client = emby_client

    def inspect_schema(self) -> dict:
        connection = sqlite3.connect(self.settings.emby_db_path)
        try:
            columns = connection.execute(
                f"PRAGMA table_info({self.settings.emby_db_table})"
            ).fetchall()
            return {
                "db_path": str(self.settings.emby_db_path),
                "table": self.settings.emby_db_table,
                "columns": [
                    {
                        "cid": row[0],
                        "name": row[1],
                        "type": row[2],
                        "notnull": row[3],
                        "default": row[4],
                        "pk": row[5],
                    }
                    for row in columns
                ],
            }
        finally:
            connection.close()

    def backup_database(self) -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        destination = self.settings.report_dir / f"library.db.backup_{timestamp}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.settings.emby_db_path, destination)
        LOGGER.info("Backed up Emby DB to %s", destination)
        return destination

    def _build_item_map(self, season: SeasonCandidate) -> dict[str, str]:
        path_index = self.emby_client.build_path_item_index(self.settings.media_roots)
        relevant = {}
        for episode in season.episodes:
            normalized = str(episode.path).replace("\\", "/")
            if normalized in path_index:
                relevant[normalized] = path_index[normalized]
        return relevant

    def season_marker_coverage(self, season: SeasonCandidate) -> dict:
        item_index = self._build_item_map(season)
        connection = sqlite3.connect(self.settings.emby_db_path)
        try:
            rows = []
            complete = 0
            partial = 0
            empty = 0
            for episode in season.episodes:
                normalized = str(episode.path).replace("\\", "/")
                item_id = item_index.get(normalized)
                pair_count = 0
                if item_id is not None:
                    cursor = connection.execute(
                        f"SELECT MarkerType, COUNT(*) FROM {self.settings.emby_db_table} WHERE ItemId = ? AND MarkerType IN (1,2) GROUP BY MarkerType",
                        (int(item_id),),
                    )
                    counts = {int(marker_type): count for marker_type, count in cursor.fetchall()}
                    pair_count = min(counts.get(1, 0), counts.get(2, 0))
                if pair_count >= 2:
                    status = "complete"
                    complete += 1
                elif pair_count == 1:
                    status = "partial"
                    partial += 1
                else:
                    status = "empty"
                    empty += 1
                rows.append(
                    {
                        "episode": Path(episode.path).name,
                        "item_id": int(item_id) if item_id is not None else None,
                        "pair_count": pair_count,
                        "status": status,
                    }
                )
            return {
                "complete_count": complete,
                "partial_count": partial,
                "empty_count": empty,
                "episodes": rows,
            }
        finally:
            connection.close()

    def _match_index(self, report: SeasonScanReport, zone: str) -> dict[str, tuple[int, int]]:
        detection = report.op if zone == "op" else report.ed
        matches: dict[str, tuple[int, int]] = {}
        for entry in detection.matched_episodes:
            path = str(entry.episode_path).replace("\\", "/")
            start_ticks = int(round(entry.marker_start_seconds * 10_000_000))
            end_ticks = int(round(entry.marker_end_seconds * 10_000_000))
            matches[path] = (start_ticks, end_ticks)
        return matches

    def _fetch_rows(self, connection: sqlite3.Connection, item_id: int) -> list[dict]:
        cursor = connection.execute(
            f"""
            SELECT ItemId, ChapterIndex, StartPositionTicks, Name, ImagePath, ImageDateModified, MarkerType
            FROM {self.settings.emby_db_table}
            WHERE ItemId = ?
            ORDER BY ChapterIndex
            """,
            (item_id,),
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _normalized_rows(
        self,
        existing_rows: list[dict],
        item_id: int,
        op_pair: tuple[int, int] | None,
        ed_pair: tuple[int, int] | None,
    ) -> list[dict]:
        rows = [row for row in existing_rows if int(row["MarkerType"]) == 0]
        image_date_modified = MIN_DOTNET_TS
        for row in existing_rows:
            if row.get("ImageDateModified") is not None:
                image_date_modified = row["ImageDateModified"]
                break

        if op_pair:
            rows.append(
                {
                    "ItemId": item_id,
                    "ChapterIndex": -1,
                    "StartPositionTicks": op_pair[0],
                    "Name": "片头",
                    "ImagePath": None,
                    "ImageDateModified": image_date_modified,
                    "MarkerType": 1,
                }
            )
            rows.append(
                {
                    "ItemId": item_id,
                    "ChapterIndex": -1,
                    "StartPositionTicks": op_pair[1],
                    "Name": "片尾",
                    "ImagePath": None,
                    "ImageDateModified": image_date_modified,
                    "MarkerType": 2,
                }
            )

        if ed_pair and self.settings.write_ed_as_second_intro_pair:
            rows.append(
                {
                    "ItemId": item_id,
                    "ChapterIndex": -1,
                    "StartPositionTicks": ed_pair[0],
                    "Name": "片头",
                    "ImagePath": None,
                    "ImageDateModified": image_date_modified,
                    "MarkerType": 1,
                }
            )
            rows.append(
                {
                    "ItemId": item_id,
                    "ChapterIndex": -1,
                    "StartPositionTicks": ed_pair[1],
                    "Name": "片尾",
                    "ImagePath": None,
                    "ImageDateModified": image_date_modified,
                    "MarkerType": 2,
                }
            )

        rows.sort(key=lambda row: (int(row["StartPositionTicks"]), int(row["MarkerType"]) != 0))
        for index, row in enumerate(rows):
            row["ChapterIndex"] = index
        return rows

    def _replace_item_rows(self, connection: sqlite3.Connection, item_id: int, rows: list[dict]) -> None:
        connection.execute(
            f"DELETE FROM {self.settings.emby_db_table} WHERE ItemId = ?",
            (item_id,),
        )
        connection.executemany(
            f"""
            INSERT INTO {self.settings.emby_db_table}
            (ItemId, ChapterIndex, StartPositionTicks, Name, ImagePath, ImageDateModified, MarkerType)
            VALUES
            (:ItemId, :ChapterIndex, :StartPositionTicks, :Name, :ImagePath, :ImageDateModified, :MarkerType)
            """,
            rows,
        )

    def prepare_writeback_summary(self, season: SeasonCandidate, report: SeasonScanReport) -> dict:
        item_index = self._build_item_map(season)
        op_index = self._match_index(report, "op")
        ed_index = self._match_index(report, "ed")
        planned = 0
        missing = []
        for episode in season.episodes:
            normalized = str(episode.path).replace("\\", "/")
            if normalized not in item_index:
                missing.append(normalized)
                continue
            if normalized in op_index or normalized in ed_index:
                planned += 1

        summary = {
            "mode": "op_intro_pair_plus_ed_intro_pair" if self.settings.write_ed_as_second_intro_pair else "single_intro_pair",
            "dry_run": self.settings.dry_run,
            "mapped_episode_count": len(item_index),
            "planned_episode_writes": planned,
            "missing_item_paths": missing[:20],
        }

        if not self.settings.dry_run:
            self.apply_report(season, report, item_index=item_index, op_index=op_index, ed_index=ed_index)
            summary["applied"] = True
        else:
            summary["applied"] = False

        return summary

    def apply_report(
        self,
        season: SeasonCandidate,
        report: SeasonScanReport,
        item_index: dict[str, str] | None = None,
        op_index: dict[str, tuple[int, int]] | None = None,
        ed_index: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        item_index = item_index or self._build_item_map(season)
        op_index = op_index or self._match_index(report, "op")
        ed_index = ed_index or self._match_index(report, "ed")

        if self.settings.enable_db_backup:
            self.backup_database()

        connection = sqlite3.connect(self.settings.emby_db_path)
        try:
            connection.execute(f"PRAGMA busy_timeout = {self.settings.db_busy_timeout_ms}")
            for episode in season.episodes:
                normalized_path = str(episode.path).replace("\\", "/")
                item_id_text = item_index.get(normalized_path)
                if item_id_text is None:
                    continue
                if normalized_path not in op_index and normalized_path not in ed_index:
                    continue
                item_id = int(item_id_text)
                existing_rows = self._fetch_rows(connection, item_id)
                new_rows = self._normalized_rows(
                    existing_rows=existing_rows,
                    item_id=item_id,
                    op_pair=op_index.get(normalized_path),
                    ed_pair=ed_index.get(normalized_path),
                )
                self._replace_item_rows(connection, item_id, new_rows)
            connection.commit()
            LOGGER.info("Applied marker writeback for season %s", season.season_key)
        finally:
            connection.close()

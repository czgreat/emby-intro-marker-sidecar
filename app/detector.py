from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import math
import statistics

from .chapter_probe import load_chapters
from .config import Settings
from .fingerprint import compute_window_fingerprint, fingerprint_similarity, probe_duration_seconds
from .models import SeasonCandidate, SeasonScanReport, WindowFingerprint, ZoneDetection, ZoneEpisodeMatch


LOGGER = logging.getLogger("intro_marker.detector")
ANIME_ROOT_NAMES = {"vcb", "COPY.VCB-Studio", "日番", "国漫"}


@dataclass(slots=True)
class _AnchorMatch:
    episode_path: Path
    window_index: int
    score: float


def _is_probable_anime(season: SeasonCandidate) -> bool:
    return season.root_name in ANIME_ROOT_NAMES


def _similarity_candidates(season: SeasonCandidate, settings: Settings) -> list[float]:
    if not _is_probable_anime(season):
        return [settings.min_similarity]
    candidates = [settings.min_similarity, 0.93, 0.90]
    seen = []
    for value in candidates:
        rounded = round(value, 3)
        if rounded not in seen:
            seen.append(rounded)
    return seen


def _op_position_tolerance(season: SeasonCandidate, settings: Settings) -> float:
    if _is_probable_anime(season):
        return max(settings.op_position_tolerance_seconds, 60.0)
    return settings.op_position_tolerance_seconds


def _ed_tail_tolerance(season: SeasonCandidate, settings: Settings) -> float:
    if _is_probable_anime(season):
        return max(settings.ed_tail_tolerance_seconds, 90.0)
    return settings.ed_tail_tolerance_seconds


def _op_search_limit(season: SeasonCandidate, settings: Settings) -> float:
    return float(settings.op_search_max_seconds)


def _ed_search_limit(season: SeasonCandidate, settings: Settings) -> float:
    return float(settings.ed_search_from_end_seconds)


def _anime_segment_strategies(zone: str) -> list[tuple[int, int]]:
    # Center segment candidates around the common ~90s anime OP/ED length,
    # then cover the shorter/longer edge cases with one smaller and one larger band.
    if zone == "op":
        return [(90, 6), (72, 6), (108, 6)]
    return [(90, 3), (72, 3), (108, 3)]


def _two_stage_coarse_hop(fine_hop_seconds: int) -> int:
    return max(12, fine_hop_seconds * 4)


def _detect_zone_by_chapters(season: SeasonCandidate, zone: str, settings: Settings) -> ZoneDetection | None:
    if not settings.chapter_detection_enabled:
        return None

    rows: list[ZoneEpisodeMatch] = []
    notes: list[str] = ["Detected by embedded chapter boundaries; similarity detection skipped."]

    for episode in season.episodes:
        try:
            chapters = load_chapters(episode.path, settings.cache_dir)
            duration = probe_duration_seconds(episode.path)
        except Exception:
            continue

        candidates = [
            chapter
            for chapter in chapters
            if settings.chapter_duration_min_seconds <= chapter["duration"] <= settings.chapter_duration_max_seconds
        ]
        if not candidates:
            continue

        if zone == "op":
            scoped = [chapter for chapter in candidates if chapter["start"] <= _op_search_limit(season, settings)]
            if not scoped:
                continue
            preferred = [chapter for chapter in scoped if chapter["start"] >= settings.op_search_min_seconds]
            chosen = min(preferred or scoped, key=lambda chapter: chapter["start"])
        else:
            min_start = max(0.0, duration - _ed_search_limit(season, settings))
            scoped = [chapter for chapter in candidates if chapter["start"] >= min_start]
            if not scoped:
                continue
            chosen = min(scoped, key=lambda chapter: chapter["start"])

        rows.append(
            ZoneEpisodeMatch(
                episode_path=episode.path,
                marker_start_seconds=round(chosen["start"], 3),
                marker_end_seconds=round(chosen["end"], 3),
                anchor_similarity=1.0,
            )
        )

    required_support = _required_support(len(season.episodes), settings)
    if len(rows) < required_support:
        return None

    starts = [row.marker_start_seconds for row in rows]
    ends = [row.marker_end_seconds for row in rows]
    season_start = round(statistics.median(starts), 3)
    season_end = round(statistics.median(ends), 3)

    return ZoneDetection(
        zone=zone,
        method="chapter",
        detected=True,
        confidence=1.0,
        support_episodes=len(rows),
        required_support=required_support,
        threshold_similarity=None,
        mean_similarity=1.0,
        min_similarity_observed=1.0,
        max_similarity_observed=1.0,
        season_start_seconds=season_start,
        season_end_seconds=season_end,
        matched_episodes=rows,
        notes=notes,
    )


def _required_support(episode_count: int, settings: Settings) -> int:
    return settings.min_cluster_episodes


def _build_windows(
    season: SeasonCandidate,
    zone: str,
    settings: Settings,
    window_seconds: int | None = None,
    hop_seconds: int | None = None,
) -> tuple[dict[Path, list[WindowFingerprint]], dict[Path, float]]:
    windows_by_episode: dict[Path, list[WindowFingerprint]] = {}
    durations_by_episode: dict[Path, float] = {}
    window_seconds = window_seconds or settings.fingerprint_window_seconds
    hop_seconds = hop_seconds or settings.fingerprint_hop_seconds
    for episode in season.episodes:
        try:
            duration = probe_duration_seconds(episode.path)
        except Exception as exc:
            LOGGER.warning("Skipping duration probe for %s: %s", episode.path, exc)
            continue
        durations_by_episode[episode.path] = duration

        if zone == "op":
            search_start = float(settings.op_search_min_seconds)
            search_end = min(_op_search_limit(season, settings), max(duration * 0.40, float(window_seconds)))
        else:
            search_start = max(0.0, duration - _ed_search_limit(season, settings))
            search_end = duration

        if search_end - search_start < window_seconds:
            continue

        episode_windows: list[WindowFingerprint] = []
        index = 0
        cursor = math.ceil(search_start / hop_seconds) * hop_seconds
        while cursor + window_seconds <= search_end:
            try:
                fingerprint = compute_window_fingerprint(
                    episode.path,
                    start_seconds=cursor,
                    duration_seconds=float(window_seconds),
                    cache_dir=settings.cache_dir,
                    work_dir=settings.work_dir,
                    sample_rate=settings.audio_sample_rate,
                    channels=settings.audio_channels,
                )
            except Exception as exc:
                LOGGER.warning("Window fingerprint failed for %s @ %.1fs: %s", episode.path, cursor, exc)
                cursor += hop_seconds
                index += 1
                continue

            episode_windows.append(
                WindowFingerprint(
                    episode_path=episode.path,
                    zone=zone,
                    start_seconds=cursor,
                    duration_seconds=float(window_seconds),
                    fingerprint=fingerprint,
                    index=index,
                )
            )
            cursor += hop_seconds
            index += 1

        if episode_windows:
            windows_by_episode[episode.path] = episode_windows

    return windows_by_episode, durations_by_episode


def _build_segment_candidates(
    season: SeasonCandidate,
    zone: str,
    settings: Settings,
    segment_seconds: int,
    hop_seconds: int,
    extra_starts: dict[Path, list[tuple[float, float]]] | None = None,
) -> tuple[dict[Path, list[WindowFingerprint]], dict[Path, float]]:
    candidates_by_episode: dict[Path, list[WindowFingerprint]] = {}
    durations_by_episode: dict[Path, float] = {}
    for episode in season.episodes:
        try:
            duration = probe_duration_seconds(episode.path)
        except Exception as exc:
            LOGGER.warning("Skipping duration probe for %s: %s", episode.path, exc)
            continue
        durations_by_episode[episode.path] = duration

        if zone == "op":
            search_start = float(settings.op_search_min_seconds)
            search_end = min(_op_search_limit(season, settings), max(duration * 0.40, float(segment_seconds)))
        else:
            search_start = max(0.0, duration - _ed_search_limit(season, settings))
            search_end = duration

        if search_end - search_start < segment_seconds:
            continue

        episode_candidates: list[WindowFingerprint] = []
        seen_keys: set[tuple[int, int]] = set()
        index = 0
        cursor = search_start
        while cursor + segment_seconds <= search_end:
            key = (int(round(cursor * 1000)), int(segment_seconds * 1000))
            seen_keys.add(key)
            try:
                fingerprint = compute_window_fingerprint(
                    episode.path,
                    start_seconds=cursor,
                    duration_seconds=float(segment_seconds),
                    cache_dir=settings.cache_dir,
                    work_dir=settings.work_dir,
                    sample_rate=settings.audio_sample_rate,
                    channels=settings.audio_channels,
                )
            except Exception as exc:
                LOGGER.warning("Segment candidate fingerprint failed for %s @ %.1fs: %s", episode.path, cursor, exc)
                cursor += hop_seconds
                index += 1
                continue

            episode_candidates.append(
                WindowFingerprint(
                    episode_path=episode.path,
                    zone=zone,
                    start_seconds=cursor,
                    duration_seconds=float(segment_seconds),
                    fingerprint=fingerprint,
                    index=index,
                )
            )
            cursor += hop_seconds
            index += 1

        if extra_starts and episode.path in extra_starts:
            for start, duration_hint in extra_starts[episode.path]:
                duration_seconds = max(float(segment_seconds), float(duration_hint))
                key = (int(round(start * 1000)), int(round(duration_seconds * 1000)))
                if key in seen_keys:
                    continue
                if start < search_start or start + duration_seconds > search_end:
                    continue
                try:
                    fingerprint = compute_window_fingerprint(
                        episode.path,
                        start_seconds=start,
                        duration_seconds=duration_seconds,
                        cache_dir=settings.cache_dir,
                        work_dir=settings.work_dir,
                        sample_rate=settings.audio_sample_rate,
                        channels=settings.audio_channels,
                    )
                except Exception as exc:
                    LOGGER.warning("Seed candidate fingerprint failed for %s @ %.1fs: %s", episode.path, start, exc)
                    continue
                episode_candidates.append(
                    WindowFingerprint(
                        episode_path=episode.path,
                        zone=zone,
                        start_seconds=start,
                        duration_seconds=duration_seconds,
                        fingerprint=fingerprint,
                        index=index,
                    )
                )
                index += 1

        if episode_candidates:
            candidates_by_episode[episode.path] = episode_candidates

    return candidates_by_episode, durations_by_episode


def _chapter_seed_starts(
    season: SeasonCandidate,
    zone: str,
    settings: Settings,
) -> dict[Path, list[tuple[float, float]]]:
    if not settings.chapter_detection_enabled:
        return {}
    extra: dict[Path, list[tuple[float, float]]] = {}
    for episode in season.episodes:
        try:
            chapters = load_chapters(episode.path, settings.cache_dir)
            duration = probe_duration_seconds(episode.path)
        except Exception:
            continue
        candidates = [
            chapter
            for chapter in chapters
            if settings.chapter_duration_min_seconds <= chapter["duration"] <= settings.chapter_duration_max_seconds
        ]
        if zone == "op":
            scoped = [chapter for chapter in candidates if chapter["start"] <= _op_search_limit(season, settings)]
        else:
            scoped = [chapter for chapter in candidates if chapter["start"] >= max(0.0, duration - _ed_search_limit(season, settings))]
        if not scoped:
            continue
        extra[episode.path] = [(chapter["start"], chapter["duration"]) for chapter in scoped]
    return extra


def _best_cluster(
    windows_by_episode: dict[Path, list[WindowFingerprint]],
    similarity_threshold: float,
    required_support: int,
) -> tuple[WindowFingerprint, dict[Path, _AnchorMatch]] | None:
    episode_paths = list(windows_by_episode.keys())
    if len(episode_paths) < required_support:
        return None

    anchor_paths = episode_paths[: min(6, len(episode_paths))]
    best_payload: tuple[tuple[int, float, float], WindowFingerprint, dict[Path, _AnchorMatch]] | None = None

    for anchor_path in anchor_paths:
        for anchor_window in windows_by_episode[anchor_path]:
            matches: dict[Path, _AnchorMatch] = {
                anchor_path: _AnchorMatch(episode_path=anchor_path, window_index=anchor_window.index, score=1.0)
            }
            scores = [1.0]
            starts = [anchor_window.start_seconds]

            for episode_path, candidate_windows in windows_by_episode.items():
                if episode_path == anchor_path:
                    continue
                best_score = 0.0
                best_index = -1
                for candidate in candidate_windows:
                    score = fingerprint_similarity(anchor_window.fingerprint, candidate.fingerprint)
                    if score > best_score:
                        best_score = score
                        best_index = candidate.index
                if best_index >= 0 and best_score >= similarity_threshold:
                    matched_window = candidate_windows[best_index]
                    matches[episode_path] = _AnchorMatch(
                        episode_path=episode_path,
                        window_index=best_index,
                        score=best_score,
                    )
                    scores.append(best_score)
                    starts.append(matched_window.start_seconds)

            if len(matches) < required_support:
                continue

            start_spread = statistics.pstdev(starts) if len(starts) > 1 else 0.0
            rank = (len(matches), -round(start_spread, 3), round(statistics.mean(scores), 4))
            if best_payload is None or rank > best_payload[0]:
                best_payload = (rank, anchor_window, matches)

    if best_payload is None:
        return None

    return best_payload[1], best_payload[2]


def _cluster_metric_center(
    zone: str,
    matches: dict[Path, _AnchorMatch],
    windows_by_episode: dict[Path, list[WindowFingerprint]],
    durations_by_episode: dict[Path, float],
) -> float:
    metrics: list[float] = []
    for episode_path, match in matches.items():
        start_seconds = windows_by_episode[episode_path][match.window_index].start_seconds
        if zone == "op":
            metrics.append(start_seconds)
        else:
            metrics.append(durations_by_episode[episode_path] - start_seconds)
    return float(statistics.median(metrics)) if metrics else 0.0


def _build_refined_windows(
    season: SeasonCandidate,
    zone: str,
    settings: Settings,
    durations_by_episode: dict[Path, float],
    center_metric: float,
    window_seconds: int,
    hop_seconds: int,
    span_seconds: int,
) -> dict[Path, list[WindowFingerprint]]:
    windows_by_episode: dict[Path, list[WindowFingerprint]] = {}
    for episode in season.episodes:
        duration = durations_by_episode.get(episode.path)
        if duration is None:
            continue

        if zone == "op":
            default_start = float(settings.op_search_min_seconds)
            default_end = min(_op_search_limit(season, settings), max(duration * 0.40, float(window_seconds)))
            center_start = center_metric
        else:
            default_start = max(0.0, duration - _ed_search_limit(season, settings))
            default_end = duration
            center_start = max(default_start, duration - center_metric)

        search_start = max(default_start, center_start - span_seconds)
        search_end = min(default_end, center_start + span_seconds + window_seconds)
        if search_end - search_start < window_seconds:
            continue

        episode_windows: list[WindowFingerprint] = []
        index = 0
        cursor = math.ceil(search_start / hop_seconds) * hop_seconds
        while cursor + window_seconds <= search_end:
            try:
                fingerprint = compute_window_fingerprint(
                    episode.path,
                    start_seconds=cursor,
                    duration_seconds=float(window_seconds),
                    cache_dir=settings.cache_dir,
                    work_dir=settings.work_dir,
                    sample_rate=settings.audio_sample_rate,
                    channels=settings.audio_channels,
                )
            except Exception as exc:
                LOGGER.warning("Refined window fingerprint failed for %s @ %.1fs: %s", episode.path, cursor, exc)
                cursor += hop_seconds
                index += 1
                continue

            episode_windows.append(
                WindowFingerprint(
                    episode_path=episode.path,
                    zone=zone,
                    start_seconds=cursor,
                    duration_seconds=float(window_seconds),
                    fingerprint=fingerprint,
                    index=index,
                )
            )
            cursor += hop_seconds
            index += 1

        if episode_windows:
            windows_by_episode[episode.path] = episode_windows

    return windows_by_episode


def _build_refined_segment_candidates(
    season: SeasonCandidate,
    zone: str,
    settings: Settings,
    durations_by_episode: dict[Path, float],
    center_metric: float,
    segment_seconds: int,
    hop_seconds: int,
    span_seconds: int,
    extra_starts: dict[Path, list[tuple[float, float]]] | None = None,
) -> dict[Path, list[WindowFingerprint]]:
    candidates_by_episode: dict[Path, list[WindowFingerprint]] = {}
    for episode in season.episodes:
        duration = durations_by_episode.get(episode.path)
        if duration is None:
            continue

        if zone == "op":
            default_start = float(settings.op_search_min_seconds)
            default_end = min(_op_search_limit(season, settings), max(duration * 0.40, float(segment_seconds)))
            center_start = center_metric
        else:
            default_start = max(0.0, duration - _ed_search_limit(season, settings))
            default_end = duration
            center_start = max(default_start, duration - center_metric)

        search_start = max(default_start, center_start - span_seconds)
        search_end = min(default_end, center_start + span_seconds + segment_seconds)
        if search_end - search_start < segment_seconds:
            continue

        episode_candidates: list[WindowFingerprint] = []
        seen_keys: set[tuple[int, int]] = set()
        index = 0
        cursor = math.ceil(search_start / hop_seconds) * hop_seconds
        while cursor + segment_seconds <= search_end:
            key = (int(round(cursor * 1000)), int(segment_seconds * 1000))
            seen_keys.add(key)
            try:
                fingerprint = compute_window_fingerprint(
                    episode.path,
                    start_seconds=cursor,
                    duration_seconds=float(segment_seconds),
                    cache_dir=settings.cache_dir,
                    work_dir=settings.work_dir,
                    sample_rate=settings.audio_sample_rate,
                    channels=settings.audio_channels,
                )
            except Exception as exc:
                LOGGER.warning("Refined segment fingerprint failed for %s @ %.1fs: %s", episode.path, cursor, exc)
                cursor += hop_seconds
                index += 1
                continue

            episode_candidates.append(
                WindowFingerprint(
                    episode_path=episode.path,
                    zone=zone,
                    start_seconds=cursor,
                    duration_seconds=float(segment_seconds),
                    fingerprint=fingerprint,
                    index=index,
                )
            )
            cursor += hop_seconds
            index += 1

        if extra_starts and episode.path in extra_starts:
            for start, duration_hint in extra_starts[episode.path]:
                duration_seconds = max(float(segment_seconds), float(duration_hint))
                key = (int(round(start * 1000)), int(round(duration_seconds * 1000)))
                if key in seen_keys:
                    continue
                if start < search_start or start + duration_seconds > search_end:
                    continue
                try:
                    fingerprint = compute_window_fingerprint(
                        episode.path,
                        start_seconds=start,
                        duration_seconds=duration_seconds,
                        cache_dir=settings.cache_dir,
                        work_dir=settings.work_dir,
                        sample_rate=settings.audio_sample_rate,
                        channels=settings.audio_channels,
                    )
                except Exception as exc:
                    LOGGER.warning("Refined seed fingerprint failed for %s @ %.1fs: %s", episode.path, start, exc)
                    continue
                episode_candidates.append(
                    WindowFingerprint(
                        episode_path=episode.path,
                        zone=zone,
                        start_seconds=start,
                        duration_seconds=duration_seconds,
                        fingerprint=fingerprint,
                        index=index,
                    )
                )
                index += 1

        if episode_candidates:
            candidates_by_episode[episode.path] = episode_candidates

    return candidates_by_episode


def _expand_segment(
    anchor_window: WindowFingerprint,
    matches: dict[Path, _AnchorMatch],
    windows_by_episode: dict[Path, list[WindowFingerprint]],
    settings: Settings,
    similarity_threshold: float,
    required_support: int,
) -> tuple[int, int]:
    anchor_windows = windows_by_episode[anchor_window.episode_path]
    backward_steps = 0
    forward_steps = 0

    while True:
        next_step = backward_steps + 1
        anchor_index = anchor_window.index - next_step
        if anchor_index < 0:
            break
        support = 1
        for episode_path, match in matches.items():
            if episode_path == anchor_window.episode_path:
                continue
            candidate_index = match.window_index - next_step
            if candidate_index < 0:
                continue
            score = fingerprint_similarity(
                anchor_windows[anchor_index].fingerprint,
                windows_by_episode[episode_path][candidate_index].fingerprint,
            )
            if score >= similarity_threshold:
                support += 1
        if support >= required_support:
            backward_steps = next_step
            continue
        break

    while True:
        next_step = forward_steps + 1
        anchor_index = anchor_window.index + next_step
        if anchor_index >= len(anchor_windows):
            break
        support = 1
        for episode_path, match in matches.items():
            if episode_path == anchor_window.episode_path:
                continue
            candidate_index = match.window_index + next_step
            if candidate_index >= len(windows_by_episode[episode_path]):
                continue
            score = fingerprint_similarity(
                anchor_windows[anchor_index].fingerprint,
                windows_by_episode[episode_path][candidate_index].fingerprint,
            )
            if score >= similarity_threshold:
                support += 1
        if support >= required_support:
            forward_steps = next_step
            continue
        break

    return backward_steps, forward_steps


def _filter_matches_by_position(
    season: SeasonCandidate,
    zone: str,
    matches: dict[Path, _AnchorMatch],
    windows_by_episode: dict[Path, list[WindowFingerprint]],
    durations_by_episode: dict[Path, float],
    backward_steps: int,
    forward_steps: int,
    window_seconds: int,
    hop_seconds: int,
    settings: Settings,
    required_support: int,
) -> tuple[dict[Path, _AnchorMatch], dict[Path, tuple[float, float]], list[str]]:
    segments: dict[Path, tuple[float, float]] = {}
    notes: list[str] = []

    for episode_path, match in matches.items():
        episode_windows = windows_by_episode[episode_path]
        window = episode_windows[match.window_index]
        start = max(0.0, window.start_seconds - (backward_steps * hop_seconds))
        end = window.start_seconds + (forward_steps * hop_seconds) + window_seconds
        duration = durations_by_episode[episode_path]
        end = min(duration, end)
        segments[episode_path] = (start, end)

    if not segments:
        return matches, segments, notes

    if zone == "op":
        metrics = {path: value[0] for path, value in segments.items()}
        tolerance = _op_position_tolerance(season, settings)
    else:
        metrics = {path: durations_by_episode[path] - value[0] for path, value in segments.items()}
        tolerance = _ed_tail_tolerance(season, settings)

    best_center = None
    best_filtered: dict[Path, _AnchorMatch] = {}
    best_score = (-1, -1.0)
    for center in metrics.values():
        candidate_filtered = {
            path: matches[path]
            for path, metric in metrics.items()
            if abs(metric - center) <= tolerance
        }
        candidate_scores = [matches[path].score for path in candidate_filtered]
        rank = (len(candidate_filtered), statistics.mean(candidate_scores) if candidate_scores else 0.0)
        if rank > best_score:
            best_score = rank
            best_center = center
            best_filtered = candidate_filtered

    filtered = best_filtered

    if len(filtered) >= required_support:
        removed = len(matches) - len(filtered)
        if removed > 0:
            notes.append(f"Filtered {removed} positional outlier episode(s) around center {round(best_center or 0.0, 3)}.")
        filtered_segments = {path: segments[path] for path in filtered}
        return filtered, filtered_segments, notes

    notes.append("Positional outlier filter skipped because support would fall below threshold.")
    return matches, segments, notes


def _detect_zone_with_segment_candidates(
    season: SeasonCandidate,
    zone: str,
    settings: Settings,
    segment_seconds: int,
    hop_seconds: int,
    use_chapter_seeds: bool = False,
) -> ZoneDetection | None:
    extra_starts = _chapter_seed_starts(season, zone, settings) if use_chapter_seeds else None
    # Futoku no Guild S1 shows that the 72s ED fallback can miss viable clusters
    # when the coarse pass is quantized to 12s. Keep the expensive 3s grid only
    # for this narrow anime-ED fallback instead of widening every strategy.
    if _is_probable_anime(season) and zone == "ed" and segment_seconds == 72 and hop_seconds == 3 and not use_chapter_seeds:
        coarse_hop_seconds = hop_seconds
    else:
        coarse_hop_seconds = _two_stage_coarse_hop(hop_seconds)
    candidates_by_episode, durations_by_episode = _build_segment_candidates(
        season,
        zone=zone,
        settings=settings,
        segment_seconds=segment_seconds,
        hop_seconds=coarse_hop_seconds,
        extra_starts=extra_starts,
    )
    required_support = _required_support(len(season.episodes), settings)
    if len(candidates_by_episode) < required_support:
        return None

    notes: list[str] = []
    selected_similarity = None
    anchor_candidate = None
    matches = None
    for similarity_threshold in _similarity_candidates(season, settings):
        cluster = _best_cluster(candidates_by_episode, similarity_threshold, required_support=required_support)
        if cluster is not None:
            selected_similarity = similarity_threshold
            anchor_candidate, matches = cluster
            break

    if selected_similarity is None or anchor_candidate is None or matches is None:
        return None

    if coarse_hop_seconds > hop_seconds:
        center_metric = _cluster_metric_center(zone, matches, candidates_by_episode, durations_by_episode)
        refined_candidates_by_episode = _build_refined_segment_candidates(
            season,
            zone=zone,
            settings=settings,
            durations_by_episode=durations_by_episode,
            center_metric=center_metric,
            segment_seconds=segment_seconds,
            hop_seconds=hop_seconds,
            span_seconds=coarse_hop_seconds,
            extra_starts=extra_starts,
        )
        if len(refined_candidates_by_episode) >= required_support:
            refined_selected_similarity = None
            refined_anchor = None
            refined_matches = None
            for similarity_threshold in _similarity_candidates(season, settings):
                cluster = _best_cluster(refined_candidates_by_episode, similarity_threshold, required_support=required_support)
                if cluster is not None:
                    refined_selected_similarity = similarity_threshold
                    refined_anchor, refined_matches = cluster
                    break
            if refined_selected_similarity is not None and refined_anchor is not None and refined_matches is not None:
                selected_similarity = refined_selected_similarity
                anchor_candidate = refined_anchor
                matches = refined_matches
                candidates_by_episode = refined_candidates_by_episode
                notes.append(
                    f"Two-stage segment search refined around coarse center (coarse_hop={coarse_hop_seconds}s, fine_hop={hop_seconds}s)."
                )

    segments = {}
    for episode_path, match in matches.items():
        candidate = candidates_by_episode[episode_path][match.window_index]
        start = candidate.start_seconds
        end = min(durations_by_episode[episode_path], start + candidate.duration_seconds)
        segments[episode_path] = (start, end)

    matched_rows: list[ZoneEpisodeMatch] = []
    starts: list[float] = []
    ends: list[float] = []
    scores: list[float] = []
    for episode_path, match in matches.items():
        start, end = segments[episode_path]
        starts.append(start)
        ends.append(end)
        scores.append(match.score)
        matched_rows.append(
            ZoneEpisodeMatch(
                episode_path=episode_path,
                marker_start_seconds=round(start, 3),
                marker_end_seconds=round(end, 3),
                anchor_similarity=round(match.score, 4),
                mean_similarity=round(match.score, 4),
            )
        )

    notes.append(f"Resolved with segment candidate strategy ({segment_seconds}s/{hop_seconds}s).")
    if use_chapter_seeds:
        notes.append("Chapter boundary seeds were included as candidate starts.")
    return ZoneDetection(
        zone=zone,
        method="chromaprint_segment_seeded" if use_chapter_seeds else "chromaprint_segment",
        detected=True,
        confidence=round(statistics.mean(scores), 4),
        support_episodes=len(matches),
        required_support=required_support,
        threshold_similarity=selected_similarity,
        mean_similarity=round(statistics.mean(scores), 4),
        min_similarity_observed=round(min(scores), 4),
        max_similarity_observed=round(max(scores), 4),
        season_start_seconds=round(statistics.median(starts), 3),
        season_end_seconds=round(statistics.median(ends), 3),
        matched_episodes=matched_rows,
        notes=notes,
    )


def _detect_best_segment_strategy(
    season: SeasonCandidate,
    zone: str,
    settings: Settings,
    strategies: list[tuple[int, int]],
) -> ZoneDetection | None:
    primary = strategies[0] if strategies else None
    for index, (segment_seconds, hop_seconds) in enumerate(strategies):
        result = _detect_zone_with_segment_candidates(
            season,
            zone=zone,
            settings=settings,
            segment_seconds=segment_seconds,
            hop_seconds=hop_seconds,
        )
        if result is None:
            continue
        if index > 0 and primary is not None:
            result.notes.insert(
                0,
                f"Fallback strategy used after primary segment candidate strategy ({primary[0]}s/{primary[1]}s) did not detect a cluster.",
            )
        return result
    return None


def _detect_zone(season: SeasonCandidate, zone: str, settings: Settings) -> ZoneDetection:
    chapter_result = _detect_zone_by_chapters(season, zone=zone, settings=settings)
    if chapter_result is not None:
        return chapter_result

    if _is_probable_anime(season) and zone == "ed":
        segment_result = _detect_best_segment_strategy(
            season,
            zone=zone,
            settings=settings,
            strategies=_anime_segment_strategies(zone),
        )
        if segment_result is not None:
            return segment_result
        if settings.chapter_detection_enabled:
            seeded_result = _detect_zone_with_segment_candidates(
                season,
                zone=zone,
                settings=settings,
                segment_seconds=90,
                hop_seconds=3,
                use_chapter_seeds=True,
            )
            if seeded_result is not None:
                return seeded_result

    required_support = _required_support(len(season.episodes), settings)

    attempts: list[tuple[int, int, str, bool]] = [(settings.fingerprint_window_seconds, settings.fingerprint_hop_seconds, "base", True)]
    if _is_probable_anime(season) and zone == "ed":
        attempts.append((48, 12, "ed_wide", True))

    last_failure_support = 0
    last_failure_notes: list[str] = []
    selected_similarity = None
    selected_mode = "base"
    pre_notes: list[str] = []
    anchor_window = None
    matches = None
    windows_by_episode = {}
    durations_by_episode = {}

    for window_seconds, hop_seconds, mode, allow_expand in attempts:
        coarse_hop_seconds = _two_stage_coarse_hop(hop_seconds)
        windows_by_episode, durations_by_episode = _build_windows(
            season,
            zone=zone,
            settings=settings,
            window_seconds=window_seconds,
            hop_seconds=coarse_hop_seconds,
        )
        if len(windows_by_episode) < required_support:
            last_failure_support = len(windows_by_episode)
            last_failure_notes = [f"Not enough episodes yielded usable fingerprints with window={window_seconds}s coarse_hop={coarse_hop_seconds}s. Required support is {required_support}."]
            continue

        for similarity_threshold in _similarity_candidates(season, settings):
            cluster = _best_cluster(windows_by_episode, similarity_threshold, required_support=required_support)
            if cluster is not None:
                selected_similarity = similarity_threshold
                selected_mode = mode
                anchor_window, matches = cluster
                break
        if selected_similarity is not None:
            if coarse_hop_seconds > hop_seconds:
                center_metric = _cluster_metric_center(zone, matches, windows_by_episode, durations_by_episode)
                refined_windows_by_episode = _build_refined_windows(
                    season,
                    zone=zone,
                    settings=settings,
                    durations_by_episode=durations_by_episode,
                    center_metric=center_metric,
                    window_seconds=window_seconds,
                    hop_seconds=hop_seconds,
                    span_seconds=coarse_hop_seconds,
                )
                if len(refined_windows_by_episode) >= required_support:
                    refined_selected_similarity = None
                    refined_anchor = None
                    refined_matches = None
                    for similarity_threshold in _similarity_candidates(season, settings):
                        cluster = _best_cluster(refined_windows_by_episode, similarity_threshold, required_support=required_support)
                        if cluster is not None:
                            refined_selected_similarity = similarity_threshold
                            refined_anchor, refined_matches = cluster
                            break
                    if refined_selected_similarity is not None and refined_anchor is not None and refined_matches is not None:
                        selected_similarity = refined_selected_similarity
                        anchor_window = refined_anchor
                        matches = refined_matches
                        windows_by_episode = refined_windows_by_episode
                        pre_notes.append(
                            f"Two-stage window search refined around coarse center (coarse_hop={coarse_hop_seconds}s, fine_hop={hop_seconds}s)."
                        )
            break
        last_failure_notes = [f"No repeated fingerprint cluster cleared the similarity threshold with window={window_seconds}s coarse_hop={coarse_hop_seconds}s and required support {required_support}."]

    if matches is None or anchor_window is None or selected_similarity is None:
        return ZoneDetection(
            zone=zone,
            method="chromaprint",
            detected=False,
            confidence=0.0,
            support_episodes=last_failure_support if last_failure_support else 0,
            required_support=required_support,
            threshold_similarity=min(_similarity_candidates(season, settings)),
            notes=last_failure_notes or [f"No repeated fingerprint cluster cleared the similarity threshold with required support {required_support}."],
        )

    if allow_expand:
        backward_steps, forward_steps = _expand_segment(
            anchor_window,
            matches,
            windows_by_episode,
            settings,
            similarity_threshold=selected_similarity,
            required_support=required_support,
        )
    else:
        backward_steps, forward_steps = 0, 0
    matches, segments, notes = _filter_matches_by_position(
        season=season,
        zone=zone,
        matches=matches,
        windows_by_episode=windows_by_episode,
        durations_by_episode=durations_by_episode,
        backward_steps=backward_steps,
        forward_steps=forward_steps,
        window_seconds=window_seconds,
        hop_seconds=hop_seconds,
        settings=settings,
        required_support=required_support,
    )
    notes = pre_notes + notes
    if selected_mode != "base":
        notes.append(f"Resolved with {selected_mode} window strategy.")

    matched_rows: list[ZoneEpisodeMatch] = []
    starts: list[float] = []
    ends: list[float] = []
    scores: list[float] = []

    for episode_path, match in matches.items():
        start, end = segments[episode_path]
        starts.append(start)
        ends.append(end)
        scores.append(match.score)
        matched_rows.append(
            ZoneEpisodeMatch(
                episode_path=episode_path,
                marker_start_seconds=round(start, 3),
                marker_end_seconds=round(end, 3),
                anchor_similarity=round(match.score, 4),
                mean_similarity=round(match.score, 4),
            )
        )

    season_start = float(round(statistics.median(starts), 3))
    season_end = float(round(statistics.median(ends), 3))
    duration = season_end - season_start

    if duration < settings.min_marker_seconds:
        season_end = round(season_start + settings.min_marker_seconds, 3)
        notes.append("Expanded detection to minimum marker duration.")
    elif duration > settings.max_marker_seconds:
        season_end = round(season_start + settings.max_marker_seconds, 3)
        notes.append("Clamped detection to maximum marker duration.")

    return ZoneDetection(
        zone=zone,
        method="chromaprint",
        detected=True,
        confidence=round(statistics.mean(scores), 4),
        support_episodes=len(matches),
        required_support=required_support,
        threshold_similarity=selected_similarity,
        mean_similarity=round(statistics.mean(scores), 4),
        min_similarity_observed=round(min(scores), 4),
        max_similarity_observed=round(max(scores), 4),
        season_start_seconds=season_start,
        season_end_seconds=season_end,
        matched_episodes=matched_rows,
        notes=notes,
    )


def scan_season(season: SeasonCandidate, settings: Settings, selected_by: str) -> SeasonScanReport:
    LOGGER.info("Scanning season %s", season.season_key)
    op = _detect_zone(season, zone="op", settings=settings)
    ed = _detect_zone(season, zone="ed", settings=settings)
    return SeasonScanReport(
        season_key=season.season_key,
        season_path=str(season.season_path),
        episode_count=len(season.episodes),
        op=op,
        ed=ed,
        selected_by=selected_by,
        dry_run=settings.dry_run,
    )

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import Settings
from app.emby_client import EmbyClient
from app.fingerprint import fingerprint_similarity
from app.media_discovery import discover_seasons
from app.detector import _build_segment_candidates, _required_support, _similarity_candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--series", required=True)
    parser.add_argument("--season", required=True)
    parser.add_argument("--zone", choices=("op", "ed"), required=True)
    parser.add_argument("--segment-seconds", type=int, required=True)
    parser.add_argument("--hops", default="24,12,6,3")
    parser.add_argument("--library", default="动漫")
    parser.add_argument("--top-anchors", type=int, default=5)
    parser.add_argument("--output", default="")
    return parser.parse_args()


def load_season(settings: Settings, library_name: str, series_name: str, season_name: str):
    client = EmbyClient(settings.emby_base_url, settings.emby_api_key, settings.emby_user_id)
    roots = client.resolve_library_scan_roots([library_name])
    lookup = {
        (season.series_name, season.season_name): season
        for season in discover_seasons(roots, settings.excluded_roots, settings.discovery_min_episodes)
    }
    key = (series_name, season_name)
    if key not in lookup:
        raise RuntimeError(f"Season not found: {series_name} / {season_name}")
    return lookup[key]


def evaluate_hop(season, settings: Settings, zone: str, segment_seconds: int, hop_seconds: int) -> dict:
    candidates_by_episode, _ = _build_segment_candidates(
        season,
        zone=zone,
        settings=settings,
        segment_seconds=segment_seconds,
        hop_seconds=hop_seconds,
    )
    episode_paths = list(candidates_by_episode.keys())
    top_payloads: list[tuple[tuple[int, int, int, float], dict]] = []

    for anchor_path in episode_paths:
        for anchor_window in candidates_by_episode[anchor_path]:
            matches = []
            for episode_path, candidate_windows in candidates_by_episode.items():
                best_score = 0.0
                best_start = None
                for candidate in candidate_windows:
                    score = fingerprint_similarity(anchor_window.fingerprint, candidate.fingerprint)
                    if score > best_score:
                        best_score = score
                        best_start = candidate.start_seconds
                matches.append(
                    {
                        "episode_path": str(episode_path),
                        "best_start": best_start,
                        "best_score": round(best_score, 4),
                    }
                )

            support_095 = sum(1 for item in matches if item["best_score"] >= 0.95)
            support_093 = sum(1 for item in matches if item["best_score"] >= 0.93)
            support_090 = sum(1 for item in matches if item["best_score"] >= 0.90)
            mean_score = round(statistics.mean(item["best_score"] for item in matches), 4)
            rank = (support_095, support_093, support_090, mean_score)
            payload = {
                "anchor_path": str(anchor_path),
                "anchor_start": anchor_window.start_seconds,
                "support_095": support_095,
                "support_093": support_093,
                "support_090": support_090,
                "mean_score": mean_score,
                "matches": matches,
            }
            top_payloads.append((rank, payload))

    top_payloads.sort(key=lambda item: item[0], reverse=True)
    result = {
        "hop_seconds": hop_seconds,
        "episodes_with_candidates": len(candidates_by_episode),
        "avg_candidates_per_episode": round(
            sum(len(value) for value in candidates_by_episode.values()) / max(1, len(candidates_by_episode)),
            2,
        ),
        "similarity_candidates": _similarity_candidates(season, settings),
        "top_anchors": [payload for _, payload in top_payloads],
    }
    return result


def main() -> int:
    args = parse_args()
    settings = Settings.load()
    season = load_season(settings, args.library, args.series, args.season)
    required_support = _required_support(len(season.episodes), settings)
    hops = [int(part.strip()) for part in args.hops.split(",") if part.strip()]

    payload = {
        "series": args.series,
        "season": args.season,
        "library": args.library,
        "zone": args.zone,
        "segment_seconds": args.segment_seconds,
        "required_support": required_support,
        "hop_results": [],
    }

    for hop in hops:
        item = evaluate_hop(season, settings, args.zone, args.segment_seconds, hop)
        item["top_anchors"] = item["top_anchors"][: args.top_anchors]
        payload["hop_results"].append(item)

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

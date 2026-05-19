from __future__ import annotations

from .models import SeasonCandidate


def choose_sample_season(seasons: list[SeasonCandidate]) -> SeasonCandidate | None:
    if not seasons:
        return None
    ranked = sorted(
        seasons,
        key=lambda season: (
            season.root_name != "vcb",
            any(episode.extension == ".strm" for episode in season.episodes),
            abs(len(season.episodes) - 12),
            season.series_name.lower(),
            season.season_name.lower(),
        ),
    )
    return ranked[0]

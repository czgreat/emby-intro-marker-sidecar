# Roadmap

This public release is a cleaned, source-focused baseline. It is intended to be usable by developers, but each deployment still needs local configuration.

## Complete enough to use

- FastAPI service can run locally or in Docker
- Dry-run workflow is available before database writes
- Configuration is example-driven via .env and config YAML
- Health endpoint is available

## Needs local completion

- A reachable Emby server
- An Emby API key
- Read-only media mounts
- A backed-up Emby SQLite database before enabling writeback
- ffmpeg available in the runtime image or host

## Suggested improvements

- Adapt volume mounts for a specific NAS layout
- Add support for another marker backend
- Tune fingerprint thresholds for a media library
- Add a dry-run report UI

## Documentation still worth adding

- Real screenshots or short demo videos.
- A known-good production deployment example for a generic Linux host.
- Troubleshooting notes collected from real user deployments.


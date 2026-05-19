# Roadmap

**Language:** English | [中文](ROADMAP.zh-CN.md)

This roadmap describes the public repository state for `emby-intro-marker-sidecar`. It separates what is ready to use from what each user should complete in their own environment.

## Complete Enough To Use

- Dry-run detection
- Report review workflow
- Optional explicit writeback path

## Needs Local Completion

- Tune detector thresholds for your media library
- Verify SQLite table/template compatibility for your Emby version
- Add integration tests against a disposable fixture database

## Suggested Improvements

- Add fixture-based detector tests
- Improve report explanations and confidence scores
- Add safe migration checks before writeback
- Document deployment examples for different Emby layouts

## Documentation Still Worth Adding

- Screenshots or short screen recordings using non-private demo data.
- A fuller API example page for common requests and responses.
- Backup and restore notes for any persistent data path.
- A troubleshooting page based on real public issues once users start deploying it.

## Maintenance Notes

- Keep public examples generic.
- Keep English and Chinese instructions aligned.
- Prefer small issues and pull requests so AI-assisted contributors can work safely.
- Re-run sensitive-data scans before publishing new releases.

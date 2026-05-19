# Emby Intro Marker Sidecar

[![CI](https://github.com/czgreat/emby-intro-marker-sidecar/actions/workflows/ci.yml/badge.svg)](https://github.com/czgreat/emby-intro-marker-sidecar/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Language:** English | [中文](README.zh-CN.md)

Self-hosted sidecar service for detecting repeated intro/outro segments and preparing Emby chapter markers.

## Overview

Emby Intro Marker Sidecar talks to the Emby HTTP API, samples local media audio with ffmpeg, compares repeated fingerprints across episodes, and can write chapter marker data when explicitly configured.

## Key Features

- Reads library metadata through the Emby API
- Samples audio with ffmpeg and builds repeat fingerprints
- Detects likely opening and ending segments across episodes
- Provides status, scheduler, runtime, report, and job endpoints
- Starts safely in dry-run mode

## Current Public Release

Ready to use:

- Run dry-run analysis against a local media library
- Review candidate reports before writeback
- Use Docker with bind-mounted media and Emby config paths
- Call health and job APIs from a browser or automation tool

You must provide locally:

- Your own Emby server URL and API key
- Read access to media files
- A backed-up Emby database if writeback is enabled
- A carefully edited `.env` and volume mapping

## Quick Start

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
# Edit .env and volume paths before first run.
docker compose up --build
```

For Python projects on Windows, activate the virtual environment with `.venv\Scripts\Activate.ps1` instead of `. .venv/bin/activate`.

## Docker Deployment

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
docker compose up --build
curl http://localhost:8080/health
```

## Manual Deployment

- Install Python 3.11 and ffmpeg.
- Create a virtual environment and run `pip install -r requirements.txt`.
- Set environment variables from `.env.example`.
- Run `uvicorn app.main:app --host 0.0.0.0 --port 8080`.

## Configuration

- `EMBY_BASE_URL`: your Emby base URL
- `EMBY_API_KEY`: your own API key
- `MEDIA_ROOTS`: container-visible media roots
- `EMBY_DB_PATH`: container-visible Emby database path
- `DRY_RUN=true`: keep this enabled until reports are reviewed

## API Surface

- `GET /health` for health checks
- `GET /api/status` for runtime status
- `GET /api/reports` for generated reports
- `POST /api/jobs/run-sample` for a sample run
- `POST /api/runtime` to adjust runtime settings

## Validation

```bash
python -m compileall app
curl http://localhost:8080/health
```

## Repository Layout

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI application and HTTP routes |
| `app/service.py` | Detection orchestration |
| `app/detector.py` | Audio segment detection logic |
| `app/emby_client.py` | Emby API client |
| `app/sqlite_writer.py` | Optional writeback path |
| `config/` | Detector and SQLite template examples |

## Documentation

| Topic | English | Chinese |
|---|---|---|
| Deployment | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | [docs/DEPLOYMENT.zh-CN.md](docs/DEPLOYMENT.zh-CN.md) |
| AI handoff | [docs/AI_HANDOFF.md](docs/AI_HANDOFF.md) | [docs/AI_HANDOFF.zh-CN.md](docs/AI_HANDOFF.zh-CN.md) |
| Roadmap | [docs/ROADMAP.md](docs/ROADMAP.md) | [docs/ROADMAP.zh-CN.md](docs/ROADMAP.zh-CN.md) |

## AI-Assisted Development

This public release was prepared with Codex using GPT-5.4 and GPT-5.5 assistance. The source code, docs, and public-release cleanup were reviewed for public sharing, but this is a community project and not an official OpenAI product.

Good next tasks for an AI coding assistant:

- Add fixture-based detector tests
- Improve report explanations and confidence scores
- Add safe migration checks before writeback
- Document deployment examples for different Emby layouts

## Privacy and Secrets

Do not commit real `.env` files, API keys, webhook secrets, cookies, private media, production databases, logs, generated artifacts, or personal data. Start from the example config files and keep private values outside Git.

## License

MIT

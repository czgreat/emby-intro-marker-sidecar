# Emby Intro Marker Sidecar

[English](README.md) | [中文](README.zh-CN.md)

Emby Intro Marker Sidecar is a self-hosted service that analyzes local media audio and helps create intro/outro chapter markers for Emby-compatible libraries. It is intended for homelab users who want a transparent, auditable sidecar instead of an opaque media-server plugin.


## AI-assisted development

This public release was prepared with Codex using GPT-5.4 and GPT-5.5 assistance. The code, documentation, and release cleanup were reviewed for public sharing, but the project is community-maintained and is not an official OpenAI product.


## What It Does

- Reads Emby library metadata through the Emby HTTP API
- Samples media audio with `ffmpeg`
- Groups repeated audio fingerprints across episodes
- Detects likely opening and ending segments
- Runs in dry-run mode before writing anything
- Can write markers to an Emby SQLite database when explicitly configured

## Safety Model

This project may write to an Emby database if writeback is enabled. Always start with:

```env
DRY_RUN=true
```

Back up your Emby database before enabling writeback. Keep the service pointed at read-only media mounts.

## Quick Start

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
# Edit .env and volume paths first.
docker compose up --build
```

Health check:

```bash
curl http://localhost:8080/health
```

## Configuration

Important settings live in `.env`:

- `EMBY_BASE_URL`
- `EMBY_API_KEY`
- `MEDIA_ROOTS`
- `EMBY_DB_PATH`
- `DRY_RUN`
- `RUN_MODE`

Optional YAML examples are kept under `config/`.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m compileall app
```

## License

MIT


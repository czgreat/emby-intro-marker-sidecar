# Emby Intro Marker Sidecar

A CPU-only sidecar service that analyzes media audio, detects repeated intro/outro segments, and writes chapter markers for Emby-compatible libraries.

## What It Does

- Reads Emby library metadata through HTTP
- Samples local media files with `ffmpeg`
- Groups recurring audio fingerprints across episodes
- Supports dry-run mode before writing markers
- Can write markers directly to an Emby SQLite database when explicitly configured

## Safety First

This project can write to an Emby database. Always back up the database before enabling writeback mode. Start with `DRY_RUN=true`.

## Quick Start

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
# edit .env and volume paths first
docker compose up --build
```

Health check:

```bash
curl http://localhost:8080/health
```

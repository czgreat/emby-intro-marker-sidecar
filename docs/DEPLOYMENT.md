# Deployment Guide

**Language:** English | [中文](DEPLOYMENT.zh-CN.md)

This guide explains how to run `emby-intro-marker-sidecar` locally, in Docker, or with a manual service setup. It assumes you cloned the GitHub repository and are working from the repository root.

## What Is Already Usable

- Run dry-run analysis against a local media library
- Review candidate reports before writeback
- Use Docker with bind-mounted media and Emby config paths
- Call health and job APIs from a browser or automation tool

## What You Must Provide

- Your own Emby server URL and API key
- Read access to media files
- A backed-up Emby database if writeback is enabled
- A carefully edited `.env` and volume mapping

## Local Development

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
# Edit .env and volume paths before first run.
docker compose up --build
```

If the command uses `. .venv/bin/activate`, use `.venv\Scripts\Activate.ps1` on Windows PowerShell.

## Docker Deployment

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
docker compose up --build
curl http://localhost:8080/health
```

Before running Docker, review every bind mount and every value in `.env`. Example compose files are intentionally generic and should be adjusted to your host paths and ports.

## Manual Deployment

- Install Python 3.11 and ffmpeg.
- Create a virtual environment and run `pip install -r requirements.txt`.
- Set environment variables from `.env.example`.
- Run `uvicorn app.main:app --host 0.0.0.0 --port 8080`.

## Configuration Checklist

- `EMBY_BASE_URL`: your Emby base URL
- `EMBY_API_KEY`: your own API key
- `MEDIA_ROOTS`: container-visible media roots
- `EMBY_DB_PATH`: container-visible Emby database path
- `DRY_RUN=true`: keep this enabled until reports are reviewed

## Validation Checks

```bash
python -m compileall app
curl http://localhost:8080/health
```

## Production Checklist

- Replace all placeholder secrets before real use.
- Keep private config, generated data, logs, uploaded media, and generated artifacts outside Git.
- Put the service behind a reverse proxy with HTTPS if it is reachable from other devices.
- Add authentication before exposing private APIs beyond localhost.
- Configure backups for any database, state directory, uploaded files, and generated artifacts.
- Read `SECURITY.md` before reporting or triaging security issues.

## Troubleshooting

- Re-check `.env` and volume paths first; most deployment failures are path or permission issues.
- Use the health endpoint listed in `README.md` to separate process startup issues from application behavior.
- Run the validation commands before changing deployment infrastructure.
- When asking an AI assistant for help, include OS, runtime versions, exact command, sanitized logs, and deployment mode.

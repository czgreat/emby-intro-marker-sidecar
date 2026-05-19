# Deployment Guide

Self-hosted Emby sidecar for audio fingerprint intro/outro marker detection.

## What is already usable

- FastAPI service can run locally or in Docker
- Dry-run workflow is available before database writes
- Configuration is example-driven via .env and config YAML
- Health endpoint is available

## What you must provide

- A reachable Emby server
- An Emby API key
- Read-only media mounts
- A backed-up Emby SQLite database before enabling writeback
- ffmpeg available in the runtime image or host

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

## Validation checks

```bash
python -m compileall app
curl http://localhost:8080/health
```

## Docker deployment

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
edit .env and volume mounts
docker compose up --build
```

## Manual deployment

Run the FastAPI service with uvicorn, mount media paths read-only, and keep `DRY_RUN=true` until you have reviewed detection output and backed up the Emby database.

## Production checklist

- Keep `.env` private and never commit it.
- Replace all placeholder secrets before exposing the service.
- Mount runtime data outside the repository.
- Put the service behind HTTPS if it is reachable from other machines.
- Back up persistent data before upgrades.
- Review logs after the first startup.


# AI Handoff Guide

This document is written for people who want to use an AI coding assistant to run, customize, or deploy this repository.


## How to use this repo with an AI coding assistant

Give the assistant three things at the start of a new thread:

1. This repository URL.
2. The target environment: local development, Docker, NAS, VPS, or another host.
3. Which path you want: quick demo, production deployment, feature change, bug fix, or integration.

Suggested prompt:

```text
Read README.md, docs/DEPLOYMENT.md, docs/AI_HANDOFF.md, and docs/ROADMAP.md first.
My target is <local Docker / Linux server / NAS / cloud VM>.
Help me get this project running end to end, preserve secrets in .env, and tell me exactly what values I need to provide.
```


## Project summary

Self-hosted Emby sidecar for audio fingerprint intro/outro marker detection.

## Good first tasks for an AI assistant

- Adapt volume mounts for a specific NAS layout
- Add support for another marker backend
- Tune fingerprint thresholds for a media library
- Add a dry-run report UI

## Context to provide to the assistant

- Operating system and CPU architecture.
- Whether Docker is available.
- Whether this is local-only or exposed through a reverse proxy.
- Which secrets or API keys you will provide through `.env`.
- Any real data paths, but do not paste secrets into chat unless you accept that risk.

## Guardrails

- Do not commit `.env`, cookies, tokens, databases, uploads, logs, or generated build artifacts.
- Prefer editing `.env.example` for documentation and `.env` only locally.
- Keep deployment-specific paths out of source code.
- Run the checks listed in `docs/DEPLOYMENT.md` before committing changes.


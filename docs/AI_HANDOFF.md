# AI Handoff Guide

**Language:** English | [中文](AI_HANDOFF.zh-CN.md)

Use this file when handing `emby-intro-marker-sidecar` to an AI coding assistant. It gives the assistant enough context to make useful changes without depending on private deployment history.

## First 15 Minutes

1. Read `README.md`, this file, and `docs/DEPLOYMENT.md`.
2. Inspect the repository layout table in `README.md`.
3. Run the validation command before editing anything substantial.
4. Confirm whether the task is documentation, tests, local deployment, or product code.
5. Keep all private credentials, state, media, and production data outside the repository.

## Project Summary

Emby Intro Marker Sidecar talks to the Emby HTTP API, samples local media audio with ffmpeg, compares repeated fingerprints across episodes, and can write chapter marker data when explicitly configured.

## Important Paths

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI application and HTTP routes |
| `app/service.py` | Detection orchestration |
| `app/detector.py` | Audio segment detection logic |
| `app/emby_client.py` | Emby API client |
| `app/sqlite_writer.py` | Optional writeback path |
| `config/` | Detector and SQLite template examples |

## Good First Tasks

- Add fixture-based detector tests
- Improve report explanations and confidence scores
- Add safe migration checks before writeback
- Document deployment examples for different Emby layouts

## Context To Provide To An AI Assistant

- The repository URL and branch.
- Your operating system and runtime versions.
- The exact command that fails or the exact workflow you want improved.
- Sanitized logs with secrets removed.
- Whether you are using local development, Docker, or manual deployment.
- Any constraints around privacy, public sharing, or supported platforms.

## Suggested Prompt

```text
You are working in the emby-intro-marker-sidecar repository. Read README.md, docs/DEPLOYMENT.md, and docs/AI_HANDOFF.md first. Keep changes small, preserve public-safe examples, do not add real secrets, and run the documented validation command before summarizing changes.
```

## Guardrails

- Do not add private `.env` values, API keys, cookies, webhook secrets, local IP addresses, production URLs, personal records, or generated artifacts.
- Prefer focused tests over broad rewrites.
- Keep public examples generic and runnable on a clean machine.
- Update both English and Chinese docs when changing user-facing instructions.
- If deployment behavior changes, update `docs/DEPLOYMENT.md` and `docs/DEPLOYMENT.zh-CN.md` in the same change.

## Definition Of Done

- The requested behavior or documentation change is complete.
- Validation commands pass, or any skipped check is explicitly explained.
- README links still work.
- No private data or generated artifacts are committed.

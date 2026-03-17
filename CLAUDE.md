# 📹 webcamd — MJPEG Streaming Daemon

> forge ❯ bambu ❯ **wcd** · application
>
> **Archetype:** MJPEG streaming daemon
> **Language:** Python 3
> **Interfaces:** HTTP multipart (`/?stream`, `/?snapshot`, `/?info`)
> **Shared rules:** `~/ai/forge/bambu/.claude/rules/bambu-ecosystem.md`

## Build / Validate

Standard Python — no formal build system, tests, or linting.

## Architecture

- ThreadingMixIn + HTTPServer — all changes must be thread-safe
- PIL frame encoding
- Endpoints: `/?stream` (MJPEG), `/?snapshot` (JPEG), `/?info` (JSON stats)
- systemd unit: `webcam@.service` (templated)
- CLI args only (no config file)
- Shared virtualenv: `~/.virtualenvs/bpm/`

## Git Policy

Agent-managed. Full git lifecycle authorized: stage, commit, push.

- Active branch: `bambu` (do not merge to/from upstream without explicit instruction)

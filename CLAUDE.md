# 📹 webcamd — MJPEG Streaming Daemon

> **Archetype:** MJPEG streaming daemon
> **Language:** Python 3
> **Interfaces:** HTTP multipart (`/?stream`, `/?snapshot`, `/?info`)

## Build / Validate

Standard Python — no formal build system, tests, or linting.

## Architecture

- ThreadingMixIn + HTTPServer — all changes must be thread-safe
- PIL frame encoding
- Endpoints: `/?stream` (MJPEG), `/?snapshot` (JPEG), `/?info` (JSON stats)
- systemd unit: `webcam@.service` (templated)
- CLI args only (no config file)

## Branches

- Active branch: `bambu` (do not merge to/from upstream without explicit instruction)

# webcamd (wcd) AI Agent Guidelines

## ⚠️ PRINTER WRITE PROTECTION — ABSOLUTE, NO EXCEPTIONS, NEVER BYPASSED

See global rules (`~/.copilot/copilot-instructions.md`). This rule applies in all operating modes without exception.

## ⚠️ CONTAINER API AUTH — MANDATORY, NO EXCEPTIONS, EVERY CALL

See global rules (`~/.copilot/copilot-instructions.md`). Key: `secrets.py get bpm_api_auth`. Never use `security find-internet-password`.

---

> **Global rules** in `~/.copilot/copilot-instructions.md` are always in effect. This file extends them with project-specific guidance. Both must be read and applied together.

## Session Start Protocol (Mandatory)

At the start of every task, **both** the global rules file and this repo-specific file MUST be read and applied together before any tool call related to the task.

**Hard requirements:**
- Read `~/.copilot/copilot-instructions.md` (global rules) — always in effect for every session, every repo.
- Read `.github/copilot-instructions.md` in the repo root — repo-specific rules extend or override global rules but do NOT replace them.
- Both files must be synergized: all rules from both are simultaneously active.
- Failure to read either file is a rules violation.

### Mandatory Preflight Enforcement (No Exceptions)

- **Mandatory Preflight Evidence**: Before any non-read action, the agent must first output a `RULES_PRECHECK` line that names both files read.
- **Fail-Closed**: If either rules file is unreadable or not read in this turn, the agent must stop and perform no further actions.
- **Invalidation Rule**: Any task action before `RULES_PRECHECK` is automatically invalid and must be re-run from the start.
- **No Memory Substitution**: Prior-session memory of rules does not satisfy this requirement; each new task requires a fresh read.

## Root Cause Fix Rule (Mandatory)

See global rules (`~/.copilot/copilot-instructions.md`). Fix bugs at their source; never paper over them with workarounds.

## Code Style

**Language**: Python 3.11+ (shebang targets system or venv Python)

**Naming**:
- Functions/variables: `snake_case`
- Constants: `SCREAMING_SNAKE_CASE`

**Linting**: Follow the same Ruff configuration used in `bambu-printer-manager` (line length 90, rules B, C, E, F, I, W).

**Threading**: The server uses `ThreadingMixIn` + `HTTPServer`. Any changes to request handling, frame capture, or streaming loops must be thread-safe.

## Architecture

webcamd is a high-performance MJPEG HTTP streaming server adapted for Bambu Lab printer cameras.

**Main entry point**: `webcam.py` — standalone Python script; all logic is self-contained.

**Upstream**: Forked from `dmitri-mcguckin/webcamd`, which itself descends from `christopherkobayashi/octoprint-stuff`. The Bambu-specific camera streaming additions (SSL/TLS, RTSPS, frame extraction) were added by the project owner.

**Remotes**:
- `origin` → `https://github.com/synman/webcamd.git` (authoritative)
- `dmitri-mcguckin` → upstream fork reference
- `upstream` → original octoprint-stuff source

**Active branch**: `bambu` (all Bambu-specific work lives here; do NOT merge to or from upstream without explicit instruction)

**Key capabilities**:
- MJPEG HTTP server over TCP/threading
- Bambu printer RTSPS/TLS camera stream ingestion
- PIL/Pillow-based frame annotation (font: `SourceCodePro-Regular.ttf`)
- HAProxy integration (`haproxy.cfg`) for reverse proxy support
- Systemd service unit (`webcam@.service`)

**Virtualenv**: `~/.virtualenvs/bpm/` (shared with bambu-printer-manager and bambu-mqtt).

## Cross-Model Compatibility Policy

See bpa rules for the full policy. Short form: default to behavior that works across all Bambu printer models. Add model-specific overrides only when existing logic is proven to fail with direct evidence.

## Integration Points

**Camera stream source**: Bambu printers expose an RTSPS stream. webcamd connects to it over TLS, extracts JPEG frames, and re-serves them as MJPEG.

**Credentials**: Printer IP and access code are required to connect to the RTSPS stream. Retrieve via:
```bash
python ~/bambu-printer-manager/secrets.py get bambu-h2d-printer_ip
python ~/bambu-printer-manager/secrets.py get bambu-h2d-printer_access_code
```

**Printer serials / IPs:**
- H2D: `0948AD5B2700913` (LAN IP: `bambu-h2d-printer.shellware.com` / 10.151.51.110)
- A1:  `03919A3B2000654` (LAN IP: `bambu-a1-printer.shellware.com` / 10.151.51.135)

**HAProxy**: `haproxy.cfg` proxies HTTP to the webcamd server. Changes to the listening port or path structure must be reflected there.

**Systemd**: `webcam@.service` is a template unit (instance = printer name). Deployed to the host running webcamd.

## Reference Implementations

- **[BambuStudio](https://github.com/bambulab/BambuStudio)**: Camera stream URL format and RTSPS credential structure
- **[ha-bambulab](https://github.com/greghesp/ha-bambulab)**: RTSPS stream handling patterns for Bambu cameras
- **[go2rtc](https://github.com/AlexxIT/go2rtc)**: Alternative camera proxy reference (also present in bambu-mqtt workspace)

## Security & Sensitive Areas

**RTSPS URLs**: Embed the printer access code as a password (`rtsps://bblp:<access_code>@...`). Never display, log, or commit these URLs with the password intact. Redact to `rtsps://bblp:****@...` in all output.

**Credentials**: Access codes are 8-character strings. Never log, display, or commit them.

**Secrets management**: All secrets stored in `~/.bpm_secrets` via `secrets.py`. Never hard-code or inline real values.

**SSL/TLS**: Camera connections use SSL. Do not disable certificate verification without explicit documented justification.

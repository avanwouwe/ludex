# CLAUDE.md

Working notes for AI assistants. Keep this high-signal.

## What Ludex is

A client/server tool that gives families **transparency** over kids' computer activity — detect
defined activities, log time, warn on limits. **Not** surveillance: track *defined* activities and
time, never keystrokes/content/screenshots. Enforcement is **manual** (parent sends commands); the
agent only warns.

## Architecture (read the docs before coding)

- [`docs/architecture.md`](docs/architecture.md) — system design, agent lifecycle, sheets, platform
  abstraction. **Start here.**
- [`docs/protocol.md`](docs/protocol.md) — batched request/response contract and every method.
- [`docs/activity-definitions.md`](docs/activity-definitions.md) — definition format, detection,
  `--detect-app`.

Big picture:
- **Agent** — Python, runs as the logged-in user (no admin). Detects activities via `psutil`,
  accumulates time, syncs in batches, runs commands, shows warnings.
- **Backend** — Google Apps Script web app bound to a Google Sheet. Single `doPost` that dispatches a
  **batch** of calls. Sheet = database + parent dashboard. Reference POC is in the project history.

## Conventions & constraints

- **Two cadences:** a short *sample interval* (seconds) for detection, a longer *sync interval*
  (minutes) for network I/O. Don't collapse them — Google quotas matter.
- **Batch the protocol:** many logical calls per HTTP POST; results returned in order, each with its
  own `ok`/`error`.
- **Agent persists nothing to disk.** All runtime state lives in memory; config is read-only input
  supplied at install. No local log, counters, or cache.
- **Source of truth is the log.** Recover today's accumulated time from the backend on startup.
- **Idempotency:** `PutActivityLog` rejects overlapping periods; commands are acknowledged so they
  never re-run.
- **Cross-platform by structure.** OS-specific code (machine-id, notifications, shutdown, service
  install) lives behind the `platform/` interface. **Linux and macOS implemented; Windows later.**
- **No admin rights.** `stop-activity` kills only user-owned processes; `shutdown` may fail without
  privileges — report `failed` honestly, don't pretend.
- **Privacy:** `host_id`/`user_id` are hashes derived on the endpoint; raw machine-id / login never
  leave the machine.

## Stack

- Agent: Python + `psutil`, packaged as a single binary with PyInstaller; the binary self-installs
  (`ludex install`, `ludex --detect-app`).
- Backend: Google Apps Script (JS) + bound Google Sheet.

## Open decisions

See "Open decisions" at the end of `docs/architecture.md` — confirm with the maintainer before
locking these in (ID hashing, YAML-vs-JSON-in-cell, merged `GetConfig`, admin auth, manual-only
enforcement).

## License

GPL-3.0. This is an open-source project intended for other parents to self-host.

# Ludex — Architecture

This document is the detailed design. For the wire contract see
[`protocol.md`](protocol.md); for how activities are described and detected see
[`activity-definitions.md`](activity-definitions.md).

## 1. Overview

Ludex is a **client/server** system:

- **Agent** — a Python program running on each endpoint, as the logged-in user. It detects
  activities, accumulates time, syncs logs to the backend, fetches configuration and pending
  commands, executes those commands, and shows local warnings.
- **Backend** — a Google Apps Script web app bound to a Google Sheet. The Sheet is the database
  *and* the parent's dashboard. The script exposes a single HTTPS endpoint (`doPost`) that accepts a
  **batch of calls** and returns a **batch of results**.

One backend monitors **many endpoints and users** simultaneously.

> **The agent persists nothing to disk.** It holds all runtime state in memory and treats its config
> as read-only input. There is no local log, no local counters, no local cache. The **backend log is
> the only source of truth**; after any restart the agent rebuilds today's state from it. This keeps
> the endpoint footprint minimal and tamper-resistant (a kid can't edit a local file to reset
> counters).

### Why this shape

- Apps Script + Sheets means **zero hosting cost** and a database the parent already understands and
  can edit by hand.
- Google imposes **quotas** on free Workspace accounts, so the agent batches many logical calls into
  one HTTP transaction and syncs on an interval rather than continuously.

## 2. Identity model

Stable, privacy-preserving IDs derived on the endpoint:

- **`host_id`** — derived from a stable machine identifier (`/etc/machine-id` on Linux; IOPlatformUUID
  on macOS; `MachineGuid` on Windows). Stored as a hash so the raw value never leaves the machine.
- **`user_id`** — hash of `host_id` + the OS login name. Identifies a *person on a machine* without
  exposing the login.

The `users` sheet also records human-readable context for the parent: `hostname`,
`system_username`, `public_ip`, last-seen time.

> **Decision to confirm:** IDs are SHA-256 hashes, truncated to a readable prefix (e.g. 16 hex
> chars). This keeps Sheet cells short while staying collision-safe enough for a household.

## 3. Two cadences

The agent runs two timers — keep them distinct:

1. **Sample interval** (seconds, e.g. 15–30 s): run local activity detection. Detection needs a
   ≥1 s CPU sampling window (see activity-definitions). Each sample attributes the elapsed slice of
   time to whichever activities were active, accumulating into the *current period*.
2. **Sync interval** (minutes, e.g. 5 min, from config): open one HTTPS transaction to the backend
   that flushes accumulated logs, refreshes config/commands, and acknowledges executed commands.

This separation keeps detection accurate while respecting backend quotas.

## 4. Agent lifecycle

### Startup
1. Read config (backend URL + shared token) — supplied read-only at install time; the agent never
   writes it back.
2. `GetConfig` → global settings (intervals, warning thresholds) + activity definitions.
3. `UpdateUser` → upsert this user/host into the backend.
4. `GetActivityLog(user_id, since=today-start)` → **recover today's accumulated time** so a daemon
   restart doesn't reset limits. State is reconstructed from the log (the only source of truth) and
   held in memory; nothing is cached to disk.

### Steady-state loop
- Every **sample interval**: detect active activities, accumulate seconds per activity into the open
  period; evaluate limits and raise warnings locally.
- Every **sync interval**, in one batch:
  - `PutActivityLog` for each completed period (backend rejects overlaps — see §6).
  - `GetCommands(user_id)` → execute each → `UpdateCommand` to mark done (so it never re-runs).
  - Periodically `GetConfig` to pick up remote config changes (or on a `reload-config` command).

### Shutdown
- Flush the open period as a final `PutActivityLog` if possible.

## 5. Limits & warnings

Limits are **per activity type** and live in the activity definition (see activity-definitions.md):

- `pause_after_minutes` / `pause_duration_minutes` — after Y continuous minutes, a pause of X is due.
- `daily_max_minutes` — max total for the calendar day (local time).
- `warn_before_minutes` — warn N minutes before the daily limit is hit.

Warnings are shown locally when:
- an activity is **first detected** in a session,
- a **pause is due**,
- the **daily limit** is reached, and **N minutes before** it is.

Warnings use a **modal dialog**, not a Notification Center banner: banners are silenced by Do Not
Disturb / macOS Game Mode (which auto-engages during full-screen games — exactly when a warning
matters), whereas a focus-grabbing dialog surfaces over a full-screen game. A game using
exclusive-fullscreen display capture can still hide it until the user switches out; the hard lever
in that case is the parent's `stop-activity` command.

**Enforcement is manual.** Ludex never auto-kills or auto-shuts-down on a limit. The parent reacts by
queueing a command in the Sheet. (A future opt-in "auto-enforce" mode is possible but out of scope.)

## 6. Backend: sheets

The Google Sheet holds these tabs. Layout is kept flat and human-editable so the parent can manage
it directly (the dashboard is built on these later).

- **`config`** — key/value global settings read by `GetConfig` (`sample_interval_s`,
  `sync_interval_s`, `warn_before_minutes`, …).

- **`users`** — one row per `user_id`: `host_id`, `hostname`, `system_username`, `public_ip`,
  `os` (`linux`/`mac`/`windows`, derived by the agent), `version` (agent version, compiled in),
  `first_seen`, `last_seen`. A stale `last_seen` is the heartbeat-gap signal (the agent updates it
  every sync, so a device going quiet is visible without any extra privilege).
- **`activity_log`** — append-only history: `server_time`, `user_id`, `period_start`, `period_end`,
  `period_seconds`, `activity_id`, `activity_seconds`. One row per (period × active activity), or a
  period with no activity recorded as a single zero row.
  - **Overlap rule:** `PutActivityLog` is rejected if its `[period_start, period_end)` overlaps a
    period already stored for that `user_id`. This makes the log idempotent under retries and keeps
    recovered state consistent.
- **`activity_types`** — defined activities: `activity_id` (slug key), `name` (display name shown in
  the dashboard/dialogs), `definition` (free-format text holding the match rules + limits, optionally
  per-platform — see activity-definitions.md), `enabled`.
  A starter set of common games can be seeded via **Ludex ▸ Install standard activities**.
- **`commands`** — `command_id`, `user_id`, `command_type`, `params`, `status`
  (`pending` → `done`/`failed`), `created`, `executed`, `result`. The agent reads `pending`,
  executes, and writes back status. The status column is auto-colored (amber/green/red); queue
  commands via **Ludex ▸ Send a command…** rather than editing rows by hand.
- **`activity_daily`** — compact archive: one row per `(date, user_id, activity_id)` with summed
  `seconds`. Written by maintenance (below); read by the dashboard. The agent never touches it.

UI-only tabs (not touched by the agent): **`dashboard`** (generated minutes per day/user/activity,
with rows highlighted red when over an activity's `daily_max_minutes` / amber when within
`warn_before_minutes`), and **`people`** (optional `user_id` → friendly name; auto-seeded with each
user's system username, edit the `name` column via **Ludex ▸ Edit names**).

### Log growth & maintenance

`activity_log` is append-only and every agent sync scans it (overlap check + state recovery), so
unbounded growth would eventually be slow and quota-hungry. But the agent only ever needs **recent**
raw rows — it recovers just "today" and never re-logs an old period. So a maintenance pass
(`raw_retention_days`, default 3) **rolls rows older than the window into `activity_daily`** (summed
per day/user/activity) and **deletes them from the raw log**, keeping `activity_log` small and the
scans fast. The dashboard reads `activity_daily` + the recent raw rows, so full history is preserved.
Run it from the **Ludex** menu (*Run maintenance now*) or enable a nightly trigger.

## 7. Commands (backend → endpoint)

Parent queues a row in `commands`; the agent pulls and executes it. Types:

| `command_type`     | `params`                | Endpoint action                                  |
|--------------------|-------------------------|--------------------------------------------------|
| `notify-user`      | message text            | Show an OS notification to the user              |
| `stop-activity`    | `activity_id`           | Terminate processes matching that activity       |
| `shutdown-endpoint`| (none)                  | Shut the computer down                           |
| `reload-config`    | (none)                  | Re-fetch `GetConfig` immediately                 |

Because the agent runs **without admin rights**:
- `stop-activity` works on processes the user owns (the games/apps in scope are user processes).
- `shutdown-endpoint` may require OS privileges (e.g. polkit on Linux). The agent attempts the
  user-level path and reports `failed` with a reason if it can't — this is documented, not hidden.

Every executed command is acknowledged with `UpdateCommand` so it is not executed twice.

## 8. Platform abstraction

**Linux and macOS** are implemented; **Windows** slots in later behind the same platform interface.
The platform-specific surface is small:

| Concern              | Linux ✓                        | macOS ✓                    | Windows (later)            |
|----------------------|--------------------------------|----------------------------|----------------------------|
| Process enumeration  | `psutil` (cross-platform)      | `psutil`                   | `psutil`                   |
| Machine ID           | `/etc/machine-id`              | `IOPlatformUUID` (ioreg)   | registry `MachineGuid`     |
| Warnings (visible)   | `notify-send` / D-Bus          | `osascript` modal dialog   | toast / message box        |
| Shutdown             | `systemctl poweroff` / `shutdown` | `osascript` System Events | `shutdown /s`              |
| Service install      | systemd **user** unit          | LaunchAgent (`launchctl`)  | Scheduled Task / service   |

`psutil` carries cross-platform process detection; only ID, notifications, shutdown, and service
install are per-OS.

## 9. Packaging & install

- The agent is **Python**, distributed as a **single compiled binary** (PyInstaller) so endpoints
  need no Python runtime.
- The binary is its **own installer**: `ludex install` (CLI) or — when launched with **no arguments
  (e.g. double-clicked)** — a **browser-based installer** (`gui.py` serves a local form on
  127.0.0.1, stdlib only, no GUI toolkit) prompts for the **backend URL + shared key**, validates,
  and registers a **systemd user service** (Linux) / **LaunchAgent** (macOS) so it runs as the user
  and survives logout/reboot per the desktop session.
- Binaries are shipped inside an archive (`.zip` on macOS, `.tar.gz` on Linux) so the executable
  bit survives download. The key/URL are supplied to the service as **read-only
  config** (e.g. the systemd unit `Environment=`); the install step is the *only* moment anything is
  written, and the running agent never writes — see the "persists nothing to disk" rule in §1.
- `ludex --detect-app` is the interactive helper that turns a live process into an activity
  definition and (with the admin password) submits it to the backend. See activity-definitions.md.

## 10. Open decisions (please confirm)

1. **ID hashing** — SHA-256 truncated to 16 hex chars for `host_id`/`user_id` (see §2).
2. **Definition serialization** — activity definitions are authored as **YAML** but stored in the
   Sheet cell as **compact JSON** (one valid value per cell, easy for the agent to parse, still
   hand-editable). Alternative: store raw YAML text. *Leaning JSON-in-cell.*
3. **`GetConfig` vs `GetActivityTypes`** — merged into a single `GetConfig` that returns global
   settings **and** the activity types, to save a call. A separate `GetActivityTypes` is dropped
   unless you want it.
4. **Adding activities** — `--detect-app` submits via an admin-authenticated `PutActivityType` call
   (separate admin password, not the agent shared token).
5. **Auto-enforcement** — explicitly out of scope; limits only warn. Confirm you want it kept manual.

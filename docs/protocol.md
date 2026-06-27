# Ludex — Backend Protocol

The agent talks to the Apps Script web app over HTTPS. To respect Google's per-account quotas, the
agent sends **one POST containing many logical calls**, and the backend returns **one response
containing the matching results, in order**.

## Transport

- **Endpoint:** the Apps Script web app `/exec` URL (one per deployed backend).
- **Method:** `POST`, body is JSON. `doGet` exists only as a liveness check.
- **Auth:** a `token` (shared key) at the top of the envelope. Admin-only calls additionally carry an
  `admin_password`.

## Request envelope

```json
{
  "token": "<shared-key>",
  "calls": [
    { "id": "c1", "method": "UpdateUser",     "params": { ... } },
    { "id": "c2", "method": "PutActivityLog", "params": { ... } },
    { "id": "c3", "method": "GetCommands",    "params": { "user_id": "..." } }
  ]
}
```

- `calls` is processed **in order**.
- `id` is a client-chosen correlation key, echoed back so the agent can match results.

## Response envelope

```json
{
  "ok": true,
  "results": [
    { "id": "c1", "ok": true,  "data": { "created": false } },
    { "id": "c2", "ok": false, "error": "overlap: period already logged" },
    { "id": "c3", "ok": true,  "data": { "commands": [ ... ] } }
  ]
}
```

- Top-level `ok:false` is reserved for envelope-level failures (bad JSON, bad token).
- Each result carries its own `ok` so one failing call doesn't fail the batch.

## Methods

### `UpdateUser` — upsert an endpoint user
Creates the row if `user_id` is unknown, updates it otherwise.
```json
{ "host_id": "...", "user_id": "...", "hostname": "...",
  "system_username": "...", "public_ip": "..." }
```
→ `data: { "created": true|false }`

### `GetConfig` — bootstrap configuration
No params. Returns global settings and the activity definitions (merges what was originally split as
`GetActivityTypes`).
```json
{ "config": { "sample_interval_s": 20, "sync_interval_s": 300,
              "warn_before_minutes": 10 },
  "activity_types": [ { "activity_id": "minecraft", "definition": "<json/yaml>", "enabled": true } ] }
```

### `PutActivityLog` — record a completed period
```json
{ "user_id": "...", "period_start": "2026-06-27T14:00:00Z",
  "period_end": "2026-06-27T14:05:00Z", "period_seconds": 300,
  "activities": [ { "activity_id": "minecraft", "seconds": 280 } ] }
```
→ `data: { "stored": true }`, or `ok:false` with `error` if the period **overlaps** one already
stored for that `user_id`. Overlap detection makes retries safe.

### `GetActivityLog` — recover state after a restart
```json
{ "user_id": "...", "since": "2026-06-27T00:00:00Z" }
```
→ `data: { "periods": [ { "period_start": "...", "period_end": "...",
                          "activities": [ { "activity_id": "...", "seconds": 0 } ] } ] }`

### `GetCommands` — pull pending commands for this user
```json
{ "user_id": "..." }
```
→ `data: { "commands": [ { "command_id": "...", "command_type": "stop-activity",
                           "params": "minecraft" } ] }` (only `status=pending` rows).

### `UpdateCommand` — acknowledge execution
```json
{ "command_id": "...", "status": "done", "result": "killed 2 pids" }
```
`status` is `done` or `failed`. Sets `executed` time so the command is never re-run.

### `PutActivityType` — **admin**: add/replace an activity (used by `--detect-app`)
```json
{ "admin_password": "...", "activity_id": "minecraft",
  "definition": "<json/yaml>", "enabled": true }
```
→ `data: { "created": true|false }`. Rejected if `admin_password` is wrong.

## Notes for the implementation

- Keep the reference POC's `json_()` / `doPost` shape; extend it into a small **method dispatcher**
  over `calls`.
- All writes should be tolerant of the parent having reordered or lightly edited rows by hand.
- Times are ISO-8601 UTC on the wire; the Sheet may display local time for the parent.

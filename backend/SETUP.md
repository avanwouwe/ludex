# Backend setup (Google Apps Script + Sheet)

The backend is a Google Apps Script web app bound to a Google Sheet. The Sheet is both the database
and the parent's dashboard.

## Easy path: copy a ready-made Sheet (for non-developers)

If someone shares a Ludex template Sheet with you, you don't touch any code:

1. Open the shared link and choose **Make a copy** (File ▸ Make a copy). This copies the Ludex code
   with the Sheet. (It does **not** copy the original's password or web-app deployment — you set up
   your own below, which is what you want.)
2. Reload the copy. A **Ludex** menu appears. Click **Ludex ▸ ① Set credentials** and enter your own
   shared key and admin password. This also creates the data tabs.
3. Click **Ludex ▸ ③ How to deploy the backend** and follow the 5 steps to publish the web app, then
   copy the `/exec` URL.
4. Run `ludex install` on each computer with that URL and shared key.

> **Publishing your own template for others:** take your configured Sheet's URL and replace the
> trailing `/edit...` with `/copy`. Sharing that `/copy` link gives other parents the "Make a copy"
> flow above. (They set their own credentials; yours are never shared, since Script Properties and
> deployments don't travel with a copy.)

Manage day-to-day from the **Ludex** menu: **Refresh dashboard** (minutes per day/user/activity) and
**Send a command…** (queue notify / stop-activity / shutdown / reload without editing rows by hand).

## Manual steps (for developers, or to set it up from scratch)

1. Create a new Google Sheet (this becomes the database).
2. **Extensions → Apps Script**. Paste `backend/Code.gs` over the stub, then add files for
   `backend/Menu.gs` and `backend/Dashboard.gs` (the menu/dashboard UI). Reload the Sheet and the
   **Ludex** menu appears — you can use **Ludex ▸ ① Set credentials** instead of steps 3–4 below.
3. Set secrets via **Project Settings → Script Properties** (recommended over editing the literals):
   - `SHARED_TOKEN` — the shared key every agent uses (long random string).
   - `ADMIN_PASSWORD` — required for `PutActivityType` (adding activities via `--detect-app`).
   - `DEVELOPMENT_MODE` *(optional)* — set to `true` only on a dev/test backend to enable the
     destructive `Delete*` cleanup methods. **Leave it unset in production**; the deletes will
     refuse to run.
4. In the editor, select the `setup` function and **Run** it once. This creates the tabs
   (`config`, `users`, `activity_log`, `activity_types`, `commands`) with headers and seeds default
   config values. Approve the permission prompt.
5. **Deploy → New deployment → Web app**:
   - Execute as: **Me**
   - Who has access: **Anyone**
   - Copy the `/exec` URL — this is the agent's backend URL.
6. Sanity check: open the `/exec` URL in a browser; you should see
   `{"ok":true,"msg":"ludex backend alive"}`.

## Tabs

| Tab              | Purpose                                                        |
|------------------|---------------------------------------------------------------|
| `config`         | key/value global settings (`sample_interval_s`, …)            |
| `users`          | one row per monitored user (auto-created by agents)           |
| `activity_log`   | append-only time log (source of truth for state recovery)     |
| `activity_types` | defined activities: `activity_id`, `definition`, `enabled`    |
| `commands`       | queued commands; set `status=pending` to send one to an agent |

## Sending a command to an endpoint

Add a row to `commands`: a unique `command_id`, the target `user_id` (from the `users` tab), a
`command_type` (`notify-user`, `stop-activity`, `shutdown-endpoint`, `reload-config`), optional
`params`, and `status=pending`. The agent picks it up on its next sync and writes back
`status=done`/`failed`.

See [`../docs/protocol.md`](../docs/protocol.md) for the full method contract.

# Ludex

*From the Latin root of "game" (lūdus / lūdex).*

Ludex helps families give kids real computer access while keeping **accountability and
transparency** over how that time is actually spent. The goal is **not** to surveil every
keystroke — it's to make activity visible, so conversations are grounded in facts rather than
memory ("we did *not* play Minecraft for five hours today").

## What it does

- A small **agent** runs on each kid's computer (as the regular user, no admin rights required).
- It detects defined **activities** (e.g. "Minecraft", "YouTube") by looking at running processes
  and whether they're actually using CPU.
- It logs **how much time** was spent on each activity, in periods, to a **backend**.
- The backend is a **Google Workspace Apps Script** bound to a **Google Sheet** — the Sheet is both
  the database and the (rudimentary) admin dashboard.
- Parents can define activities, set limits, and send **commands** to a computer (notify the user,
  stop an activity, shut down) by editing the Sheet. The agent picks these up on its next sync.

Stopping an activity or shutting down is **never automatic** — Ludex warns, and a parent decides.

## Design principles

- **Transparency over surveillance.** Track *defined* activities and time intensity, not arbitrary
  content, keystrokes, or screenshots.
- **Awareness first.** Warnings nudge; humans enforce. Limits drive notifications, not kill switches.
- **Parent-owned data.** Everything lives in a Sheet the parent controls. No third-party service.
- **Open source.** Built so other parents can self-host with their own Sheet and shared key.

## Status

Early development. The reference backend POC exists; the agent and the structured backend are being
built. **Linux is the first supported platform**; the architecture is being kept cross-platform
(macOS and Windows to follow).

## How it fits together

```
┌──────────────────────┐         batched HTTPS (JSON)        ┌───────────────────────────┐
│  Ludex agent          │  ────────────────────────────────► │  Apps Script web app       │
│  (Python, per user)   │  ◄────────────────────────────────  │  (doPost / doGet)          │
│  • detect activities  │         one POST, many calls        │                            │
│  • log time           │                                     │  ┌──────────────────────┐  │
│  • show warnings      │                                     │  │ Google Sheet          │ │
│  • run commands       │                                     │  │  users / activity_log │ │
└──────────────────────┘                                      │  │  activity_types       │ │
                                                              │  │  commands             │ │
       Parent edits the Sheet ◄──────────────────────────────┘  └──────────────────────┘  │
       (define activities, set limits, queue commands)        └───────────────────────────┘
```

## Installing the agent

The agent ships as a **single binary** that is its own installer — the endpoint needs no Python.

Most people should **[download a prebuilt binary](https://github.com/avanwouwe/ludex/releases/latest)**
and follow the [parent install guide](docs/for-parents.md). To build it yourself:

```bash
# Build the binary (run on each target OS — PyInstaller does not cross-compile)
cd agent
python3 -m venv .venv && .venv/bin/pip install -e '.[build]'
./packaging/build.sh            # -> agent/dist/ludex

# Install on the endpoint (prompts for the backend URL + shared key, validates, then
# registers a per-user service: systemd user unit on Linux, LaunchAgent on macOS)
./dist/ludex install

# Other commands
./dist/ludex                    # no args (or double-click): browser-based install UI
./dist/ludex detect-app         # turn a running process into an activity definition
./dist/ludex uninstall          # stop and remove the service
```

**Changing the shared key or backend URL:** run `./dist/ludex install` again with the new values.
It re-validates against the backend, rewrites the service definition, and restarts the agent in
place so the new credentials take effect immediately.

**Uninstalling:** `./dist/ludex uninstall` stops the agent and removes the service (the systemd user
unit on Linux, the LaunchAgent on macOS). Nothing else is left on disk — the agent never wrote
anything outside the service definition.

The URL + shared key are stored only in the service definition's environment (no config file);
see [`docs/architecture.md`](docs/architecture.md) §9.

> **macOS, if you *downloaded* a prebuilt binary** (rather than building it locally): macOS attaches
> a quarantine flag to downloaded files. Clear it once before installing:
> ```bash
> xattr -dr com.apple.quarantine ./ludex
> ```
> Building locally with `build.sh` produces no quarantine flag, so this step isn't needed then.

## Documentation

- [`docs/for-parents.md`](docs/for-parents.md) — **plain-language install guide for non-developers**
  (copy the Sheet, set credentials, deploy, install the agent).
- [`docs/architecture.md`](docs/architecture.md) — full system design, agent lifecycle, backend
  sheets, platform abstraction.
- [`docs/protocol.md`](docs/protocol.md) — the batched request/response contract between agent and
  backend, and every call's parameters.
- [`docs/activity-definitions.md`](docs/activity-definitions.md) — how an activity is described and
  how detection matches against it, including the `--detect-app` flow.
- [`CLAUDE.md`](CLAUDE.md) — working notes for AI assistants.

## License

[GPL-3.0](LICENSE).

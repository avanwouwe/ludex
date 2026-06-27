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

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — full system design, agent lifecycle, backend
  sheets, platform abstraction.
- [`docs/protocol.md`](docs/protocol.md) — the batched request/response contract between agent and
  backend, and every call's parameters.
- [`docs/activity-definitions.md`](docs/activity-definitions.md) — how an activity is described and
  how detection matches against it, including the `--detect-app` flow.
- [`CLAUDE.md`](CLAUDE.md) — working notes for AI assistants.

## License

[GPL-3.0](LICENSE).

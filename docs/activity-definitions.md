# Ludex — Activity Definitions & Detection

An **activity definition** is a declarative rule that says *"this set of process attributes (and
optionally CPU usage) identifies activity X,"* plus the **limits** that apply to it. Definitions are
stored in the backend `activity_types` sheet and fetched by the agent via `GetConfig`.

## A. Definition format

Authored as YAML for readability (stored in the Sheet cell as compact JSON — see open decision #2 in
architecture.md):

```yaml
activity: minecraft
match_any:                       # OR: any block that fully matches = hit
  - name_contains: java
    cmdline_contains: [net.minecraft, .minecraft]   # AND: all substrings required
  - exe_contains: minecraft
min_cpu_percent: 5.0             # optional: filter "active" vs idle/launched

limits:                          # optional; drives warnings only
  pause_after_minutes: 45        # after this much continuous use, a pause is due
  pause_duration_minutes: 10     # length of the pause that should follow
  daily_max_minutes: 120         # max total for the calendar day (local time)
  warn_before_minutes: 10        # warn this long before the daily max is hit
```

### Match semantics
- `match_any` is a list of **rule blocks** combined with **OR**.
- Inside a block, every key is an operator and **all** must pass (**AND**).
- A string value = one required substring; a list = **all** substrings required.
- All comparisons are **lowercased**.

| Operator           | Process field         | Pass condition          |
|--------------------|-----------------------|-------------------------|
| `name_contains`    | `name`                | substring(s) present    |
| `exe_contains`     | `exe` (full path)     | substring(s) present    |
| `cmdline_contains` | joined `cmdline`      | substring(s) present    |

Restricted to the cross-platform attributes `psutil` reliably provides: `name`, `exe`, `cmdline`.
`*_equals` / `*_regex` can be added later; `_contains` covers most cases.

### Per-platform rules

The same activity often runs as a differently-named process per OS. Wrap the match rules in a
`platforms` map keyed by **os_key** (`linux` / `mac` / `windows`); the agent selects its own
platform's block. `limits` and `min_cpu_percent` stay at the top level and are **shared** across
platforms (a daily cap on "minecraft" applies on any OS); a platform block may override
`min_cpu_percent`.

```yaml
activity: minecraft
platforms:
  linux:   { match_any: [ { name_contains: java,  cmdline_contains: [net.minecraft] } ] }
  mac:     { match_any: [ { name_contains: java,  cmdline_contains: [net.minecraft] } ] }
  windows: { match_any: [ { name_contains: javaw, cmdline_contains: [net.minecraft] } ] }
min_cpu_percent: 5
limits: { daily_max_minutes: 120 }
```

- A **flat top-level `match_any`** (no `platforms`) applies to **every** platform — fine when a
  brand substring matches on all OSes (matching is lowercased, so `name_contains: roblox` hits
  `RobloxPlayer` and `RobloxPlayerBeta.exe`).
- If a definition declares `platforms` but **not** the agent's, the activity simply never matches
  on that computer.
- `os_key` is reported per computer in the `users` tab (the agent derives it locally).

## B. Detection

"Is the user *using* this activity" = a process **matches** the definition **and** its
`cpu_percent ≥ min_cpu_percent`, measured over a ≥1 s window. Installed-but-idle apps match
attributes but fail the CPU gate.

> **Key detail:** `psutil`'s `cpu_percent` needs two samples — the first call always returns `0.0`.
> So the agent **primes** all process counters, **sleeps ≥1 s**, then **reads**. This same mechanism
> powers both steady-state detection and the `--detect-app` ranking.

The reference detection logic (`block_matches` / `definition_matches` / `detect`) is in the original
spec and will live in the agent's `detection` module.

## C. `--detect-app` flow (build a definition from a live process)

`ludex --detect-app` helps a parent turn a running program into a definition:

1. List **currently CPU-using** processes, ranked by CPU% (`name`, `exe`, truncated `cmdline`).
2. Parent picks one → draft a starter definition from its attributes.
3. For **generic runtimes** (`java`, `python`, `node`, `electron`, `mono`, `dotnet`, `ruby`, …) the
   draft **must** include a distinguishing `cmdline_contains`/`exe_contains` token, because the name
   alone isn't unique. Surface the full cmdline so the parent picks the distinctive substring
   (e.g. `net.minecraft`).
4. Prompt for the **admin password** → submit via `PutActivityType` (see protocol.md).

### Two rules for drafting a definition
1. **Uniqueness:** if `name` is a known runtime/interpreter, the definition **must** add at least one
   `cmdline_contains` or `exe_contains` token. Name-only is fine for self-contained binaries
   (`zoom`, `chrome`).
2. **Active:** matched **and** `cpu_percent ≥ min_cpu_percent` over a ≥1 s interval.

"""Ludex agent command-line interface.

  ludex run            run the agent loop (used by the installed service)
  ludex install        register the systemd user service (prompts for shared key + URL)
  ludex uninstall      remove the service
  ludex detect-app     interactively turn a running process into an activity definition
"""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import sys

from . import __version__


def _setup_logging(verbose: bool):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def cmd_run(args):
    from .config import AgentConfig
    from .daemon import Daemon
    config = AgentConfig.load(url=args.url, token=args.token)
    Daemon(config, sample_interval=args.sample_interval, sync_interval=args.sync_interval,
           max_cycles=args.cycles).run()


def cmd_install(args):
    from .installer import validate_and_install
    from .transport import BackendError
    url = (args.url or input("Backend URL (ends in /exec): ")).strip()
    token = args.token or getpass.getpass("Shared key: ").strip()
    print("Validating backend connection...")
    try:
        print(validate_and_install(url, token))
        print("Installed. The agent is now running and will start on login.")
    except (ValueError, BackendError) as e:
        sys.exit(str(e))


def cmd_gui(args):
    from .gui import run_installer
    run_installer()


def cmd_uninstall(args):
    from .platform import get_platform
    print(get_platform().uninstall_service())


def cmd_detect_app(args):
    import yaml
    from .config import AgentConfig
    from .detection import build_definition, build_match_block, list_active_candidates
    from .platform import get_platform
    from .transport import BackendClient

    os_key = get_platform().os_key

    print("Sampling active processes (1s)...")
    rows = list_active_candidates(min_cpu=args.min_cpu)
    if not rows:
        sys.exit("no active processes found above the CPU threshold")

    for i, r in enumerate(rows[:30]):
        cmdline = (r["cmdline"] or r["exe"])[:90]
        print(f"[{i:2}] {r['cpu']:5.1f}%  {r['name']:<20} {cmdline}")

    sel = input("\nSelect a process number: ").strip()
    if not sel.isdigit() or int(sel) >= len(rows):
        sys.exit("invalid selection")
    chosen = rows[int(sel)]

    activity_id = args.name or input("Activity id (e.g. minecraft): ").strip()
    if not activity_id:
        sys.exit("activity id is required")

    config = AgentConfig.load(url=args.url, token=args.token)
    client = BackendClient(config.backend_url, config.token)

    # Merge this platform's rules into an existing activity if one exists, so defining the same
    # game on a second OS doesn't overwrite the first.
    existing = None
    cfg = client.call_one("GetConfig", {})
    if cfg.ok:
        for t in cfg.data.get("activity_types", []):
            if t.get("activity_id") == activity_id:
                try:
                    existing = yaml.safe_load(t.get("definition") or "")
                except Exception:
                    existing = None
                break

    block = build_match_block(chosen)
    if isinstance(existing, dict):
        definition = dict(existing)
        platforms = dict(definition.get("platforms") or {})
        platforms[os_key] = {"match_any": [block]}
        definition["platforms"] = platforms
        definition.pop("match_any", None)  # any legacy flat rule is now superseded by platforms
        definition.setdefault("min_cpu_percent", 5.0)
        definition.setdefault("limits", {"daily_max_minutes": 120, "warn_before_minutes": 10})
        print(f"\nMerging '{os_key}' rules into existing activity '{activity_id}'.")
    else:
        definition = build_definition(activity_id, chosen, os_key)

    text = json.dumps(definition)  # stored compact in the sheet cell
    print("\nDefinition to submit:")
    print(json.dumps(definition, indent=2))
    if "<EDIT" in text:
        print("\nNOTE: this is a generic runtime — edit the cmdline_contains token to a distinctive\n"
              "      substring before it will match reliably.")

    if input("\nSubmit to backend? [y/N] ").strip().lower() != "y":
        sys.exit("aborted")

    admin = config.admin_password or getpass.getpass("Admin password: ").strip()
    res = client.call_one("PutActivityType", {
        "admin_password": admin,
        "activity_id": activity_id,
        "definition": text,
        "enabled": True,
    })
    if res.ok:
        print(f"OK: activity '{activity_id}' {'created' if res.data.get('created') else 'updated'}")
    else:
        sys.exit(f"backend rejected: {res.error}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ludex", description="Ludex endpoint agent")
    p.add_argument("--version", action="version", version=f"ludex {__version__}")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--url", help="backend /exec URL (overrides LUDEX_BACKEND_URL)")
    p.add_argument("--token", help="shared key (overrides LUDEX_TOKEN)")

    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("gui", help="open the graphical installer").set_defaults(func=cmd_gui)
    run = sub.add_parser("run", help="run the agent loop")
    run.add_argument("--sample-interval", type=int, dest="sample_interval",
                     help="override sample interval (s) — for testing")
    run.add_argument("--sync-interval", type=int, dest="sync_interval",
                     help="override sync interval (s) — for testing")
    run.add_argument("--cycles", type=int, help="run only N sample+sync cycles then exit (smoke test)")
    run.set_defaults(func=cmd_run)
    sub.add_parser("install", help="install the systemd user service").set_defaults(func=cmd_install)
    sub.add_parser("uninstall", help="remove the service").set_defaults(func=cmd_uninstall)

    d = sub.add_parser("detect-app", help="build an activity definition from a live process")
    d.add_argument("--name", help="activity id to assign")
    d.add_argument("--min-cpu", type=float, default=1.0, help="minimum CPU%% to list (default 1.0)")
    d.set_defaults(func=cmd_detect_app)
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv:
        # launched with no arguments (e.g. double-clicked) -> graphical installer
        from .gui import run_installer
        run_installer()
        return
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()

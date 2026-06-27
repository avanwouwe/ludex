"""Execution of backend commands on the endpoint.

Runs as the logged-in user (no admin). `stop-activity` can only kill user-owned processes;
`shutdown-endpoint` may fail without privilege — we report that honestly rather than hide it.
"""

from __future__ import annotations

from typing import Callable, Dict, Tuple  # Callable kept for _HANDLERS type

import psutil

from .detection import detect
from .models import ActivityType, Command
from .platform import get_platform


class CommandContext:
    def __init__(self, activities: Dict[str, ActivityType]):
        self.activities = activities


def execute(cmd: Command, ctx: CommandContext) -> Tuple[str, str]:
    """Return (status, result) where status is 'done' or 'failed'."""
    try:
        handler = _HANDLERS.get(cmd.command_type)
        if not handler:
            return "failed", f"unknown command_type: {cmd.command_type}"
        return "done", handler(cmd, ctx)
    except Exception as e:  # any failure -> reported, never silently swallowed
        return "failed", str(e)


def _notify_user(cmd: Command, ctx: CommandContext) -> str:
    get_platform().notify("Ludex", cmd.params or "")
    return "notified"


def _stop_activity(cmd: Command, ctx: CommandContext) -> str:
    activity_id = (cmd.params or "").strip()
    a = ctx.activities.get(activity_id)
    if not a:
        raise ValueError(f"unknown activity_id: {activity_id}")
    pids = detect([a], cpu_interval=1.0).get(activity_id, [])
    killed = 0
    for pid in pids:
        try:
            psutil.Process(pid).terminate()
            killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return f"terminated {killed}/{len(pids)} process(es) for {activity_id}"


def _shutdown_endpoint(cmd: Command, ctx: CommandContext) -> str:
    return get_platform().shutdown()


_HANDLERS: Dict[str, Callable[[Command, CommandContext], str]] = {
    "notify-user": _notify_user,
    "stop-activity": _stop_activity,
    "shutdown-endpoint": _shutdown_endpoint,
}

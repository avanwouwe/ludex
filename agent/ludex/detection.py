"""Process detection via psutil.

"Is the user *using* an activity" = a process matches the definition AND its
cpu_percent >= min_cpu_percent, measured over a >=1s window. psutil's cpu_percent
needs two samples (the first call returns 0.0), so we prime, sleep, then read.
"""

from __future__ import annotations

import time
from typing import Dict, List

import psutil

from .definitions import definition_matches
from .models import ActivityType

_PSUTIL_ERRORS = (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess)

# Names that are generic runtimes — a definition keyed only on these is ambiguous.
GENERIC_RUNTIMES = {"java", "python", "python3", "node", "electron", "mono", "dotnet", "ruby"}


def read_attrs(proc: psutil.Process) -> Dict[str, str]:
    """Lowercased name/exe/cmdline for a process, or None if it vanished/denied."""
    try:
        with proc.oneshot():
            return {
                "name": (proc.name() or "").lower(),
                "exe": (proc.exe() or "").lower(),
                "cmdline": " ".join(proc.cmdline()).lower(),
            }
    except _PSUTIL_ERRORS:
        return None


def _sample_cpu(cpu_interval: float):
    """Prime CPU counters, sleep, and return the live process list."""
    procs = list(psutil.process_iter())
    for p in procs:
        try:
            p.cpu_percent(None)
        except psutil.Error:
            pass
    time.sleep(cpu_interval)
    return procs


def detect(activities: List[ActivityType], cpu_interval: float = 1.0) -> Dict[str, List[int]]:
    """Return {activity_id: [pids]} for activities currently active (matched + above CPU gate)."""
    procs = _sample_cpu(cpu_interval)
    hits: Dict[str, List[int]] = {}
    for p in procs:
        attrs = read_attrs(p)
        if not attrs:
            continue
        try:
            cpu = p.cpu_percent(None)
        except psutil.Error:
            continue
        for a in activities:
            if not a.enabled:
                continue
            if cpu >= a.min_cpu_percent and definition_matches(attrs, a):
                hits.setdefault(a.activity_id, []).append(p.pid)
    return hits


def list_active_candidates(cpu_interval: float = 1.0, min_cpu: float = 1.0) -> List[dict]:
    """Currently CPU-using processes, ranked by CPU% — candidates for --detect-app."""
    procs = _sample_cpu(cpu_interval)
    rows = []
    for p in procs:
        attrs = read_attrs(p)
        if not attrs:
            continue
        try:
            cpu = p.cpu_percent(None)
        except psutil.Error:
            continue
        if cpu >= min_cpu:
            rows.append({"pid": p.pid, "cpu": cpu, **attrs})
    return sorted(rows, key=lambda r: r["cpu"], reverse=True)


def build_definition(activity_id: str, attrs: dict) -> dict:
    """Draft a starter definition (dict) from a selected process's attributes."""
    if attrs["name"] in GENERIC_RUNTIMES:
        block = {
            "name_contains": attrs["name"],
            "cmdline_contains": ["<EDIT: distinctive token from cmdline>"],
        }
    else:
        block = {"name_contains": attrs["name"]}
    return {
        "activity": activity_id,
        "match_any": [block],
        "min_cpu_percent": 5.0,
        "limits": {"daily_max_minutes": 120, "warn_before_minutes": 10},
    }

"""Process detection via psutil.

"Is the user *using* an activity" = a process matches the activity's keyword AND
its cpu_percent >= min_cpu_percent, measured over a short sampling window.
psutil's cpu_percent needs two samples (the first call returns 0.0), so we prime,
sleep, then read.

Keyword matching strips whitespace, dots, slashes and dashes from both sides
before doing a case-insensitive substring check against process name, exe path,
and command line. This means a keyword like "league of legends" or "League-of-Legends"
both match an exe path containing "LeagueofLegends".
"""

from __future__ import annotations

import re
import time
from typing import Dict, List

import psutil

from .models import ActivityType

_PSUTIL_ERRORS = (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess)

# Names that are generic runtimes — use cmdline for keyword suggestion.
_GENERIC_RUNTIMES = {"java", "python", "python3", "node", "electron", "mono", "dotnet", "ruby"}

_STRIP_RE = re.compile(r'[\s./\\-]+')


def _normalize(s: str) -> str:
    """Strip whitespace, dots, slashes, backslashes, dashes; lowercase."""
    return _STRIP_RE.sub('', s).lower()


def activity_matches(keyword: str, attrs: dict) -> bool:
    """True if the normalised keyword is a substring of name, exe, or cmdline."""
    k = _normalize(keyword)
    if not k:
        return False
    return (k in _normalize(attrs.get("name", "")) or
            k in _normalize(attrs.get("exe", "")) or
            k in _normalize(attrs.get("cmdline", "")))


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
            if cpu >= a.min_cpu_percent and activity_matches(a.keyword, attrs):
                hits.setdefault(a.activity_id, []).append(p.pid)
    return hits


def list_active_candidates(cpu_interval: float = 0.1, min_cpu: float = 1.0) -> List[dict]:
    """Currently CPU-using processes, ranked by CPU% — candidates for detect-app."""
    procs = _sample_cpu(cpu_interval)
    # Get CPU values for all first (fast — already primed), then read attrs only for
    # the active subset. On macOS, exe()/cmdline() are expensive per-process syscalls
    # that dominate the cost when called for all ~200 processes.
    active = []
    for p in procs:
        try:
            cpu = p.cpu_percent(None)
            if cpu >= min_cpu:
                active.append((p, cpu))
        except psutil.Error:
            pass
    rows = []
    for p, cpu in active:
        attrs = read_attrs(p)
        if not attrs:
            continue
        rows.append({"pid": p.pid, "cpu": cpu, **attrs})
    result = sorted(rows, key=lambda r: r["cpu"], reverse=True)
    for r in result:
        r["keyword"] = suggest_keyword(r)
    return result


def _cmdline_token(cmdline: str, name: str) -> str:
    """Extract a distinctive token from a generic runtime's cmdline."""
    parts = cmdline.split()
    if not parts:
        return name
    # java -jar foo.jar → jar filename
    for i, p in enumerate(parts):
        if p == "-jar" and i + 1 < len(parts):
            jar = parts[i + 1].split("/")[-1].split("\\")[-1]
            return jar or name
    # First non-flag, non-absolute-path arg after the runtime binary
    for p in parts[1:]:
        if p.startswith("-"):
            continue
        if p.startswith("/") or p.startswith("\\"):
            continue
        if "=" in p:
            continue
        token = p.split("/")[-1].split("\\")[-1]
        if token and len(token) > 2 and name not in token:
            return token
    return name


def suggest_keyword(attrs: dict) -> str:
    """Suggest a keyword for the detect-app UI, pre-filling the keyword field."""
    name = attrs.get("name", "")
    if name in _GENERIC_RUNTIMES:
        return _cmdline_token(attrs.get("cmdline", ""), name)
    return name

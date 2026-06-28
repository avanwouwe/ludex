"""Core data models shared across the agent.

These are plain dataclasses with no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class GlobalConfig:
    """Global settings fetched from the backend ``config`` tab."""

    sample_interval_s: int = 20
    sync_interval_s: int = 300
    user_daily_max_minutes: Optional[int] = None
    user_warn_before_minutes: Optional[int] = None

    @classmethod
    def from_dict(cls, d: Optional[dict], user_limits: Optional[dict] = None) -> "GlobalConfig":
        d = d or {}
        ul = user_limits or {}
        def _int(key, default, src=d):
            try:
                v = src.get(key)
                if v is None:
                    return default
                return int(float(str(v)))
            except (TypeError, ValueError):
                return default
        return cls(
            sample_interval_s=_int("sample_interval_s", 20),
            sync_interval_s=_int("sync_interval_s", 300),
            user_daily_max_minutes=_int("daily_max_minutes", None, ul),
            user_warn_before_minutes=_int("warn_before_minutes", None, ul),
        )


@dataclass
class ActivityType:
    """A defined activity: keyword + optional limits."""

    activity_id: str
    name: str = ""
    keyword: str = ""
    min_cpu_percent: float = 0.0
    daily_max_minutes: Optional[int] = None
    warn_before_minutes: Optional[int] = None
    pause_after_minutes: Optional[int] = None
    pause_duration_minutes: Optional[int] = None
    enabled: bool = True


@dataclass
class Command:
    """A pending command pulled from the backend."""

    command_id: str
    command_type: str
    params: str = ""


@dataclass
class Identity:
    """Stable, privacy-preserving identity for this user-on-machine."""

    host_id: str
    user_id: str
    hostname: str
    system_username: str
    public_ip: str = ""
    os: str = ""  # os_key: linux | mac | windows
    version: str = ""  # agent version (compiled in)

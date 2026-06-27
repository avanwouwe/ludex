"""Core data models shared across the agent.

These are plain dataclasses with no I/O. Parsing of the free-text activity
``definition`` field lives in ``definitions.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Limits:
    """Per-activity policy. All fields optional; drives warnings only (never auto-enforced)."""

    pause_after_minutes: Optional[int] = None
    pause_duration_minutes: Optional[int] = None
    daily_max_minutes: Optional[int] = None
    warn_before_minutes: Optional[int] = None

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "Limits":
        d = d or {}
        def _int(key):
            v = d.get(key)
            return int(v) if v is not None else None
        return cls(
            pause_after_minutes=_int("pause_after_minutes"),
            pause_duration_minutes=_int("pause_duration_minutes"),
            daily_max_minutes=_int("daily_max_minutes"),
            warn_before_minutes=_int("warn_before_minutes"),
        )


@dataclass
class ActivityType:
    """A defined activity: detection rules + optional limits."""

    activity_id: str
    match_any: List[dict] = field(default_factory=list)
    min_cpu_percent: float = 0.0
    limits: Limits = field(default_factory=Limits)
    enabled: bool = True


@dataclass
class GlobalConfig:
    """Global settings fetched from the backend ``config`` tab."""

    sample_interval_s: int = 20
    sync_interval_s: int = 300
    warn_before_minutes: int = 10

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "GlobalConfig":
        d = d or {}
        def _int(key, default):
            try:
                return int(d.get(key, default))
            except (TypeError, ValueError):
                return default
        return cls(
            sample_interval_s=_int("sample_interval_s", 20),
            sync_interval_s=_int("sync_interval_s", 300),
            warn_before_minutes=_int("warn_before_minutes", 10),
        )


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

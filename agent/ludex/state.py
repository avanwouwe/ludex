"""In-memory runtime state. Nothing is persisted to disk.

Tracks, for the current local calendar day:
  * daily total seconds per activity (for daily-limit warnings),
  * the current contiguous streak per activity (for pause warnings),
  * the open logging period being accumulated between syncs.

Recovered from the backend log on startup; rebuilt the same way after any restart.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set


def _local_today() -> "datetime.date":
    return datetime.now().astimezone().date()


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


class State:
    def __init__(self):
        self.day = _local_today()
        self.daily_seconds: Dict[str, float] = {}
        self.streak_seconds: Dict[str, float] = {}
        self.prev_active: Set[str] = set()
        self.fired_warnings: Set[str] = set()  # dedup keys "kind:activity_id"
        # open period
        self.period_start: datetime = datetime.now(timezone.utc)
        self.period_seconds: float = 0.0
        self.period_activity_seconds: Dict[str, float] = {}

    # ----- day rollover -----
    def _roll_day_if_needed(self):
        today = _local_today()
        if today != self.day:
            self.day = today
            self.daily_seconds.clear()
            self.streak_seconds.clear()
            self.fired_warnings.clear()

    # ----- recovery -----
    def recover(self, periods: List[dict]):
        """Seed today's daily totals from previously-logged periods (no streaks)."""
        for p in periods:
            for a in p.get("activities", []):
                aid = a.get("activity_id")
                if aid:
                    self.daily_seconds[aid] = self.daily_seconds.get(aid, 0.0) + float(a.get("seconds", 0))

    # ----- sampling -----
    def record_sample(self, active_ids: Set[str], elapsed_s: float):
        """Attribute `elapsed_s` to active activities; reset streaks for inactive ones."""
        self._roll_day_if_needed()
        for aid in active_ids:
            self.daily_seconds[aid] = self.daily_seconds.get(aid, 0.0) + elapsed_s
            self.streak_seconds[aid] = self.streak_seconds.get(aid, 0.0) + elapsed_s
            self.period_activity_seconds[aid] = self.period_activity_seconds.get(aid, 0.0) + elapsed_s
        # anything that was active but no longer is: streak broken, clear transient warnings
        for aid in list(self.streak_seconds.keys()):
            if aid not in active_ids:
                self.streak_seconds[aid] = 0.0
                self.fired_warnings.discard(f"detected:{aid}")
                self.fired_warnings.discard(f"pause_due:{aid}")
        self.period_seconds += elapsed_s
        self.prev_active = set(active_ids)

    def newly_active(self, active_ids: Set[str]) -> Set[str]:
        return active_ids - self.prev_active

    # ----- period flush -----
    def flush_period(self) -> Optional[dict]:
        """Return a PutActivityLog payload for the open period, then start a fresh one."""
        if self.period_seconds <= 0 and not self.period_activity_seconds:
            # still advance the window so the next period starts now
            self.period_start = datetime.now(timezone.utc)
            return None
        now = datetime.now(timezone.utc)
        payload = {
            "period_start": _iso(self.period_start),
            "period_end": _iso(now),
            "period_seconds": int(round(self.period_seconds)),
            "activities": [
                {"activity_id": aid, "seconds": int(round(secs))}
                for aid, secs in self.period_activity_seconds.items()
            ],
        }
        self.period_start = now
        self.period_seconds = 0.0
        self.period_activity_seconds = {}
        return payload

    # ----- warning dedup -----
    def mark_fired(self, key: str) -> bool:
        """Return True if this is the first time `key` fires (and record it)."""
        if key in self.fired_warnings:
            return False
        self.fired_warnings.add(key)
        return True

"""Limit evaluation → warnings. Warnings only; Ludex never auto-enforces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from .models import ActivityType, GlobalConfig
from .state import State


@dataclass
class Warning:
    kind: str          # detected | pause_due | daily_warn | daily_reached | global_daily_warn | global_daily_reached
    activity_id: str
    message: str


def evaluate(state: State, activities: Dict[str, ActivityType], active_ids: Set[str],
             gconfig: Optional[GlobalConfig] = None) -> List[Warning]:
    """Produce warnings for this sample, de-duplicated via state.fired_warnings."""
    out: List[Warning] = []

    # 1. newly-detected activities
    for aid in state.newly_active(active_ids):
        a = activities.get(aid)
        label = (a.name if a and a.name else aid)
        if state.mark_fired(f"detected:{aid}"):
            out.append(Warning("detected", aid, f"Activity started: {label}"))

    for aid, a in activities.items():
        label = a.name or aid
        daily = state.daily_seconds.get(aid, 0.0)
        streak = state.streak_seconds.get(aid, 0.0)

        # 2. pause due after continuous use
        if a.pause_after_minutes and aid in active_ids:
            if streak >= a.pause_after_minutes * 60:
                if state.mark_fired(f"pause_due:{aid}"):
                    msg = f"Time for a break from {label} ({a.pause_after_minutes} min reached)"
                    if a.pause_duration_minutes:
                        msg += f" — take {a.pause_duration_minutes} min off"
                    out.append(Warning("pause_due", aid, msg))

        # 3. daily limit + pre-warning
        if a.daily_max_minutes:
            cap = a.daily_max_minutes * 60
            warn_before = (a.warn_before_minutes or 0) * 60
            if daily >= cap:
                if state.mark_fired(f"daily_reached:{aid}"):
                    out.append(Warning("daily_reached", aid,
                                       f"Daily limit reached for {label} ({a.daily_max_minutes} min)"))
            elif warn_before and daily >= cap - warn_before:
                if state.mark_fired(f"daily_warn:{aid}"):
                    remaining = int(round((cap - daily) / 60))
                    out.append(Warning("daily_warn", aid,
                                       f"{remaining} min left of {label} today"))

    # 4. global daily screen-time limit (per-person, set in the people tab)
    if gconfig and gconfig.user_daily_max_minutes:
        total_daily = sum(state.daily_seconds.values())
        cap = gconfig.user_daily_max_minutes * 60
        warn_before = (gconfig.user_warn_before_minutes or 0) * 60
        if total_daily >= cap:
            if state.mark_fired("global_daily_reached"):
                out.append(Warning("global_daily_reached", "",
                                   f"Daily screen time limit reached ({gconfig.user_daily_max_minutes} min)"))
        elif warn_before and total_daily >= cap - warn_before:
            if state.mark_fired("global_daily_warn"):
                remaining = int(round((cap - total_daily) / 60))
                out.append(Warning("global_daily_warn", "",
                                   f"{remaining} min of daily screen time left"))

    return out

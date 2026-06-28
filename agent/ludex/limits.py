"""Limit evaluation → warnings. Warnings only; Ludex never auto-enforces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

from .models import ActivityType
from .state import State


@dataclass
class Warning:
    kind: str          # detected | pause_due | daily_warn | daily_reached
    activity_id: str
    message: str


def evaluate(state: State, activities: Dict[str, ActivityType], active_ids: Set[str]) -> List[Warning]:
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
        lim = a.limits
        daily = state.daily_seconds.get(aid, 0.0)
        streak = state.streak_seconds.get(aid, 0.0)

        # 2. pause due after continuous use
        if lim.pause_after_minutes and aid in active_ids:
            if streak >= lim.pause_after_minutes * 60:
                if state.mark_fired(f"pause_due:{aid}"):
                    msg = f"Time for a break from {label} ({lim.pause_after_minutes} min reached)"
                    if lim.pause_duration_minutes:
                        msg += f" — take {lim.pause_duration_minutes} min off"
                    out.append(Warning("pause_due", aid, msg))

        # 3. daily limit + pre-warning
        if lim.daily_max_minutes:
            cap = lim.daily_max_minutes * 60
            warn_before = (lim.warn_before_minutes or 0) * 60
            if daily >= cap:
                if state.mark_fired(f"daily_reached:{aid}"):
                    out.append(Warning("daily_reached", aid,
                                        f"Daily limit reached for {label} ({lim.daily_max_minutes} min)"))
            elif warn_before and daily >= cap - warn_before:
                if state.mark_fired(f"daily_warn:{aid}"):
                    remaining = int(round((cap - daily) / 60))
                    out.append(Warning("daily_warn", aid,
                                        f"{remaining} min left of {label} today"))

    return out

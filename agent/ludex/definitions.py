"""Activity definition parsing and match semantics.

A definition is authored as YAML (and stored in the backend as compact JSON, which is
valid YAML, so the same parser handles both). See docs/activity-definitions.md.

    activity: minecraft
    match_any:
      - name_contains: java
        cmdline_contains: [net.minecraft, .minecraft]
      - exe_contains: minecraft
    min_cpu_percent: 5.0
    limits:
      daily_max_minutes: 120
"""

from __future__ import annotations

from typing import Dict, List

import yaml

from .models import ActivityType, Limits

# Operator -> process attribute it tests.
FIELD_OF = {
    "name_contains": "name",
    "exe_contains": "exe",
    "cmdline_contains": "cmdline",
}


def parse_definition(activity_id: str, text: str, enabled: bool = True) -> ActivityType:
    """Parse a free-text definition (YAML or JSON) into an ActivityType."""
    if not text or not str(text).strip():
        raise ValueError(f"empty definition for activity '{activity_id}'")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"definition for '{activity_id}' must be a mapping")

    match_any = data.get("match_any") or []
    if not isinstance(match_any, list):
        raise ValueError(f"match_any for '{activity_id}' must be a list of blocks")

    return ActivityType(
        activity_id=activity_id,
        match_any=match_any,
        min_cpu_percent=float(data.get("min_cpu_percent", 0.0) or 0.0),
        limits=Limits.from_dict(data.get("limits")),
        enabled=enabled,
    )


def _block_matches(attrs: Dict[str, str], block: dict) -> bool:
    """All operators in a block must pass (AND)."""
    for key, val in block.items():
        field = FIELD_OF.get(key)
        if not field:
            continue  # unknown operator ignored (forward-compatible)
        needles = [val] if isinstance(val, str) else list(val)
        haystack = attrs.get(field, "")
        if not all(str(n).lower() in haystack for n in needles):
            return False
    return True


def definition_matches(attrs: Dict[str, str], activity: ActivityType) -> bool:
    """Any block matching = hit (OR)."""
    return any(_block_matches(attrs, b) for b in activity.match_any)

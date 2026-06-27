"""Shared install logic used by both the CLI (`ludex install`) and the GUI installer.

Validates the backend is reachable with the given credentials, then registers the per-user
service. Raises ValueError (bad input / rejected) or transport.BackendError (unreachable).
"""

from __future__ import annotations

from .platform import get_platform
from .transport import BackendClient


def validate_and_install(url: str, token: str) -> str:
    url = (url or "").strip()
    token = (token or "").strip()
    if not url or not token:
        raise ValueError("Dashboard URL and shared key are both required.")
    if "docs.google.com/spreadsheets" in url:
        raise ValueError(
            "That looks like a Google Sheet link, not the Dashboard URL.\n"
            "You need the Web app URL (ending in /exec) from your deployment.\n"
            "In Apps Script: Deploy → Manage deployments → copy the /exec URL."
        )
    if "/exec" not in url:
        raise ValueError("That doesn't look like a Dashboard URL — it should end in /exec.")

    res = BackendClient(url, token).call_one("GetConfig", {})  # may raise BackendError
    if not res.ok:
        raise ValueError("Backend rejected the credentials: " + (res.error or "unknown error"))

    msg = get_platform().install_service(url, token)
    n = len(res.data.get("activity_types", []))
    return f"{msg}\nBackend reachable ({n} activit{'y' if n == 1 else 'ies'} defined)."

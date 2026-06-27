"""Read-only agent configuration.

The agent persists nothing to disk. Its backend URL and shared token are supplied as
read-only input (environment, typically the systemd unit's ``Environment=``). CLI flags
may override for ad-hoc runs (e.g. --detect-app).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

ENV_URL = "LUDEX_BACKEND_URL"
ENV_TOKEN = "LUDEX_TOKEN"
ENV_ADMIN = "LUDEX_ADMIN_PASSWORD"

_EXEC_URL = "https://script.google.com/macros/s/{}/exec"


def normalize_backend_url(value: str) -> str:
    """Accept either a full web-app URL or a bare Apps Script deployment ID.

    A bare ID (e.g. 'AKfycb…') is expanded to the canonical /exec URL. A value that already
    looks like a URL is returned unchanged. This lets users share the short ID instead of the
    long URL, and guarantees the /exec form (never the /dev test URL).
    """
    value = (value or "").strip()
    if not value:
        return value
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return _EXEC_URL.format(value)


@dataclass
class AgentConfig:
    backend_url: str
    token: str
    admin_password: str = ""

    @classmethod
    def load(cls, url: Optional[str] = None, token: Optional[str] = None,
             admin_password: Optional[str] = None) -> "AgentConfig":
        backend_url = normalize_backend_url(url or os.environ.get(ENV_URL, ""))
        tok = token or os.environ.get(ENV_TOKEN, "")
        admin = admin_password or os.environ.get(ENV_ADMIN, "")
        if not backend_url:
            raise SystemExit(f"missing backend URL (set {ENV_URL} or pass --url)")
        if not tok:
            raise SystemExit(f"missing shared token (set {ENV_TOKEN} or pass --token)")
        return cls(backend_url=backend_url, token=tok, admin_password=admin)

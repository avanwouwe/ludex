"""Stable, privacy-preserving identity derived on the endpoint.

host_id = sha256(machine-id)[:16]; user_id = sha256(host_id + login)[:16].
Raw machine-id and login never leave the machine.
"""

from __future__ import annotations

import getpass
import hashlib
import socket

import requests

from .models import Identity
from .platform import get_platform

_ID_LEN = 16  # hex chars


def _hash(*parts: str) -> str:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return h[:_ID_LEN]


def fetch_public_ip(timeout: float = 5.0) -> str:
    """Best-effort public IP lookup. Returns '' on failure (never raises)."""
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            r = requests.get(url, timeout=timeout)
            if r.ok:
                return r.text.strip()
        except requests.RequestException:
            continue
    return ""


def resolve_identity(include_public_ip: bool = True) -> Identity:
    machine_id = get_platform().machine_id()
    login = getpass.getuser()
    host_id = _hash(machine_id)
    user_id = _hash(host_id, login)
    return Identity(
        host_id=host_id,
        user_id=user_id,
        hostname=socket.gethostname(),
        system_username=login,
        public_ip=fetch_public_ip() if include_public_ip else "",
    )

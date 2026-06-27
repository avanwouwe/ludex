"""Batched RPC client for the Apps Script backend.

One POST carries many logical calls; the response carries the matching results in order.
See docs/protocol.md.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests


class BackendError(Exception):
    pass


class CallResult:
    def __init__(self, ok: bool, data: Any = None, error: str = ""):
        self.ok = ok
        self.data = data or {}
        self.error = error

    def __repr__(self):
        return f"CallResult(ok={self.ok}, data={self.data!r}, error={self.error!r})"


class BackendClient:
    def __init__(self, url: str, token: str, timeout: float = 30.0):
        self.url = url
        self.token = token
        self.timeout = timeout

    def call_batch(self, calls: List[Tuple[str, str, dict]]) -> Dict[str, CallResult]:
        """Send [(id, method, params), ...]; return {id: CallResult}.

        Raises BackendError on transport/envelope-level failure; per-call failures are
        returned as CallResult(ok=False) so one bad call doesn't sink the batch.
        """
        envelope = {
            "token": self.token,
            "calls": [{"id": cid, "method": method, "params": params} for cid, method, params in calls],
        }
        try:
            resp = requests.post(self.url, json=envelope, timeout=self.timeout)
        except requests.RequestException as e:
            raise BackendError(f"transport error: {e}") from e

        if not resp.ok:
            raise BackendError(f"http {resp.status_code}: {resp.text[:200]}")

        try:
            body = resp.json()
        except ValueError as e:
            raise BackendError(f"invalid JSON response: {resp.text[:200]}") from e

        if not body.get("ok"):
            raise BackendError(f"backend error: {body.get('error', 'unknown')}")

        out: Dict[str, CallResult] = {}
        for r in body.get("results", []):
            out[r.get("id")] = CallResult(ok=r.get("ok", False), data=r.get("data"), error=r.get("error", ""))
        return out

    def call_one(self, method: str, params: dict, *, cid: str = "c1") -> CallResult:
        return self.call_batch([(cid, method, params)])[cid]

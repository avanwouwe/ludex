#!/usr/bin/env python3
"""End-to-end backend integration test.

Exercises every protocol method against a *live* deployed Apps Script backend, using the
agent's own BackendClient (dogfooding the transport layer).

Run after deploying the backend (see backend/SETUP.md):

    LUDEX_BACKEND_URL="https://script.google.com/macros/s/.../exec" \
    LUDEX_TOKEN="your-shared-token" \
    LUDEX_ADMIN_PASSWORD="your-admin-password" \
    .venv/bin/python tests/integration_backend.py

It writes rows under a clearly-marked TEST user id with timestamps in the year 2000, so it
never collides with real data or with "today's" state recovery. (Apps Script can't delete
rows via this API, so the test rows remain in the sheet — safe to delete by hand.)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ludex.transport import BackendClient, BackendError  # noqa: E402

TEST_USER = "TEST-integration-user"
TEST_HOST = "TEST-integration-host"
TEST_ACTIVITY = "TEST-integration-activity"

_passed = 0
_failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}  {detail}")


def main():
    url = os.environ.get("LUDEX_BACKEND_URL")
    token = os.environ.get("LUDEX_TOKEN")
    admin = os.environ.get("LUDEX_ADMIN_PASSWORD", "")
    if not url or not token:
        sys.exit("set LUDEX_BACKEND_URL and LUDEX_TOKEN (and LUDEX_ADMIN_PASSWORD for the admin test)")

    c = BackendClient(url, token)

    print("\n== GetConfig ==")
    r = c.call_one("GetConfig", {})
    check("GetConfig ok", r.ok, r.error)
    check("GetConfig returns config dict", isinstance(r.data.get("config"), dict))
    check("GetConfig returns activity_types list", isinstance(r.data.get("activity_types"), list))

    print("\n== UpdateUser (create then update) ==")
    params = {"host_id": TEST_HOST, "user_id": TEST_USER, "hostname": "itest",
              "system_username": "itest", "public_ip": "203.0.113.1"}
    r1 = c.call_one("UpdateUser", params)
    check("UpdateUser ok", r1.ok, r1.error)
    r2 = c.call_one("UpdateUser", params)
    check("UpdateUser idempotent (created=false on 2nd)", r2.ok and r2.data.get("created") is False,
          str(r2.data))

    if admin:
        print("\n== PutActivityType (admin) ==")
        definition = '{"match_any":[{"name_contains":"itest"}],"min_cpu_percent":0,"limits":{"daily_max_minutes":60}}'
        r = c.call_one("PutActivityType", {"admin_password": admin, "activity_id": TEST_ACTIVITY,
                                           "definition": definition, "enabled": True})
        check("PutActivityType ok", r.ok, r.error)
        bad = c.call_one("PutActivityType", {"admin_password": "wrong", "activity_id": TEST_ACTIVITY,
                                             "definition": definition})
        check("PutActivityType rejects bad admin password", not bad.ok, "should have failed")
        cfg = c.call_one("GetConfig", {})
        ids = [t["activity_id"] for t in cfg.data.get("activity_types", [])]
        check("activity appears in GetConfig", TEST_ACTIVITY in ids, str(ids))
    else:
        print("\n== PutActivityType (skipped — no LUDEX_ADMIN_PASSWORD) ==")

    print("\n== PutActivityLog + overlap rejection ==")
    p1 = {"user_id": TEST_USER, "period_start": "2000-01-01T10:00:00Z",
          "period_end": "2000-01-01T10:05:00Z", "period_seconds": 300,
          "activities": [{"activity_id": TEST_ACTIVITY, "seconds": 280}]}
    r = c.call_one("PutActivityLog", p1)
    check("PutActivityLog stores first period", r.ok, r.error)
    overlap = {"user_id": TEST_USER, "period_start": "2000-01-01T10:03:00Z",
               "period_end": "2000-01-01T10:08:00Z", "period_seconds": 300, "activities": []}
    r = c.call_one("PutActivityLog", overlap)
    check("PutActivityLog REJECTS overlapping period", not r.ok and "overlap" in r.error.lower(), r.error)
    p2 = {"user_id": TEST_USER, "period_start": "2000-01-01T10:05:00Z",
          "period_end": "2000-01-01T10:10:00Z", "period_seconds": 300, "activities": []}
    r = c.call_one("PutActivityLog", p2)
    check("PutActivityLog accepts adjacent (non-overlapping) period", r.ok, r.error)

    print("\n== GetActivityLog ==")
    r = c.call_one("GetActivityLog", {"user_id": TEST_USER, "since": "2000-01-01T00:00:00Z"})
    check("GetActivityLog ok", r.ok, r.error)
    periods = r.data.get("periods", [])
    check("GetActivityLog returns >=2 periods", len(periods) >= 2, f"got {len(periods)}")

    print("\n== GetCommands ==")
    r = c.call_one("GetCommands", {"user_id": TEST_USER})
    check("GetCommands ok", r.ok, r.error)
    check("GetCommands returns list", isinstance(r.data.get("commands"), list))

    print("\n== Batch ordering (multiple calls, one POST) ==")
    try:
        results = c.call_batch([
            ("a", "GetConfig", {}),
            ("b", "GetCommands", {"user_id": TEST_USER}),
            ("c", "UpdateUser", params),
        ])
        check("batch returns all ids", {"a", "b", "c"} <= set(results.keys()), str(list(results)))
        check("batch results independent ok flags", all(results[k].ok for k in ("a", "b", "c")))
    except BackendError as e:
        check("batch call", False, str(e))

    print("\n== Unknown method handling ==")
    r = c.call_one("NoSuchMethod", {})
    check("unknown method returns ok=false (not a crash)", not r.ok and "unknown method" in r.error.lower(), r.error)

    print(f"\n=== {_passed} passed, {_failed} failed ===")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()

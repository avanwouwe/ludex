"""The agent run loop: bootstrap, sample, sync."""

from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone
from typing import Dict, List

from .commands import CommandContext, execute
from .config import AgentConfig
from .definitions import parse_definition
from .identity import resolve_identity
from .limits import evaluate
from .models import ActivityType, Command, GlobalConfig, Identity
from .platform import get_platform
from .state import State
from .transport import BackendClient, BackendError

log = logging.getLogger("ludex.daemon")

CPU_INTERVAL = 1.0  # seconds of CPU sampling window inside each detect()


def _local_midnight_utc_iso() -> str:
    now_local = datetime.now().astimezone()
    midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_types(activity_types: List[dict], os_key: str) -> Dict[str, ActivityType]:
    out: Dict[str, ActivityType] = {}
    for t in activity_types:
        aid = t.get("activity_id")
        if not aid:
            continue
        try:
            out[aid] = parse_definition(aid, t.get("definition", ""),
                                        enabled=t.get("enabled", True), os_key=os_key)
        except Exception as e:
            log.warning("skipping activity '%s': %s", aid, e)
    return out


class Daemon:
    def __init__(self, config: AgentConfig, sample_interval=None, sync_interval=None, max_cycles=None):
        self.config = config
        self.client = BackendClient(config.backend_url, config.token)
        self.platform = get_platform()
        self.state = State()
        self.gconfig = GlobalConfig()
        self.activities: Dict[str, ActivityType] = {}
        self.identity: Identity = None  # type: ignore
        self._stop = False
        self._reload_requested = False
        self._last_tick = None  # monotonic time of the previous sample, for time attribution
        # test/override knobs (None = use backend-provided config)
        self._override_sample = sample_interval
        self._override_sync = sync_interval
        self.max_cycles = max_cycles

    def _apply_overrides(self):
        if self._override_sample is not None:
            self.gconfig.sample_interval_s = self._override_sample
        if self._override_sync is not None:
            self.gconfig.sync_interval_s = self._override_sync

    # ----- lifecycle -----
    def request_reload(self):
        self._reload_requested = True

    def _install_signals(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, lambda *_: setattr(self, "_stop", True))
            except ValueError:
                pass  # not in main thread

    def bootstrap(self):
        self.identity = resolve_identity()
        log.info("identity: user_id=%s host=%s", self.identity.user_id, self.identity.hostname)

        cfg = self.client.call_one("GetConfig", {})
        if cfg.ok:
            self.gconfig = GlobalConfig.from_dict(cfg.data.get("config"))
            self.activities = _parse_types(cfg.data.get("activity_types", []), self.platform.os_key)
        else:
            log.error("GetConfig failed: %s", cfg.error)
        self._apply_overrides()
        log.info("loaded %d activity types; sample=%ss sync=%ss",
                 len(self.activities), self.gconfig.sample_interval_s, self.gconfig.sync_interval_s)

        self.client.call_one("UpdateUser", {
            "host_id": self.identity.host_id,
            "user_id": self.identity.user_id,
            "hostname": self.identity.hostname,
            "system_username": self.identity.system_username,
            "public_ip": self.identity.public_ip,
            "os": self.identity.os,
            "version": self.identity.version,
        })

        rec = self.client.call_one("GetActivityLog", {
            "user_id": self.identity.user_id,
            "since": _local_midnight_utc_iso(),
        })
        if rec.ok:
            periods = rec.data.get("periods", [])
            self.state.recover(periods)
            log.info("recovered %d prior periods for today", len(periods))

    # ----- main loop -----
    def run(self):
        self._install_signals()
        self.bootstrap()

        last_sample = time.monotonic()
        last_sync = time.monotonic()
        cycle = 0
        # account for the very first detect's own sleep against the period start
        while not self._stop:
            cycle += 1
            self._sample()
            now = time.monotonic()
            # in cycle-limited (test) mode, sync every cycle so a short run still exercises sync
            if (self.max_cycles is not None or now - last_sync >= self.gconfig.sync_interval_s
                    or self._reload_requested):
                self._sync()
                last_sync = time.monotonic()

            if self.max_cycles is not None and cycle >= self.max_cycles:
                break

            # sleep the remainder of the sample interval (detect already slept CPU_INTERVAL)
            elapsed = time.monotonic() - last_sample
            remaining = max(0.0, self.gconfig.sample_interval_s - elapsed)
            last_sample = time.monotonic()
            self._interruptible_sleep(remaining)

        log.info("stopping; flushing final period")
        self._sync()

    def _interruptible_sleep(self, seconds: float):
        end = time.monotonic() + seconds
        while not self._stop and time.monotonic() < end:
            time.sleep(min(1.0, end - time.monotonic()))

    # ----- sample tick -----
    def _sample(self):
        from .detection import detect  # imported here so --detect-app paths don't require a loop
        hits = detect(list(self.activities.values()), cpu_interval=CPU_INTERVAL)
        active_ids = set(hits.keys())

        # Attribute the wall time since the PREVIOUS sample to whatever is active now — that is the
        # interval this sample represents (~sample_interval), not just the ~1s detection window.
        # Cap it so a long gap (suspend/sleep, a stalled loop) can't over-count: time.monotonic()
        # already pauses during system sleep on macOS/Linux, and the cap is a belt-and-braces guard.
        now = time.monotonic()
        if self._last_tick is None:
            elapsed = 0.0
        else:
            elapsed = min(now - self._last_tick, self.gconfig.sample_interval_s * 2)
        self._last_tick = now

        warnings = evaluate(self.state, self.activities, active_ids)
        self.state.record_sample(active_ids, elapsed)
        for w in warnings:
            log.info("warn[%s] %s", w.kind, w.message)
            try:
                self.platform.notify("Ludex", w.message)
            except Exception as e:
                log.warning("notify failed: %s", e)

    # ----- sync tick -----
    def _sync(self):
        calls = []
        payload = self.state.flush_period()
        if payload:
            payload["user_id"] = self.identity.user_id
            calls.append(("log", "PutActivityLog", payload))
        calls.append(("cmds", "GetCommands", {"user_id": self.identity.user_id}))
        calls.append(("cfg", "GetConfig", {}))

        try:
            results = self.client.call_batch(calls)
        except BackendError as e:
            log.warning("sync failed (will retry next interval): %s", e)
            return

        if "log" in results and not results["log"].ok:
            log.warning("PutActivityLog rejected: %s", results["log"].error)

        cfg = results.get("cfg")
        if cfg and cfg.ok:
            self.gconfig = GlobalConfig.from_dict(cfg.data.get("config"))
            self.activities = _parse_types(cfg.data.get("activity_types", []), self.platform.os_key)
            self._apply_overrides()
        self._reload_requested = False

        cmds_res = results.get("cmds")
        if cmds_res and cmds_res.ok:
            self._run_commands([Command(c["command_id"], c["command_type"], c.get("params", ""))
                                for c in cmds_res.data.get("commands", [])])

    def _run_commands(self, commands: List[Command]):
        if not commands:
            return
        ctx = CommandContext(self.activities, self.request_reload)
        acks = []
        for cmd in commands:
            status, result = execute(cmd, ctx)
            log.info("command %s (%s) -> %s: %s", cmd.command_id, cmd.command_type, status, result)
            acks.append((f"ack-{cmd.command_id}", "UpdateCommand",
                         {"command_id": cmd.command_id, "status": status, "result": result}))
        try:
            self.client.call_batch(acks)
        except BackendError as e:
            log.warning("failed to ack commands: %s", e)

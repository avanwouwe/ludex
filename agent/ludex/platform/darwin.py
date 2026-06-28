"""macOS platform implementation."""

from __future__ import annotations

import plistlib
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

# The entire .app bundle is installed here; launchd points at the binary inside it.
_APP_INSTALL_PATH = Path.home() / "Applications" / "Ludex.app"
_APP_BINARY = _APP_INSTALL_PATH / "Contents" / "MacOS" / "Ludex"

from .base import Platform

_LABEL = "com.ludex.agent"
_UUID_RE = re.compile(r'"IOPlatformUUID"\s*=\s*"([^"]+)"')


class DarwinPlatform(Platform):
    name = "darwin"
    os_key = "mac"

    def __init__(self):
        self._pending = []  # detached osascript dialog processes, reaped lazily

    def machine_id(self) -> str:
        try:
            out = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, check=True,
            ).stdout
            m = _UUID_RE.search(out)
            if m:
                return m.group(1)
        except (OSError, subprocess.CalledProcessError):
            pass
        import os
        return os.uname().nodename

    def notify(self, title: str, message: str) -> None:
        # A modal alert (not a Notification Center banner): it isn't subject to Do Not Disturb /
        # macOS Game Mode notification-silencing, grabs focus, and so surfaces over a full-screen
        # game. (A game using exclusive-fullscreen display capture can still hide it until the
        # user switches out — that's inherent; the parent's stop-activity command is the hard lever.)
        # We present it via System Events (always running, can show UI from a background agent),
        # spawn it detached so the agent loop never blocks waiting for a click, and `giving up
        # after` so a stale dialog self-dismisses.
        self._pending = [p for p in self._pending if p.poll() is None]  # reap finished dialogs
        msg = message.replace("\\", "\\\\").replace('"', '\\"')
        ttl = title.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            f'tell application "System Events" to display dialog "{msg}" '
            f'with title "{ttl}" buttons {{"OK"}} default button "OK" '
            f"with icon caution giving up after 120"
        )
        p = subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        self._pending.append(p)

    def shutdown(self) -> str:
        # As a normal user, ask System Events to shut down (the GUI path). `shutdown -h`
        # would need sudo. Surface failure rather than pretend.
        proc = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to shut down'],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            return "shutdown requested via System Events"
        raise RuntimeError(f"shutdown failed: {(proc.stderr or proc.stdout).strip()}")

    def _install_binary(self) -> Path:
        """Copy Ludex.app to ~/Applications; return the executable path inside for launchd."""
        if not getattr(sys, "frozen", False):
            return Path(sys.executable)  # dev mode — don't copy
        # sys.executable = .../Ludex.app/Contents/MacOS/Ludex — three levels up is the bundle.
        src_bundle = Path(sys.executable).resolve().parent.parent.parent
        dst_bundle = _APP_INSTALL_PATH
        if src_bundle.resolve() != dst_bundle.resolve():
            if dst_bundle.exists():
                shutil.rmtree(dst_bundle)
            dst_bundle.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src_bundle, dst_bundle)
            # Remove the source bundle after a short delay so Spotlight doesn't index two
            # copies. Safe on macOS: the running process keeps its file descriptors open
            # even after the directory is deleted from disk.
            subprocess.Popen(
                ["sh", "-c", f"sleep 3 && rm -rf {shlex.quote(str(src_bundle))}"],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return _APP_BINARY

    def _program_args(self, binary: Path) -> list:
        if getattr(sys, "frozen", False):
            return [str(binary), "run"]
        return [sys.executable, "-m", "ludex", "run"]

    def _plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{_LABEL}.plist"

    def install_service(self, backend_url: str, token: str) -> str:
        binary = self._install_binary()
        path = self._plist_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        plist = {
            "Label": _LABEL,
            "ProgramArguments": self._program_args(binary),
            "EnvironmentVariables": {
                "LUDEX_BACKEND_URL": backend_url,
                "LUDEX_TOKEN": token,
            },
            "RunAtLoad": True,
            "KeepAlive": True,
            "ProcessType": "Background",
        }
        with open(path, "wb") as f:
            plistlib.dump(plist, f)
        # reload if already loaded, then load
        subprocess.run(["launchctl", "unload", str(path)], check=False,
                       capture_output=True)
        subprocess.run(["launchctl", "load", "-w", str(path)], check=False)
        return f"installed binary at {binary}, LaunchAgent at {path}"

    def installed_config(self) -> dict | None:
        path = self._plist_path()
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                data = plistlib.load(f)
            env = data.get("EnvironmentVariables", {})
            url = env.get("LUDEX_BACKEND_URL", "")
            token = env.get("LUDEX_TOKEN", "")
            if url and token:
                return {"backend_url": url, "token": token}
        except Exception:
            pass
        return None

    def uninstall_service(self) -> str:
        path = self._plist_path()
        subprocess.run(["launchctl", "unload", "-w", str(path)], check=False,
                       capture_output=True)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        if _APP_INSTALL_PATH.exists():
            shutil.rmtree(_APP_INSTALL_PATH)
        return f"removed LaunchAgent {path} and {_APP_INSTALL_PATH}"

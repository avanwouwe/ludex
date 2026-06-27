"""macOS platform implementation."""

from __future__ import annotations

import plistlib
import re
import subprocess
import sys
from pathlib import Path

from .base import Platform

_LABEL = "com.ludex.agent"
_UUID_RE = re.compile(r'"IOPlatformUUID"\s*=\s*"([^"]+)"')


class DarwinPlatform(Platform):
    name = "darwin"

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
        # Escape double quotes for the AppleScript string literals.
        msg = message.replace('"', '\\"')
        ttl = title.replace('"', '\\"')
        script = f'display notification "{msg}" with title "{ttl}"'
        subprocess.run(["osascript", "-e", script], check=False)

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

    def _program_args(self) -> list:
        if getattr(sys, "frozen", False):  # PyInstaller binary
            return [sys.executable, "run"]
        return [sys.executable, "-m", "ludex", "run"]

    def _plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{_LABEL}.plist"

    def install_service(self, backend_url: str, token: str) -> str:
        path = self._plist_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        plist = {
            "Label": _LABEL,
            "ProgramArguments": self._program_args(),
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
        return f"installed LaunchAgent at {path}"

    def uninstall_service(self) -> str:
        path = self._plist_path()
        subprocess.run(["launchctl", "unload", "-w", str(path)], check=False,
                       capture_output=True)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return f"removed LaunchAgent {path}"

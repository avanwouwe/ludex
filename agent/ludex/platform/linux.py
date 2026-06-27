"""Linux platform implementation."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .base import Platform

_MACHINE_ID_PATHS = ("/etc/machine-id", "/var/lib/dbus/machine-id")
_SERVICE_NAME = "ludex.service"


class LinuxPlatform(Platform):
    name = "linux"

    def machine_id(self) -> str:
        for path in _MACHINE_ID_PATHS:
            try:
                val = Path(path).read_text().strip()
                if val:
                    return val
            except OSError:
                continue
        # fallback: hostname-based (less stable, but keeps the agent functional)
        return os.uname().nodename

    def notify(self, title: str, message: str) -> None:
        notify = shutil.which("notify-send")
        if not notify:
            # No GUI notifier available; fall back to stderr so it's at least visible.
            print(f"[notify] {title}: {message}", file=sys.stderr)
            return
        subprocess.run([notify, "--app-name=Ludex", title, message], check=False)

    def shutdown(self) -> str:
        # Try the systemd path first, then classic shutdown. As a non-admin user this may be
        # blocked by polkit — we surface the error rather than pretend it worked.
        attempts = [["systemctl", "poweroff"], ["shutdown", "-h", "now"]]
        last_err = ""
        for cmd in attempts:
            if not shutil.which(cmd[0]):
                continue
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                return f"shutdown initiated via '{' '.join(cmd)}'"
            last_err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"shutdown failed (no privilege?): {last_err or 'no usable command found'}")

    def _exec_command(self) -> str:
        """How to invoke the agent's run loop, for the systemd unit ExecStart."""
        if getattr(sys, "frozen", False):  # PyInstaller binary
            return f"{sys.executable} run"
        return f"{sys.executable} -m ludex run"

    def _unit_path(self) -> Path:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        return base / "systemd" / "user" / _SERVICE_NAME

    def install_service(self, backend_url: str, token: str) -> str:
        unit = self._unit_path()
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text(
            "[Unit]\n"
            "Description=Ludex activity agent\n"
            "After=network-online.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f'Environment="LUDEX_BACKEND_URL={backend_url}"\n'
            f'Environment="LUDEX_TOKEN={token}"\n'
            f"ExecStart={self._exec_command()}\n"
            "Restart=on-failure\n"
            "RestartSec=10\n\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        )
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "--user", "enable", "--now", _SERVICE_NAME], check=False)
        # Optional: keep running after logout. Needs privileges; ignore failure.
        subprocess.run(["loginctl", "enable-linger", os.environ.get("USER", "")], check=False)
        return f"installed systemd user service at {unit}"

    def uninstall_service(self) -> str:
        subprocess.run(["systemctl", "--user", "disable", "--now", _SERVICE_NAME], check=False)
        unit = self._unit_path()
        try:
            unit.unlink()
        except FileNotFoundError:
            pass
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        return f"removed systemd user service {unit}"

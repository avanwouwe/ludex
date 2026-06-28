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
_INSTALL_PATH = Path.home() / ".local" / "bin" / "ludex"


class LinuxPlatform(Platform):
    name = "linux"
    os_key = "linux"

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

    def _install_binary(self) -> Path:
        """Copy the frozen binary to a stable location; return the path to use in the service."""
        if not getattr(sys, "frozen", False):
            return Path(sys.executable)  # dev mode — don't copy
        src = Path(sys.executable).resolve()
        target = _INSTALL_PATH
        if src != target.resolve() if target.exists() else src != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            target.chmod(target.stat().st_mode | 0o755)
        return target

    def _exec_command(self, binary: Path) -> str:
        """How to invoke the agent's run loop, for the systemd unit ExecStart."""
        if getattr(sys, "frozen", False):
            return f"{binary} run"
        return f"{sys.executable} -m ludex run"

    def _unit_path(self) -> Path:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        return base / "systemd" / "user" / _SERVICE_NAME

    def install_service(self, backend_url: str, token: str) -> str:
        binary = self._install_binary()
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
            f"ExecStart={self._exec_command(binary)}\n"
            "Restart=on-failure\n"
            "RestartSec=10\n\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        )
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "--user", "enable", _SERVICE_NAME], check=False)
        # restart (not just enable --now): on a re-install this picks up a changed URL/token,
        # since a still-running unit would otherwise keep the old Environment values.
        subprocess.run(["systemctl", "--user", "restart", _SERVICE_NAME], check=False)
        # Optional: keep running after logout. Needs privileges; ignore failure.
        subprocess.run(["loginctl", "enable-linger", os.environ.get("USER", "")], check=False)
        return f"installed binary at {binary}, systemd user service at {unit}"

    def installed_config(self) -> dict | None:
        path = self._unit_path()
        if not path.exists():
            return None
        try:
            url, token = "", ""
            for line in path.read_text().splitlines():
                if line.startswith('Environment="LUDEX_BACKEND_URL='):
                    url = line.split("=", 2)[2].rstrip('"')
                elif line.startswith('Environment="LUDEX_TOKEN='):
                    token = line.split("=", 2)[2].rstrip('"')
            if url and token:
                return {"backend_url": url, "token": token}
        except Exception:
            pass
        return None

    def uninstall_service(self) -> str:
        subprocess.run(["systemctl", "--user", "disable", "--now", _SERVICE_NAME], check=False)
        unit = self._unit_path()
        try:
            unit.unlink()
        except FileNotFoundError:
            pass
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        try:
            _INSTALL_PATH.unlink()
        except FileNotFoundError:
            pass
        return f"removed systemd user service {unit} and binary {_INSTALL_PATH}"

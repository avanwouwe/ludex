"""Windows platform implementation."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .base import Platform

_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Ludex"
_INSTALL_PATH = _INSTALL_DIR / "ludex.exe"
_TASK_NAME = "LudexAgent"


class WindowsPlatform(Platform):
    name = "windows"
    os_key = "windows"

    def machine_id(self) -> str:
        try:
            out = subprocess.run(
                ["wmic", "csproduct", "get", "UUID"],
                capture_output=True, text=True, check=True,
            ).stdout
            lines = [l.strip() for l in out.splitlines() if l.strip() and l.strip() != "UUID"]
            if lines:
                return lines[0]
        except (OSError, subprocess.CalledProcessError):
            pass
        return os.environ.get("COMPUTERNAME", "unknown")

    def notify(self, title: str, message: str) -> None:
        # Toast notification via PowerShell (works without admin).
        script = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null; "
            "$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
            "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
            f'$template.SelectSingleNode("//text[@id=1]").InnerText = "{title}"; '
            f'$template.SelectSingleNode("//text[@id=2]").InnerText = "{message}"; '
            "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Ludex').Show($toast)"
        )
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def shutdown(self) -> str:
        proc = subprocess.run(["shutdown", "/s", "/t", "0"], capture_output=True, text=True)
        if proc.returncode == 0:
            return "shutdown initiated"
        raise RuntimeError(f"shutdown failed: {(proc.stderr or proc.stdout).strip()}")

    def _install_binary(self) -> Path:
        """Copy the frozen binary to a stable location; return the path to use in the service."""
        if not getattr(sys, "frozen", False):
            return Path(sys.executable)  # dev mode — don't copy
        src = Path(sys.executable).resolve()
        target = _INSTALL_PATH
        # On Windows we can't overwrite a running exe; write to a temp name then rename.
        if src != target.resolve() if target.exists() else src != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            shutil.copy2(src, tmp)
            if target.exists():
                target.unlink()
            tmp.rename(target)
        return target

    def install_service(self, backend_url: str, token: str) -> str:
        binary = self._install_binary()
        # Task Scheduler has no native env var injection, so we write a small wrapper
        # script that sets the credentials before calling the binary.
        wrapper = _INSTALL_DIR / "run.cmd"
        wrapper.write_text(
            "@echo off\r\n"
            f"set LUDEX_BACKEND_URL={backend_url}\r\n"
            f"set LUDEX_TOKEN={token}\r\n"
            f'"{binary}" run\r\n',
            encoding="utf-8",
        )
        # Register as a Task Scheduler task that runs at logon for the current user.
        # /F overwrites an existing task with the same name (re-install).
        subprocess.run([
            "schtasks", "/Create", "/F",
            "/TN", _TASK_NAME,
            "/TR", f'cmd /c "{wrapper}"',
            "/SC", "ONLOGON",
            "/RU", os.environ.get("USERNAME", ""),
            "/RL", "LIMITED",
        ], check=False)
        return f"installed binary at {binary}, Task Scheduler task '{_TASK_NAME}'"

    def uninstall_service(self) -> str:
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", _TASK_NAME], check=False)
        try:
            shutil.rmtree(_INSTALL_DIR)
        except FileNotFoundError:
            pass
        return f"removed Task Scheduler task '{_TASK_NAME}' and {_INSTALL_DIR}"

"""Platform interface. Keep this surface small — everything else is cross-platform."""

from __future__ import annotations

import abc


class Platform(abc.ABC):
    name: str = "base"
    # OS key reported to the backend as the user's OS: "linux" | "mac" | "windows".
    os_key: str = "unknown"

    @abc.abstractmethod
    def machine_id(self) -> str:
        """A stable machine identifier (raw; callers hash it before it leaves the host)."""

    @abc.abstractmethod
    def notify(self, title: str, message: str) -> None:
        """Show a desktop notification to the logged-in user."""

    @abc.abstractmethod
    def shutdown(self) -> str:
        """Attempt to shut the computer down. Returns a human-readable result.

        Raises on failure (e.g. insufficient privileges) so the caller can report 'failed'.
        """

    @abc.abstractmethod
    def install_service(self, backend_url: str, token: str) -> str:
        """Register the agent to run as the logged-in user, surviving logout/reboot."""

    @abc.abstractmethod
    def uninstall_service(self) -> str:
        """Remove the service registration."""

    def installed_config(self) -> "dict | None":
        """Return {backend_url, token} if the service is installed, else None."""
        return None

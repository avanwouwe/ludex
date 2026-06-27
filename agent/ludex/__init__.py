"""Ludex endpoint agent.

Detects defined activities, logs time to the backend, fetches config and commands,
runs those commands, and shows local warnings. The agent persists nothing to disk:
all runtime state lives in memory and is recovered from the backend log on startup.
"""

__version__ = "0.1.2"

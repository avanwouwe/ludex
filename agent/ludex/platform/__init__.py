"""Platform abstraction. Linux is implemented; macOS/Windows raise until added."""

from __future__ import annotations

import sys
from functools import lru_cache

from .base import Platform


@lru_cache(maxsize=1)
def get_platform() -> Platform:
    if sys.platform.startswith("linux"):
        from .linux import LinuxPlatform
        return LinuxPlatform()
    if sys.platform == "darwin":
        from .darwin import DarwinPlatform
        return DarwinPlatform()
    if sys.platform.startswith("win"):
        raise NotImplementedError("Windows support is not implemented yet")
    raise NotImplementedError(f"unsupported platform: {sys.platform}")

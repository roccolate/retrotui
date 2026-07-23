"""Render invalidation levels returned by runtime services."""

from enum import IntEnum


class RenderUpdate(IntEnum):
    """Describe how much of the curses surface changed."""

    NONE = 0
    OVERLAY = 1
    FULL = 2

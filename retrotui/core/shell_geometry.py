"""Shared geometry for the desktop workspace and classic shell bar."""

from ..constants import BOTTOM_BARS_HEIGHT, MENU_BAR_HEIGHT


def global_bar_row(screen_h):
    """Return the terminal row occupied by the global shell bar."""
    height = max(0, int(screen_h))
    if height <= 0:
        return 0
    if BOTTOM_BARS_HEIGHT:
        return max(0, height - int(BOTTOM_BARS_HEIGHT))
    return 0


def workspace_top_row():
    """Return the first row available to desktop content and windows."""
    return max(0, int(MENU_BAR_HEIGHT))


def workspace_bottom_exclusive(screen_h):
    """Return the first row reserved below the desktop workspace."""
    height = max(0, int(screen_h))
    bottom = max(0, height - max(0, int(BOTTOM_BARS_HEIGHT)))
    return max(workspace_top_row(), bottom)


def workspace_height(screen_h):
    """Return the number of rows available to windows and desktop content."""
    return max(0, workspace_bottom_exclusive(screen_h) - workspace_top_row())

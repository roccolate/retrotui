"""Theme definitions and lookup helpers for RetroTUI."""

from dataclasses import dataclass
import curses
from typing import Optional

from .constants import (
    C_BUTTON,
    C_BUTTON_SEL,
    C_DESKTOP,
    C_DIALOG,
    C_FM_DIR,
    C_FM_SELECTED,
    C_ICON,
    C_ICON_SEL,
    C_MENUBAR,
    C_MENU_ITEM,
    C_MENU_SEL,
    C_SCROLLBAR,
    C_STATUS,
    C_TASKBAR,
    C_WIN_BODY,
    C_WIN_BORDER,
    C_WIN_INACTIVE,
    C_WIN_TITLE,
    C_WIN_TITLE_INV,
)

import sys

# Test doubles may expose only a subset of color constants.
for _name, _fallback in {
    "COLOR_BLACK": 0,
    "COLOR_BLUE": 4,
    "COLOR_CYAN": 6,
    "COLOR_GREEN": 2,
    "COLOR_WHITE": 7,
    "COLOR_YELLOW": 3,
}.items():
    if not hasattr(curses, _name):
        setattr(curses, _name, _fallback)

# Fix for Windows PowerShell rendering black as light gray
WIN_BLACK = curses.COLOR_BLACK
if sys.platform == 'win32':
    WIN_BLACK = 0  # Sometimes explicit 0 works better than curses.COLOR_BLACK, or we can just use another contrasting color like White. Let's stick to explicit 0. 

DEFAULT_THEME = "win31"

ROLE_TO_PAIR_ID = {
    "desktop": C_DESKTOP,
    "menubar": C_MENUBAR,
    "menu_item": C_MENU_ITEM,
    "menu_selected": C_MENU_SEL,
    "window_border": C_WIN_BORDER,
    "window_title": C_WIN_TITLE,
    "window_title_invert": C_WIN_TITLE_INV,
    "window_body": C_WIN_BODY,
    "button": C_BUTTON,
    "button_selected": C_BUTTON_SEL,
    "dialog": C_DIALOG,
    "status": C_STATUS,
    "icon": C_ICON,
    "icon_selected": C_ICON_SEL,
    "scrollbar": C_SCROLLBAR,
    "window_inactive": C_WIN_INACTIVE,
    "file_selected": C_FM_SELECTED,
    "file_directory": C_FM_DIR,
    "taskbar": C_TASKBAR,
}


def _mk_pairs(fg_bg):
    return {
        "desktop": fg_bg[0],
        "menubar": fg_bg[1],
        "menu_item": fg_bg[1],
        "menu_selected": fg_bg[2],
        "window_border": fg_bg[3],
        "window_title": fg_bg[4],
        "window_title_invert": fg_bg[5],
        "window_body": fg_bg[6],
        "button": fg_bg[6],
        "button_selected": fg_bg[7],
        "dialog": fg_bg[6],
        "status": fg_bg[8],
        "icon": fg_bg[0],
        "icon_selected": fg_bg[2],
        "scrollbar": fg_bg[6],
        "window_inactive": fg_bg[9],
        "file_selected": fg_bg[2],
        "file_directory": fg_bg[10],
        "taskbar": fg_bg[1],
    }


@dataclass(frozen=True)
class Theme:
    """RetroTUI semantic theme definition."""

    key: str
    label: str
    desktop_pattern: str
    pairs_base: dict[str, tuple[int, int]]
    pairs_256: Optional[dict[str, tuple[int, int]]] = None
    custom_colors: Optional[dict[int, tuple[int, int, int]]] = None


THEMES = {
    "win31": Theme(
        key="win31",
        label="Windows 3.1",
        desktop_pattern=" ",
        pairs_base=_mk_pairs(
            (
                (WIN_BLACK, curses.COLOR_CYAN),
                (WIN_BLACK, curses.COLOR_WHITE),
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_BLUE, curses.COLOR_WHITE),
                (WIN_BLACK, curses.COLOR_WHITE),
                (curses.COLOR_WHITE, WIN_BLACK),
                (WIN_BLACK, curses.COLOR_CYAN),
                (WIN_BLACK, curses.COLOR_WHITE),
                (curses.COLOR_BLUE, curses.COLOR_WHITE),
            )
        ),
        pairs_256=_mk_pairs(
            (
                (WIN_BLACK, 20),
                (WIN_BLACK, curses.COLOR_WHITE),
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_WHITE, 21),
                (21, curses.COLOR_WHITE),
                (WIN_BLACK, curses.COLOR_WHITE),
                (curses.COLOR_WHITE, WIN_BLACK),
                (WIN_BLACK, curses.COLOR_CYAN),
                (curses.COLOR_WHITE, 23),
                (curses.COLOR_BLUE, curses.COLOR_WHITE),
            )
        ),
        custom_colors={
            20: (0, 500, 500),      # desktop teal
            21: (0, 0, 500),        # title blue
            22: (800, 800, 800),    # light gray (reserved for future)
            23: (600, 600, 600),    # inactive gray
        },
    ),
    "dos_cga": Theme(
        key="dos_cga",
        label="DOS / CGA",
        desktop_pattern="▒",
        pairs_base=_mk_pairs(
            (
                (curses.COLOR_YELLOW, curses.COLOR_BLUE),
                (curses.COLOR_BLACK, curses.COLOR_CYAN),
                (curses.COLOR_BLACK, curses.COLOR_YELLOW),
                (curses.COLOR_YELLOW, curses.COLOR_BLUE),
                (curses.COLOR_YELLOW, curses.COLOR_BLUE),
                (curses.COLOR_BLUE, curses.COLOR_YELLOW),
                (curses.COLOR_YELLOW, curses.COLOR_BLUE),
                (curses.COLOR_BLUE, curses.COLOR_YELLOW),
                (curses.COLOR_BLACK, curses.COLOR_CYAN),
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_CYAN, curses.COLOR_BLUE),
            )
        ),
    ),
    "win95": Theme(
        key="win95",
        label="Windows 95",
        desktop_pattern="·",
        pairs_base=_mk_pairs(
            (
                (curses.COLOR_BLUE, curses.COLOR_CYAN),
                (curses.COLOR_BLACK, curses.COLOR_WHITE),
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_BLACK, curses.COLOR_WHITE),
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_BLUE, curses.COLOR_WHITE),
                (curses.COLOR_BLACK, curses.COLOR_WHITE),
                (curses.COLOR_WHITE, curses.COLOR_BLACK),
                (curses.COLOR_BLACK, curses.COLOR_CYAN),
                (curses.COLOR_BLACK, curses.COLOR_WHITE),
                (curses.COLOR_BLUE, curses.COLOR_WHITE),
            )
        ),
    ),
    "hacker": Theme(
        key="hacker",
        label="Hacker",
        desktop_pattern="▓",
        pairs_base=_mk_pairs(
            (
                (curses.COLOR_GREEN, curses.COLOR_BLACK),
                (curses.COLOR_GREEN, curses.COLOR_BLACK),
                (curses.COLOR_BLACK, curses.COLOR_GREEN),
                (curses.COLOR_GREEN, curses.COLOR_BLACK),
                (curses.COLOR_GREEN, curses.COLOR_BLACK),
                (curses.COLOR_BLACK, curses.COLOR_GREEN),
                (curses.COLOR_GREEN, curses.COLOR_BLACK),
                (curses.COLOR_BLACK, curses.COLOR_GREEN),
                (curses.COLOR_GREEN, curses.COLOR_BLACK),
                (curses.COLOR_GREEN, curses.COLOR_BLACK),
                (curses.COLOR_GREEN, curses.COLOR_BLACK),
            )
        ),
    ),
    "amiga": Theme(
        key="amiga",
        label="Amiga Workbench",
        desktop_pattern="▒",
        pairs_base=_mk_pairs(
            (
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_BLACK, curses.COLOR_CYAN),
                (curses.COLOR_BLACK, curses.COLOR_YELLOW),
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_YELLOW, curses.COLOR_BLUE),
                (curses.COLOR_BLUE, curses.COLOR_YELLOW),
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_BLUE, curses.COLOR_WHITE),
                (curses.COLOR_BLACK, curses.COLOR_CYAN),
                (curses.COLOR_CYAN, curses.COLOR_BLUE),
                (curses.COLOR_CYAN, curses.COLOR_BLUE),
            )
        ),
    ),
}


def list_themes():
    """Return themes in deterministic UI order."""
    order = ("win31", "dos_cga", "win95", "hacker", "amiga")
    return [THEMES[key] for key in order]


def get_theme(theme_key: Optional[str]) -> Theme:
    """Resolve theme by key with fallback to default."""
    if not theme_key:
        return THEMES[DEFAULT_THEME]
    return THEMES.get(theme_key, THEMES[DEFAULT_THEME])

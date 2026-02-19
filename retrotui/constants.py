"""Constants and configuration for RetroTUI."""

import curses

from .core.actions import AppAction

# Box drawing characters (Unicode).
BOX_TL = "\u2554"
BOX_TR = "\u2557"
BOX_BL = "\u255a"
BOX_BR = "\u255d"
BOX_H = "\u2550"
BOX_V = "\u2551"

# Single-line box characters.
SB_TL = "\u250c"
SB_TR = "\u2510"
SB_BL = "\u2514"
SB_BR = "\u2518"
SB_H = "\u2500"
SB_V = "\u2502"

# Desktop pattern fallback.
DESKTOP_PATTERN = " "

# Desktop icons (Unicode).
ICONS = [
    {
        "label": "Files",
        "action": AppAction.FILE_MANAGER,
        "art": ["\u250c\u2500\u2500\u2510", "\u2502\u2592\u2592\u2502", "\u2514\u2500\u2500\u2518"],
    },
    {
        "label": "Notepad",
        "action": AppAction.NOTEPAD,
        "art": ["\u2554\u2550\u2550\u2557", "\u2551\u2261\u2261\u2551", "\u255a\u2550\u2550\u255d"],
    },
    {
        "label": "ASCII Vid",
        "action": AppAction.ASCII_VIDEO,
        "art": ["\u250c\u2500\u2500\u2510", "\u2502\u25b6\u2588\u2502", "\u2514\u2500\u2500\u2518"],
    },
    {
        "label": "Terminal",
        "action": AppAction.TERMINAL,
        "art": ["\u250c\u2500\u2500\u2510", "\u2502>_\u2502", "\u2514\u2500\u2500\u2518"],
    },
    {"label": "Calc", "action": AppAction.CALCULATOR, "art": ["+--+", "|+-|", "+--+"]},
    {
        "label": "Logs",
        "action": AppAction.LOG_VIEWER,
        "art": ["\u250c\u2500\u2500\u2510", "\u2502LN\u2502", "\u2514\u2500\u2500\u2518"],
    },
    {
        "label": "Procs",
        "action": AppAction.PROCESS_MANAGER,
        "art": ["\u250c\u2500\u2500\u2510", "\u2502PS\u2502", "\u2514\u2500\u2500\u2518"],
    },
    {
        "label": "Clock",
        "action": AppAction.CLOCK_CALENDAR,
        "art": ["\u250c\u2500\u2500\u2510", "\u2502CL\u2502", "\u2514\u2500\u2500\u2518"],
    },
    {
        "label": "Images",
        "action": AppAction.IMAGE_VIEWER,
        "art": ["\u250c\u2500\u2500\u2510", "\u2502IM\u2502", "\u2514\u2500\u2500\u2518"],
    },
    {
        "label": "Trash",
        "action": AppAction.TRASH_BIN,
        "art": ["\u250c\u2500\u2500\u2510", "\u2502TR\u2502", "\u2514\u2500\u2500\u2518"],
    },
    {
        "label": "Settings",
        "action": AppAction.SETTINGS,
        "art": ["\u256d\u2500\u2500\u256e", "\u2502\u2699 \u2502", "\u2570\u2500\u2500\u256f"],
    },
    {
        "label": "About",
        "action": AppAction.ABOUT,
        "art": ["\u256d\u2500\u2500\u256e", "\u2502 ?\u2502", "\u2570\u2500\u2500\u256f"],
    },
]

# Fallback ASCII icons for non-Unicode terminals.
ICONS_ASCII = [
    {"label": "Files", "action": AppAction.FILE_MANAGER, "art": ["+--+", "|##|", "+--+"]},
    {"label": "Notepad", "action": AppAction.NOTEPAD, "art": ["+--+", "|==|", "+--+"]},
    {"label": "ASCII Vid", "action": AppAction.ASCII_VIDEO, "art": ["+--+", "|>|#", "+--+"]},
    {"label": "Terminal", "action": AppAction.TERMINAL, "art": ["+--+", "|>_|", "+--+"]},
    {"label": "Calc", "action": AppAction.CALCULATOR, "art": ["+--+", "|+-|", "+--+"]},
    {"label": "Logs", "action": AppAction.LOG_VIEWER, "art": ["+--+", "|LN|", "+--+"]},
    {"label": "Procs", "action": AppAction.PROCESS_MANAGER, "art": ["+--+", "|PS|", "+--+"]},
    {"label": "Clock", "action": AppAction.CLOCK_CALENDAR, "art": ["+--+", "|CL|", "+--+"]},
    {"label": "Images", "action": AppAction.IMAGE_VIEWER, "art": ["+--+", "|IM|", "+--+"]},
    {"label": "Trash", "action": AppAction.TRASH_BIN, "art": ["+--+", "|TR|", "+--+"]},
    {"label": "Settings", "action": AppAction.SETTINGS, "art": ["+--+", "|**|", "+--+"]},
    {"label": "About", "action": AppAction.ABOUT, "art": ["+--+", "| ?|", "+--+"]},
]

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".avi",
    ".mov",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".wmv",
}

# Legacy color pair IDs (kept for compatibility with existing code/tests).
C_DESKTOP = 1
C_MENUBAR = 2
C_MENU_ITEM = 3
C_MENU_SEL = 4
C_WIN_BORDER = 5
C_WIN_TITLE = 6
C_WIN_TITLE_INV = 7
C_WIN_BODY = 8
C_BUTTON = 9
C_BUTTON_SEL = 10
C_DIALOG = 11
C_STATUS = 12
C_ICON = 13
C_ICON_SEL = 14
C_SCROLLBAR = 15
C_WIN_INACTIVE = 16
C_FM_SELECTED = 17
C_FM_DIR = 18
C_TASKBAR = 19
C_ANSI_START = 50

# Layout constants
MENU_BAR_HEIGHT = 1          # Row 0 is the global menu bar
BOTTOM_BARS_HEIGHT = 2       # Taskbar + status bar at bottom
TASKBAR_TITLE_MAX_LEN = 15   # Max chars shown in taskbar buttons
WIN_MIN_WIDTH = 20           # Minimum window width on resize
WIN_MIN_HEIGHT = 8           # Minimum window height on resize
WIN_SPAWN_SCREEN_MARGIN = 4  # Margin from screen edge for new windows
ICON_ART_HEIGHT = 3          # Height of icon ASCII art in rows
ICON_DEFAULT_START_X = 3     # Default icon grid X start
ICON_DEFAULT_START_Y = 3     # Default icon grid Y start
ICON_DEFAULT_SPACING_Y = 5   # Default icon grid vertical spacing
DEFAULT_DOUBLE_CLICK_INTERVAL = 0.35  # Seconds for double-click detection
CLOCK_CLICK_REGION_WIDTH = 8  # Width of clock area in status bar
BINARY_DETECT_CHUNK_SIZE = 1024  # Bytes read to detect binary files

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
        "symbol": "\U0001F4C1",
        "art": ["\u250c\u2500\u2500\u2510", "\u2502FL\u2502", "\u2514\u2500\u2500\u2518"],
        "category": "Apps",
    },
    {
        "label": "Notepad",
        "action": AppAction.NOTEPAD,
        "symbol": "\U0001F4DD",
        "art": ["\u250c\u2500\u2500\u2510", "\u2502NP\u2502", "\u2514\u2500\u2500\u2518"],
        "category": "Apps",
    },
    {"label": "ASCII Vid", "action": AppAction.ASCII_VIDEO, "art": ["\u250c\u2500\u2500\u2510", "\u2502AV\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {
        "label": "Terminal",
        "action": AppAction.TERMINAL,
        "symbol": "\U0001F4BB",
        "art": ["\u250c\u2500\u2500\u2510", "\u2502>_\u2502", "\u2514\u2500\u2500\u2518"],
        "category": "Apps",
    },
    {"label": "Calc", "action": AppAction.CALCULATOR, "art": ["\u250c\u2500\u2500\u2510", "\u2502+-\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "Logs", "action": AppAction.LOG_VIEWER, "art": ["\u250c\u2500\u2500\u2510", "\u2502LG\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "Procs", "action": AppAction.PROCESS_MANAGER, "art": ["\u250c\u2500\u2500\u2510", "\u2502PS\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "Clock", "action": AppAction.CLOCK_CALENDAR, "art": ["\u250c\u2500\u2500\u2510", "\u2502CK\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "Images", "action": AppAction.IMAGE_VIEWER, "art": ["\u250c\u2500\u2500\u2510", "\u2502IM\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "Trash", "action": AppAction.TRASH_BIN, "art": ["\u250c\u2500\u2500\u2510", "\u2502TR\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {
        "label": "Settings",
        "action": AppAction.SETTINGS,
        "symbol": "\u2699\ufe0f",
        "art": ["\u250c\u2500\u2500\u2510", "\u2502ST\u2502", "\u2514\u2500\u2500\u2518"],
        "category": "Apps",
    },
    {
        "label": "About",
        "action": AppAction.ABOUT,
        "symbol": "\u2139\ufe0f",
        "art": ["\u250c\u2500\u2500\u2510", "\u2502i?\u2502", "\u2514\u2500\u2500\u2518"],
        "category": "Apps",
    },
    {"label": "Mines", "action": AppAction.MINESWEEPER, "art": ["\u250c\u2500\u2500\u2510", "\u2502MX\u2502", "\u2514\u2500\u2500\u2518"], "category": "Games"},
    {"label": "Solitaire", "action": AppAction.SOLITAIRE, "art": ["\u250c\u2500\u2500\u2510", "\u2502SL\u2502", "\u2514\u2500\u2500\u2518"], "category": "Games"},
    {"label": "Snake", "action": AppAction.SNAKE, "art": ["\u250c\u2500\u2500\u2510", "\u2502SN\u2502", "\u2514\u2500\u2500\u2518"], "category": "Games"},
    {"label": "Chars", "action": AppAction.CHARMAP, "art": ["\u250c\u2500\u2500\u2510", "\u2502CH\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "Clip", "action": AppAction.CLIPBOARD, "art": ["\u250c\u2500\u2500\u2510", "\u2502CB\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "Hex", "action": AppAction.HEX_VIEWER, "art": ["\u250c\u2500\u2500\u2510", "\u25020x\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "WiFi", "action": AppAction.WIFI_MANAGER, "art": ["\u250c\u2500\u2500\u2510", "\u2502WF\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {
        "label": "Desktop",
        "action": AppAction.DESKTOP_ICON_MANAGER,
        "art": ["\u250c\u2500\u2500\u2510", "\u2502DT\u2502", "\u2514\u2500\u2500\u2518"],
        "category": "Apps",
        "hide_key": "icons",
        "position_key": "Icons",
    },
    {
        "label": "Desktop 0.1",
        "action": AppAction.DESKTOP_ICON_MANAGER,
        "art": ["\u256d\u2500\u2500\u256e", "\u2502:)\u2502", "\u2570\u2500\u2500\u256f"],
        "category": "Apps",
    },
    {"label": "Menus", "action": AppAction.MENU_EDITOR, "art": ["\u250c\u2500\u2500\u2510", "\u2502MN\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "MdView", "action": AppAction.MARKDOWN_VIEWER, "art": ["\u250c\u2500\u2500\u2510", "\u2502MD\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "SysMon", "action": AppAction.SYSTEM_MONITOR, "art": ["\u250c\u2500\u2500\u2510", "\u2502SM\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "Control", "action": AppAction.CONTROL_PANEL, "art": ["\u250c\u2500\u2500\u2510", "\u2502CT\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
    {"label": "Tetris", "action": AppAction.TETRIS, "art": ["\u250c\u2500\u2500\u2510", "\u2502TT\u2502", "\u2514\u2500\u2500\u2518"], "category": "Games"},
    {"label": "RetroNet", "action": AppAction.RETRONET, "art": ["\u250c\u2500\u2500\u2510", "\u2502RN\u2502", "\u2514\u2500\u2500\u2518"], "category": "Apps"},
]

# Fallback ASCII icons for non-Unicode terminals.
ICONS_ASCII = [
    {"label": "Files", "action": AppAction.FILE_MANAGER, "symbol": "[D]", "art": ["+--+", "|FL|", "+--+"], "category": "Apps"},
    {"label": "Notepad", "action": AppAction.NOTEPAD, "symbol": "[N]", "art": ["+--+", "|NP|", "+--+"], "category": "Apps"},
    {"label": "ASCII Vid", "action": AppAction.ASCII_VIDEO, "art": ["+--+", "|AV|", "+--+"], "category": "Apps"},
    {"label": "Terminal", "action": AppAction.TERMINAL, "symbol": "[>]", "art": ["+--+", "|>_|", "+--+"], "category": "Apps"},
    {"label": "Calc", "action": AppAction.CALCULATOR, "art": ["+--+", "|+-|", "+--+"], "category": "Apps"},
    {"label": "Logs", "action": AppAction.LOG_VIEWER, "art": ["+--+", "|LG|", "+--+"], "category": "Apps"},
    {"label": "Procs", "action": AppAction.PROCESS_MANAGER, "art": ["+--+", "|PS|", "+--+"], "category": "Apps"},
    {"label": "Clock", "action": AppAction.CLOCK_CALENDAR, "art": ["+--+", "|CK|", "+--+"], "category": "Apps"},
    {"label": "Images", "action": AppAction.IMAGE_VIEWER, "art": ["+--+", "|IM|", "+--+"], "category": "Apps"},
    {"label": "Trash", "action": AppAction.TRASH_BIN, "art": ["+--+", "|TR|", "+--+"], "category": "Apps"},
    {"label": "Settings", "action": AppAction.SETTINGS, "symbol": "[S]", "art": ["+--+", "|ST|", "+--+"], "category": "Apps"},
    {"label": "About", "action": AppAction.ABOUT, "symbol": "[?]", "art": ["+--+", "|i?|", "+--+"], "category": "Apps"},
    {"label": "Mines", "action": AppAction.MINESWEEPER, "art": ["+--+", "|MX|", "+--+"], "category": "Games"},
    {"label": "Solitaire", "action": AppAction.SOLITAIRE, "art": ["+--+", "|SL|", "+--+"], "category": "Games"},
    {"label": "Snake", "action": AppAction.SNAKE, "art": ["+--+", "|SN|", "+--+"], "category": "Games"},
    {"label": "Chars", "action": AppAction.CHARMAP, "art": ["+--+", "|CH|", "+--+"], "category": "Apps"},
    {"label": "Clip", "action": AppAction.CLIPBOARD, "art": ["+--+", "|CB|", "+--+"], "category": "Apps"},
    {"label": "Hex", "action": AppAction.HEX_VIEWER, "art": ["+--+", "|0x|", "+--+"], "category": "Apps"},
    {"label": "WiFi", "action": AppAction.WIFI_MANAGER, "art": ["+--+", "|WF|", "+--+"], "category": "Apps"},
    {
        "label": "Desktop",
        "action": AppAction.DESKTOP_ICON_MANAGER,
        "art": ["+--+", "|DT|", "+--+"],
        "category": "Apps",
        "hide_key": "icons",
        "position_key": "Icons",
    },
    {
        "label": "Desktop 0.1",
        "action": AppAction.DESKTOP_ICON_MANAGER,
        "art": ["+--+", "|:)|", "+--+"],
        "category": "Apps",
    },
    {"label": "Menus", "action": AppAction.MENU_EDITOR, "art": ["+--+", "|MN|", "+--+"], "category": "Apps"},
    {"label": "MdView", "action": AppAction.MARKDOWN_VIEWER, "art": ["+--+", "|MD|", "+--+"], "category": "Apps"},
    {"label": "SysMon", "action": AppAction.SYSTEM_MONITOR, "art": ["+--+", "|SM|", "+--+"], "category": "Apps"},
    {"label": "Control", "action": AppAction.CONTROL_PANEL, "art": ["+--+", "|CT|", "+--+"], "category": "Apps"},
    {"label": "Tetris", "action": AppAction.TETRIS, "art": ["+--+", "|TT|", "+--+"], "category": "Games"},
    {"label": "RetroNet", "action": AppAction.RETRONET, "art": ["+--+", "|RN|", "+--+"], "category": "Apps"},
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
C_TERM_BODY = 20
C_ERROR = 21
C_ANSI_START = 50

# Layout constants
MENU_BAR_HEIGHT = 1          # Row 0 is the global menu bar
BOTTOM_BARS_HEIGHT = 1       # Unified bottom bar (taskbar + status info)
TASKBAR_TITLE_MAX_LEN = 15   # Max chars shown in taskbar buttons
WIN_MIN_WIDTH = 20           # Minimum window width on resize
WIN_MIN_HEIGHT = 8           # Minimum window height on resize
WIN_SPAWN_SCREEN_MARGIN = 4  # Margin from screen edge for new windows
ICON_ART_HEIGHT = 3          # Height of icon ASCII art in rows
ICON_DEFAULT_START_X = 3     # Default icon grid X start
ICON_DEFAULT_START_Y = 3     # Default icon grid Y start
ICON_DEFAULT_SPACING_X = 12  # Default icon grid horizontal spacing (chars per column)
ICON_DEFAULT_SPACING_Y = 5   # Default icon grid vertical spacing
ICON_GRID_BOTTOM_MARGIN = 3  # Rows reserved at bottom for icon grid boundary
ICON_FALLBACK_TERMINAL_HEIGHT = 24  # Fallback terminal height when stdscr is unavailable
DEFAULT_DOUBLE_CLICK_INTERVAL = 0.35  # Seconds for double-click detection
CLOCK_CLICK_REGION_WIDTH = 8  # Width of clock area in status bar
BINARY_DETECT_CHUNK_SIZE = 1024  # Bytes read to detect binary files

# Terminal / input constants
# Idle timeout keeps CPU low when the desktop is mostly static.
TERMINAL_INPUT_TIMEOUT_MS = 500  # Curses input timeout in milliseconds
# Live terminal windows need lower latency for smooth shell output/input.
TERMINAL_LIVE_INPUT_TIMEOUT_MS = 33  # ~30 FPS polling cadence
# Background workers (progress dialogs) benefit from faster updates than idle mode.
TERMINAL_BACKGROUND_INPUT_TIMEOUT_MS = 120
MOUSE_SCROLL_DOWN_FALLBACK = 0x200000  # Fallback mask for BUTTON5_PRESSED (scroll down)

# Welcome window dimensions
WELCOME_WIN_WIDTH = 44   # Width of the welcome dialog window
WELCOME_WIN_HEIGHT = 20  # Height of the welcome dialog window


"""
Typed action contract used by windows/apps to communicate with RetroTUI.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    """Supported action kinds exchanged with the app dispatcher."""

    OPEN_FILE = "open_file"
    EXECUTE = "execute"
    REQUEST_SAVE_AS = "request_save_as"
    REQUEST_OPEN_PATH = "request_open_path"
    REQUEST_RENAME_ENTRY = "request_rename_entry"
    REQUEST_DELETE_CONFIRM = "request_delete_confirm"
    REQUEST_COPY_ENTRY = "request_copy_entry"
    REQUEST_MOVE_ENTRY = "request_move_entry"
    REQUEST_COPY_BETWEEN_PANES = "request_copy_between_panes"
    REQUEST_MOVE_BETWEEN_PANES = "request_move_between_panes"
    REQUEST_NEW_DIR = "request_new_dir"
    REQUEST_NEW_FILE = "request_new_file"
    REQUEST_KILL_CONFIRM = "request_kill_confirm"
    SAVE_ERROR = "save_error"
    ERROR = "error"
    UPDATE_CONFIG = "update_config"
    REFRESH = "refresh"


class AppAction(str, Enum):
    """Application-level actions used by menus, icons and dispatchers."""

    EXIT = "exit"
    ABOUT = "about"
    HELP = "help"
    FILE_MANAGER = "filemanager"
    NOTEPAD = "notepad"
    ASCII_VIDEO = "asciivideo"
    TERMINAL = "terminal"
    SETTINGS = "settings"
    CALCULATOR = "calculator"
    LOG_VIEWER = "log_viewer"
    PROCESS_MANAGER = "process_manager"
    CLOCK_CALENDAR = "clock_calendar"
    IMAGE_VIEWER = "image_viewer"
    TRASH_BIN = "trash_bin"
    NEW_WINDOW = "new_window"
    CLOSE_WINDOW = "close"
    NP_NEW = "np_new"
    NP_OPEN = "np_open"
    NP_SAVE = "np_save"
    NP_SAVE_AS = "np_save_as"
    NP_CLOSE = "np_close"
    NP_TOGGLE_WRAP = "np_toggle_wrap"
    FM_OPEN = "fm_open"
    FM_COPY = "fm_copy"
    FM_MOVE = "fm_move"
    FM_NEW_DIR = "fm_new_dir"
    FM_NEW_FILE = "fm_new_file"
    FM_PARENT = "fm_parent"
    FM_TOGGLE_HIDDEN = "fm_toggle_hidden"
    FM_REFRESH = "fm_refresh"
    FM_RENAME = "fm_rename"
    FM_DELETE = "fm_delete"
    FM_CLOSE = "fm_close"
    FM_UNDO_DELETE = "fm_undo_delete"
    FM_TOGGLE_SELECT = "fm_toggle_select"
    FM_BOOKMARK_1 = "fm_bookmark_1"
    FM_BOOKMARK_2 = "fm_bookmark_2"
    FM_BOOKMARK_3 = "fm_bookmark_3"
    FM_BOOKMARK_4 = "fm_bookmark_4"
    FM_SET_BOOKMARK_1 = "fm_set_bookmark_1"
    FM_SET_BOOKMARK_2 = "fm_set_bookmark_2"
    FM_SET_BOOKMARK_3 = "fm_set_bookmark_3"
    FM_SET_BOOKMARK_4 = "fm_set_bookmark_4"

    # New app actions
    MINESWEEPER = "minesweeper"
    SOLITAIRE = "solitaire"
    SNAKE = "snake"
    CHARMAP = "charmap"
    CLIPBOARD = "clipboard"
    WIFI_MANAGER = "wifi_manager"

    # Snake specific
    SNAKE_NEW = "snake_new"
    SNAKE_TOGGLE_WRAP = "snake_toggle_wrap"
    SNAKE_PAUSE = "snake_pause"


@dataclass(frozen=True)
class ActionResult:
    """Action message emitted by window/app handlers."""

    type: ActionType
    payload: Any = None

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
    SAVE_ERROR = "save_error"


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
    NEW_WINDOW = "new_window"
    CLOSE_WINDOW = "close"
    NP_NEW = "np_new"
    NP_SAVE = "np_save"
    NP_SAVE_AS = "np_save_as"
    NP_CLOSE = "np_close"
    NP_TOGGLE_WRAP = "np_toggle_wrap"
    FM_OPEN = "fm_open"
    FM_PARENT = "fm_parent"
    FM_TOGGLE_HIDDEN = "fm_toggle_hidden"
    FM_REFRESH = "fm_refresh"
    FM_CLOSE = "fm_close"


@dataclass(frozen=True)
class ActionResult:
    """Action message emitted by window/app handlers."""

    type: ActionType
    payload: Any = None

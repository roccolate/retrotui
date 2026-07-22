"""
Typed action contract used by windows/apps to communicate with RetroTUI.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar


class ActionType(str, Enum):
    """Supported action kinds exchanged with the app dispatcher."""

    OPEN_FILE = "open_file"
    EXECUTE = "execute"
    REQUEST_SAVE_AS = "request_save_as"
    REQUEST_SAVE_CONFIRM = "request_save_confirm"
    REQUEST_OPEN_PATH = "request_open_path"
    REQUEST_RENAME_ENTRY = "request_rename_entry"
    REQUEST_DELETE_CONFIRM = "request_delete_confirm"
    REQUEST_EMPTY_TRASH_CONFIRM = "request_empty_trash_confirm"
    REQUEST_RESTORE_TRASH = "request_restore_trash"
    REQUEST_COPY_ENTRY = "request_copy_entry"
    REQUEST_MOVE_ENTRY = "request_move_entry"
    REQUEST_COPY_BETWEEN_PANES = "request_copy_between_panes"
    REQUEST_MOVE_BETWEEN_PANES = "request_move_between_panes"
    REQUEST_NEW_DIR = "request_new_dir"
    REQUEST_NEW_FILE = "request_new_file"
    REQUEST_URL = "request_url"
    REQUEST_KILL_CONFIRM = "request_kill_confirm"
    REQUEST_BOOKMARKS = "request_bookmarks"
    REQUEST_ADD_BOOKMARK = "request_add_bookmark"
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
    HEX_VIEWER = "hex_viewer"
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

    # App actions
    CLIPBOARD = "clipboard"
    APP_MANAGER = "app_manager"
    DESKTOP_ICON_MANAGER = "desktop_icon_manager"
    ICONS = "icons"
    MENU_EDITOR = "menu_editor"
    MARKDOWN_VIEWER = "markdown_viewer"
    SYSTEM_MONITOR = "system_monitor"
    CONTROL_PANEL = "control_panel"


class _PayloadCompat:
    """Small read-only mapping facade retained for legacy plugins/tests."""

    _payload_fields: ClassVar[tuple[str, ...]] = ()

    def __getitem__(self, key):
        if key not in self._payload_fields:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self._payload_fields

    def items(self):
        return tuple((key, getattr(self, key)) for key in self._payload_fields)

    def as_dict(self):
        return dict(self.items())


@dataclass(frozen=True)
class SaveConfirmPayload(_PayloadCompat):
    """Callbacks and message for a destructive unsaved-document decision."""

    on_discard: Callable[[], Any] | None = None
    on_cancel: Callable[[], Any] | None = None
    message: str = ""
    _payload_fields: ClassVar[tuple[str, ...]] = (
        "on_discard",
        "on_cancel",
        "message",
    )

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            return cls()
        on_discard = value.get("on_discard")
        on_cancel = value.get("on_cancel")
        message = value.get("message", "")
        return cls(
            on_discard=on_discard if callable(on_discard) else None,
            on_cancel=on_cancel if callable(on_cancel) else None,
            message=str(message) if message is not None else "",
        )


@dataclass(frozen=True)
class FileTransferPayload(_PayloadCompat):
    """Explicit source and destination for a copy/move request."""

    source: str = ""
    destination: str = ""
    _payload_fields: ClassVar[tuple[str, ...]] = ("source", "destination")

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        getter = getattr(value, "get", None)
        if not callable(getter):
            return cls()
        source = getter("source", "")
        destination = getter("destination", getter("dest", ""))
        return cls(
            source=str(source or "").strip(),
            destination=str(destination or "").strip(),
        )


@dataclass(frozen=True)
class ProcessSignalPayload(_PayloadCompat):
    """Validated process signal request."""

    pid: int = 0
    command: str = ""
    signal: int = 15
    start_time_ticks: int = 0
    _payload_fields: ClassVar[tuple[str, ...]] = (
        "pid",
        "command",
        "signal",
        "start_time_ticks",
    )

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            return cls()
        try:
            pid = int(value.get("pid", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            pid = 0
        try:
            signal_number = int(value.get("signal", 15) or 15)
        except (TypeError, ValueError, OverflowError):
            signal_number = 15
        try:
            start_time_ticks = int(value.get("start_time_ticks", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            start_time_ticks = 0
        command = value.get("command", "")
        return cls(
            pid=pid,
            command=str(command or ""),
            signal=signal_number,
            start_time_ticks=max(0, start_time_ticks),
        )


def _optional_bool(value):
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


@dataclass(frozen=True)
class ConfigUpdatePayload(_PayloadCompat):
    """Recognized preference fields accepted from extension action results."""

    show_hidden: bool | None = None
    word_wrap_default: bool | None = None
    sunday_first: bool | None = None
    show_welcome: bool | None = None
    _payload_fields: ClassVar[tuple[str, ...]] = (
        "show_hidden",
        "word_wrap_default",
        "sunday_first",
        "show_welcome",
    )

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            return cls()
        return cls(
            show_hidden=_optional_bool(value.get("show_hidden")),
            word_wrap_default=_optional_bool(value.get("word_wrap_default")),
            sunday_first=_optional_bool(value.get("sunday_first")),
            show_welcome=_optional_bool(value.get("show_welcome")),
        )

    def as_kwargs(self):
        return {
            key: value
            for key, value in self.items()
            if value is not None
        }


@dataclass(frozen=True)
class ActionResult:
    """Action message emitted by window/app handlers."""

    type: ActionType
    payload: Any = None

    # Backwards-compatible aliases used by older tests/code
    @property
    def action_type(self):
        return self.type

    @property
    def action_payload(self):
        return self.payload

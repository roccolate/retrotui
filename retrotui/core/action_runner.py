"""Action execution helpers for RetroTUI app-level actions."""

import inspect

from ..apps.filemanager import FileManagerWindow
from ..apps.notepad import NotepadWindow
from ..apps.settings import SettingsWindow
from ..apps.terminal import TerminalWindow
from ..apps.calculator import CalculatorWindow
from ..apps.logviewer import LogViewerWindow
from ..apps.process_manager import ProcessManagerWindow
from ..apps.clock import ClockCalendarWindow
from ..apps.image_viewer import ImageViewerWindow
from ..apps.trash import TrashWindow
from ..apps.minesweeper import MinesweeperWindow
from ..apps.solitaire import SolitaireWindow
from ..apps.snake import SnakeWindow
from ..apps.charmap import CharacterMapWindow
from ..apps.clipboard_viewer import ClipboardViewerWindow
from ..apps.wifi_manager import WifiManagerWindow
from ..ui.dialog import Dialog
from ..ui.window import Window
from .actions import AppAction
from .content import build_about_message, build_help_message


def _supports_constructor_kwarg(constructor, kwarg: str) -> bool:
    """Return True when callable constructor accepts the provided keyword."""
    try:
        params = inspect.signature(constructor).parameters.values()
    except (TypeError, ValueError):
        return False

    for param in params:
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
        if param.name == kwarg and param.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            return True
    return False


def execute_app_action(app, action, logger, *, version: str) -> None:
    """Execute an AppAction against a RetroTUI-like app context."""
    if action == AppAction.EXIT:
        app.dialog = Dialog(
            "Exit RetroTUI",
            "Are you sure you want to exit?\n\nAll windows will be closed.",
            ["Yes", "No"],
            width=44,
        )
        return

    if action == AppAction.ABOUT:
        app.dialog = Dialog("About RetroTUI", build_about_message(version), ["OK"], width=52)
        return

    if action == AppAction.HELP:
        app.dialog = Dialog("Keyboard & Mouse Help", build_help_message(), ["OK"], width=46)
        return

    if action == AppAction.FILE_MANAGER:
        offset_x, offset_y = app._next_window_offset(15, 3)
        kwargs = {}
        if _supports_constructor_kwarg(FileManagerWindow, 'show_hidden_default'):
            kwargs['show_hidden_default'] = getattr(app, 'default_show_hidden', False)
        win = FileManagerWindow(offset_x, offset_y, 58, 22, **kwargs)
        app._spawn_window(win)
        return

    if action == AppAction.NOTEPAD:
        offset_x, offset_y = app._next_window_offset(20, 4)
        kwargs = {}
        if _supports_constructor_kwarg(NotepadWindow, 'wrap_default'):
            kwargs['wrap_default'] = getattr(app, 'default_word_wrap', False)
        win = NotepadWindow(offset_x, offset_y, 60, 20, **kwargs)
        app._spawn_window(win)
        return

    if action == AppAction.ASCII_VIDEO:
        opener = getattr(app, "show_video_open_dialog", None)
        if callable(opener):
            opener()
            return
        app.dialog = Dialog(
            "ASCII Video",
            "Reproduce video en la terminal.\n\n"
            "Usa mpv (color) o mplayer (fallback).\n"
            "Abre un video desde File Manager.",
            ["OK"],
            width=50,
        )
        return

    if action == AppAction.IMAGE_VIEWER:
        offset_x, offset_y = app._next_window_offset(14, 3)
        app._spawn_window(ImageViewerWindow(offset_x, offset_y, 84, 26))
        return

    if action == AppAction.TERMINAL:
        offset_x, offset_y = app._next_window_offset(18, 5)
        app._spawn_window(TerminalWindow(offset_x, offset_y, 70, 18))
        return

    if action == AppAction.TRASH_BIN:
        offset_x, offset_y = app._next_window_offset(15, 4)
        app._spawn_window(TrashWindow(offset_x, offset_y, 62, 20))
        return

    if action == AppAction.SETTINGS:
        offset_x, offset_y = app._next_window_offset(22, 4)
        app._spawn_window(SettingsWindow(offset_x, offset_y, 56, 18, app))
        return

    if action == AppAction.CALCULATOR:
        offset_x, offset_y = app._next_window_offset(24, 5)
        app._spawn_window(CalculatorWindow(offset_x, offset_y, 44, 14))
        return

    if action == AppAction.LOG_VIEWER:
        offset_x, offset_y = app._next_window_offset(16, 4)
        app._spawn_window(LogViewerWindow(offset_x, offset_y, 74, 22))
        return

    if action == AppAction.PROCESS_MANAGER:
        offset_x, offset_y = app._next_window_offset(14, 3)
        app._spawn_window(ProcessManagerWindow(offset_x, offset_y, 76, 22))
        return

    if action == AppAction.CLOCK_CALENDAR:
        offset_x, offset_y = app._next_window_offset(30, 6)
        app._spawn_window(ClockCalendarWindow(offset_x, offset_y, 34, 14))
        return

    if action == AppAction.NEW_WINDOW:
        offset_x, offset_y = app._next_window_offset(20, 3)
        app._spawn_window(
            Window(
                f"Window {Window._next_id}",
                offset_x,
                offset_y,
                40,
                12,
                content=["", " New empty window", ""],
            )
        )
        return

    if action == AppAction.MINESWEEPER:
        offset_x, offset_y = app._next_window_offset(18, 4)
        app._spawn_window(MinesweeperWindow(offset_x, offset_y, 54, 20))
        return

    if action == AppAction.SOLITAIRE:
        offset_x, offset_y = app._next_window_offset(20, 4)
        app._spawn_window(SolitaireWindow(offset_x, offset_y, 70, 22))
        return

    if action == AppAction.SNAKE:
        offset_x, offset_y = app._next_window_offset(22, 5)
        app._spawn_window(SnakeWindow(offset_x, offset_y, 48, 20))
        return

    if action == AppAction.CHARMAP:
        offset_x, offset_y = app._next_window_offset(26, 6)
        app._spawn_window(CharacterMapWindow(offset_x, offset_y, 46, 18))
        return

    if action == AppAction.CLIPBOARD:
        offset_x, offset_y = app._next_window_offset(24, 5)
        app._spawn_window(ClipboardViewerWindow(offset_x, offset_y, 56, 18))
        return

    if action == AppAction.WIFI_MANAGER:
        offset_x, offset_y = app._next_window_offset(22, 4)
        app._spawn_window(WifiManagerWindow(offset_x, offset_y, 60, 18))
        return

    logger.warning("Unknown action received: %s", action)

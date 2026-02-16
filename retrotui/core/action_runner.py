"""Action execution helpers for RetroTUI app-level actions."""

from ..apps.filemanager import FileManagerWindow
from ..apps.notepad import NotepadWindow
from ..apps.terminal import TerminalWindow
from ..ui.dialog import Dialog
from ..ui.window import Window
from .actions import AppAction
from .content import build_about_message, build_help_message, build_settings_content


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
        app._spawn_window(FileManagerWindow(offset_x, offset_y, 58, 22))
        return

    if action == AppAction.NOTEPAD:
        offset_x, offset_y = app._next_window_offset(20, 4)
        app._spawn_window(NotepadWindow(offset_x, offset_y, 60, 20))
        return

    if action == AppAction.ASCII_VIDEO:
        app.dialog = Dialog(
            "ASCII Video",
            "Reproduce video en la terminal.\n\n"
            "Usa mpv (color) o mplayer (fallback).\n"
            "Abre un video desde File Manager.",
            ["OK"],
            width=50,
        )
        return

    if action == AppAction.TERMINAL:
        offset_x, offset_y = app._next_window_offset(18, 5)
        app._spawn_window(TerminalWindow(offset_x, offset_y, 70, 18))
        return

    if action == AppAction.SETTINGS:
        offset_x, offset_y = app._next_window_offset(22, 4)
        app._spawn_window(
            Window(
                "Settings",
                offset_x,
                offset_y,
                48,
                15,
                content=build_settings_content(),
            )
        )
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

    logger.warning("Unknown action received: %s", action)

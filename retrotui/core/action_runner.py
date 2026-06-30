"""Action execution helpers for RetroTUI app-level actions."""

import curses
import functools
import inspect

from ..apps.filemanager import FileManagerWindow
from ..apps.notepad import NotepadWindow
from ..apps.settings import SettingsWindow
from ..apps.terminal import TerminalWindow
from ..apps.calculator import CalculatorWindow
from ..apps.logviewer import LogViewerWindow
from ..apps.process_manager import ProcessManagerWindow
from ..apps.trash import TrashWindow
from ..apps.hexviewer import HexViewerWindow
from ..apps.sysmon import SystemMonitorWindow
from ..apps.control_panel import ControlPanelWindow
from ..apps.clipboard_viewer import ClipboardViewerWindow
from ..ui.dialog import Dialog
from ..ui.window import Window
from .actions import AppAction
from .content import build_about_message, build_help_message
from ..constants import _CURSES_ERROR, WIN_MIN_HEIGHT, WIN_MIN_WIDTH
_TERMINAL_SIZE_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)
_PLUGIN_ACTION_ROUTE_ERRORS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)


@functools.lru_cache(maxsize=None)
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


# Registry mapping AppAction -> (class_name, width, height, base_x, base_y, kwarg_map)
#
# class_name is a string — the module-level attribute name of the window class.
# Looked up via globals() at dispatch time so that mock.patch.object() works in
# tests (patching the module attribute is enough; no need to monkey-patch the dict).
#
# kwarg_map: {constructor_kwarg_name: app_attribute_name}
# Only "simple spawn" actions belong here — actions with special logic stay
# as explicit handlers below.
_APP_REGISTRY = {
    AppAction.HEX_VIEWER:      ("HexViewerWindow",      76, 22, 16, 4, {}),
    AppAction.TERMINAL:        ("TerminalWindow",        80, 24, 18, 5, {}),
    AppAction.TRASH_BIN:       ("TrashWindow",           62, 20, 15, 4, {}),
    AppAction.CALCULATOR:      ("CalculatorWindow",      44, 14, 24, 5, {}),
    AppAction.LOG_VIEWER:      ("LogViewerWindow",       74, 22, 16, 4, {}),
    AppAction.PROCESS_MANAGER: ("ProcessManagerWindow",  76, 22, 14, 3, {}),
    AppAction.CLIPBOARD:       ("ClipboardViewerWindow", 56, 18, 24, 5, {}),
    AppAction.SYSTEM_MONITOR:  ("SystemMonitorWindow",   44, 20, 15, 4, {}),
    # Actions with kwargs derived from app state
    AppAction.FILE_MANAGER:    ("FileManagerWindow",     70, 24,  8, 3,
                                {"show_hidden_default": "default_show_hidden"}),
    AppAction.NOTEPAD:         ("NotepadWindow",         60, 20, 20, 4,
                                {"wrap_default": "default_word_wrap"}),
}

# Module globals reference, captured once so _spawn_registered_app can resolve
# class names to the current module-level binding (honours mock.patch.object).
_MODULE_GLOBALS = globals()


def _spawn_registered_app(app, action, registry) -> bool:
    """Look up *action* in *registry* and spawn the window.

    Returns True when the action was handled, False when not found.
    Terminal size is retrieved via curses when available; dimensions are
    clamped so windows fit on-screen.
    """
    entry = registry.get(action)
    if entry is None:
        return False

    class_name, default_w, default_h, base_x, base_y, kwarg_map = entry

    # Resolve the class through the module's live globals so that
    # mock.patch.object() substitutions are picked up at call time.
    cls = _MODULE_GLOBALS[class_name]

    # Clamp to terminal size when curses is available.
    try:
        term_h, term_w = curses.LINES, curses.COLS
        w = min(default_w, max(WIN_MIN_WIDTH, term_w - 4))
        h = min(default_h, max(WIN_MIN_HEIGHT, term_h - 4))
    except _TERMINAL_SIZE_ERRORS:
        w, h = default_w, default_h

    offset_x, offset_y = app._next_window_offset(base_x, base_y)

    kwargs = {}
    for kwarg_name, attr_name in kwarg_map.items():
        if _supports_constructor_kwarg(cls, kwarg_name):
            kwargs[kwarg_name] = getattr(app, attr_name, False)

    win = cls(offset_x, offset_y, w, h, **kwargs)
    app._spawn_window(win)
    return True


def execute_app_action(app, action, logger, *, version: str) -> None:
    """Execute an AppAction against a RetroTUI-like app context."""
    # Plugin actions: string like 'plugin:<id>' open plugin windows
    try:
        if isinstance(action, str) and action.startswith('plugin:'):
            plugin_id = action.split(':', 1)[1]
            opener = getattr(app, 'open_plugin', None)
            if callable(opener):
                opener(plugin_id)
                return
    except _PLUGIN_ACTION_ROUTE_ERRORS:
        # don't let plugin issues crash the app
        logger.debug('plugin action failed', exc_info=True)

    # --- Special-case actions (non-trivial logic) ---

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

    if action == AppAction.SETTINGS:
        offset_x, offset_y = app._next_window_offset(22, 4)
        app._spawn_window(SettingsWindow(offset_x, offset_y, 56, 18, app))
        return

    if action in (AppAction.APP_MANAGER, AppAction.DESKTOP_ICON_MANAGER):
        from ..apps.app_manager import DesktopIconManagerWindow
        offset_x, offset_y = app._next_window_offset(22, 6)
        app._spawn_window(DesktopIconManagerWindow(offset_x, offset_y, 72, 22, app))
        return

    if action == AppAction.ICONS:
        from ..apps.app_manager import IconsWindow
        offset_x, offset_y = app._next_window_offset(22, 6)
        app._spawn_window(IconsWindow(offset_x, offset_y, 72, 22, app))
        return

    if action == AppAction.MENU_EDITOR:
        from ..apps.app_manager import MenuEditorWindow
        offset_x, offset_y = app._next_window_offset(20, 5)
        app._spawn_window(MenuEditorWindow(offset_x, offset_y, 76, 22, app))
        return

    if action == AppAction.MARKDOWN_VIEWER:
        from ..apps.markdown_viewer import MarkdownViewerWindow
        offset_x, offset_y = app._next_window_offset(18, 4)
        app._spawn_window(MarkdownViewerWindow(offset_x, offset_y, 70, 24))
        return

    if action == AppAction.CONTROL_PANEL:
        offset_x, offset_y = app._next_window_offset(10, 3)
        app._spawn_window(ControlPanelWindow(offset_x, offset_y, 60, 18, app))
        return

    # --- Registry dispatch for simple window-spawn actions ---
    if _spawn_registered_app(app, action, _APP_REGISTRY):
        return

    logger.warning("Unknown action received: %s", action)

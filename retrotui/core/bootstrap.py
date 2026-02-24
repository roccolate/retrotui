"""Terminal bootstrap helpers for RetroTUI startup and cleanup."""

import curses
import sys
import os

from ..constants import MOUSE_SCROLL_DOWN_FALLBACK

# Platform-aware termios import
if os.name == 'nt':
    from . import win_termios as termios
else:
    import termios

_CURSES_ERROR = getattr(curses, "error", Exception)
_TERMINAL_SETUP_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)
_FLOW_CONTROL_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_FLOW_CONTROL_ATTR_ERRORS = (AttributeError, IndexError, TypeError, ValueError)
_MOUSEMASK_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)


def detect_mouse_backend():
    """Return normalized mouse backend name for current terminal session."""
    forced = (os.environ.get("RETROTUI_MOUSE_BACKEND") or "").strip().lower()
    if forced in {"gpm", "sgr"}:
        return forced
    return "gpm" if os.environ.get("TERM") == "linux" else "sgr"


def configure_terminal(stdscr, timeout_ms=500):
    """Apply core curses terminal setup.

    Some terminals/backends only support a subset of curses features.
    We treat setup as best-effort to avoid failing startup on missing caps.
    """
    for fn, args in (
        (getattr(curses, "curs_set", None), (0,)),
        (getattr(curses, "noecho", None), ()),
        (getattr(curses, "cbreak", None), ()),
        (getattr(stdscr, "keypad", None), (True,)),
        (getattr(stdscr, "nodelay", None), (False,)),
        (getattr(stdscr, "timeout", None), (timeout_ms,)),
    ):
        if not callable(fn):
            continue
        try:
            fn(*args)
        except _TERMINAL_SETUP_ERRORS:
            continue


def disable_flow_control(stdin_stream=None):
    """Disable XON/XOFF so Ctrl+Q/Ctrl+S reach the app."""
    stream = sys.stdin if stdin_stream is None else stdin_stream
    try:
        fd = stream.fileno()
    except _FLOW_CONTROL_ERRORS:
        return
    # Prefer a `termios` module in sys.modules (tests inject a fake there).
    fallback_mod = sys.modules.get('termios')
    if fallback_mod is not None and callable(getattr(fallback_mod, 'tcgetattr', None)):
        tcget = getattr(fallback_mod, 'tcgetattr')
        tcset = getattr(fallback_mod, 'tcsetattr', None)
    else:
        tcget = getattr(termios, 'tcgetattr', None)
        tcset = getattr(termios, 'tcsetattr', None)
        if not callable(tcget) or not callable(tcset):
            try:
                import importlib
                mod = importlib.import_module('termios')
                tcget = getattr(mod, 'tcgetattr', tcget)
                tcset = getattr(mod, 'tcsetattr', tcset)
            except (ImportError, ModuleNotFoundError, AttributeError, TypeError, ValueError):
                return

    try:
        attrs = tcget(fd)
    except _FLOW_CONTROL_ERRORS:
        return

    try:
        # Prefer constants from the injected `termios` module (fallback_mod),
        # then the module bound at import time, then sys.modules entry.
        def _get_const(name, default=0):
            if fallback_mod is not None and hasattr(fallback_mod, name):
                return getattr(fallback_mod, name)
            if hasattr(termios, name):
                return getattr(termios, name)
            return getattr(sys.modules.get('termios', object()), name, default)

        ixon = _get_const('IXON', 0)
        ixoff = _get_const('IXOFF', 0)

        if ixon or ixoff:
            try:
                if len(attrs) > 0:
                    attrs[0] &= ~ixon
                    attrs[0] &= ~ixoff
            except _FLOW_CONTROL_ATTR_ERRORS:
                pass
            try:
                if len(attrs) > 3:
                    attrs[3] &= ~ixon
                    attrs[3] &= ~ixoff
            except _FLOW_CONTROL_ATTR_ERRORS:
                pass

        tcset(fd, _get_const('TCSANOW', 0), attrs)
    except (AttributeError, ValueError, OSError):
        pass


def enable_mouse_support():
    """Enable curses mouse mask and SGR tracking modes."""
    all_mouse_events = getattr(curses, "ALL_MOUSE_EVENTS", 0)
    report_mouse_position = getattr(curses, "REPORT_MOUSE_POSITION", 0)
    button1_clicked = getattr(curses, "BUTTON1_CLICKED", 0)
    button1_pressed = getattr(curses, "BUTTON1_PRESSED", 0)
    button1_double = getattr(curses, "BUTTON1_DOUBLE_CLICKED", 0)
    button1_released = getattr(curses, "BUTTON1_RELEASED", 0)

    mousemask_fn = getattr(curses, "mousemask", None)
    if callable(mousemask_fn):
        try:
            mousemask_fn(all_mouse_events | report_mouse_position)
        except _MOUSEMASK_ERRORS:
            pass

    click_flags = (
        button1_clicked
        | button1_pressed
        | button1_double
    )
    # End drag/resize on release-like events, not on BUTTON1_PRESSED.
    # This keeps TTY/GPM drag streams working where motion is reported with PRESSED.
    stop_drag_flags = (
        button1_released
        | button1_clicked
        | button1_double
    )
    scroll_down_mask = getattr(curses, 'BUTTON5_PRESSED', MOUSE_SCROLL_DOWN_FALLBACK)

    if detect_mouse_backend() != "gpm":
        # Use 1002 (button-event tracking) + 1006 (SGR coordinates)
        print('\033[?1002h', end='', flush=True)
        print('\033[?1006h', end='', flush=True)
    return click_flags, stop_drag_flags, scroll_down_mask


def disable_mouse_support():
    """Restore terminal mouse tracking modes."""
    if detect_mouse_backend() != "gpm":
        print('\033[?1002l', end='', flush=True)
        print('\033[?1006l', end='', flush=True)

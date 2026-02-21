"""Terminal bootstrap helpers for RetroTUI startup and cleanup."""

import curses
import sys
import os

# Platform-aware termios import
if os.name == 'nt':
    from . import win_termios as termios
else:
    import termios


def configure_terminal(stdscr, timeout_ms=500):
    """Apply core curses terminal setup."""
    curses.curs_set(0)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.nodelay(False)
    stdscr.timeout(timeout_ms)


def disable_flow_control(stdin_stream=None):
    """Disable XON/XOFF so Ctrl+Q/Ctrl+S reach the app."""
    stream = sys.stdin if stdin_stream is None else stdin_stream
    try:
        fd = stream.fileno()
    except Exception:
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
            except Exception:
                return

    try:
        attrs = tcget(fd)
    except Exception:
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
            except Exception:
                pass
            try:
                if len(attrs) > 3:
                    attrs[3] &= ~ixon
                    attrs[3] &= ~ixoff
            except Exception:
                pass

        tcset(fd, _get_const('TCSANOW', 0), attrs)
    except (AttributeError, ValueError, OSError):
        pass


def enable_mouse_support():
    """Enable curses mouse mask and SGR tracking modes."""
    curses.mousemask(
        curses.ALL_MOUSE_EVENTS
        | curses.REPORT_MOUSE_POSITION
    )
    click_flags = (
        curses.BUTTON1_CLICKED
        | curses.BUTTON1_PRESSED
        | curses.BUTTON1_DOUBLE_CLICKED
    )
    # End drag/resize on release-like events, not on BUTTON1_PRESSED.
    # This keeps TTY/GPM drag streams working where motion is reported with PRESSED.
    stop_drag_flags = (
        curses.BUTTON1_RELEASED
        | curses.BUTTON1_CLICKED
        | curses.BUTTON1_DOUBLE_CLICKED
    )
    scroll_down_mask = getattr(curses, 'BUTTON5_PRESSED', 0x200000)

    # Use 1002 (button-event tracking) + 1006 (SGR coordinates)
    print('\033[?1002h', end='', flush=True)
    print('\033[?1006h', end='', flush=True)
    return click_flags, stop_drag_flags, scroll_down_mask


def disable_mouse_support():
    """Restore terminal mouse tracking modes."""
    print('\033[?1002l', end='', flush=True)
    print('\033[?1006l', end='', flush=True)

"""Focused-terminal keyboard ownership and host-command prefix policy."""

from __future__ import annotations

import curses

from ..utils import normalize_key_code
from .actions import AppAction


_HOST_PREFIX_OWNER_ATTR = "_retrotui_terminal_host_prefix_owner"


def is_terminal_input_target(window) -> bool:
    """Return whether ``window`` exposes the terminal input capabilities.

    The router intentionally uses capabilities instead of a concrete class or
    visible title so terminal-like plugins can opt into the same policy.
    """
    if window is None:
        return False
    return callable(getattr(window, "_key_to_input", None)) and callable(
        getattr(window, "_forward_payload", None)
    )


def _prefix_key_code() -> int:
    return int(getattr(curses, "KEY_F12", 276))


def _backtab_key_code() -> int:
    return int(getattr(curses, "KEY_BTAB", 353))


def _function_key_code(number: int):
    return getattr(curses, f"KEY_F{number}", None)


def _terminal_reserved_key_codes() -> set[int]:
    """Keys that RetroTUI otherwise consumes before the focused terminal."""
    codes = {9, 17, _backtab_key_code()}  # Tab, Ctrl+Q, Shift+Tab
    for number in (6, 7, 8, 10):
        code = _function_key_code(number)
        if code is not None:
            codes.add(int(code))
    return codes


def _clear_prefix_owner(app):
    owner = getattr(app, _HOST_PREFIX_OWNER_ATTR, None)
    try:
        setattr(app, _HOST_PREFIX_OWNER_ATTR, None)
    except (AttributeError, TypeError):
        pass
    return owner


def cancel_terminal_host_prefix(app) -> bool:
    """Cancel an armed host prefix, returning whether one was active."""
    return _clear_prefix_owner(app) is not None


def _arm_prefix(app, window):
    try:
        setattr(app, _HOST_PREFIX_OWNER_ATTR, window)
    except (AttributeError, TypeError):
        return False
    return True


def _pending_prefix_owner(app, active_window):
    owner = getattr(app, _HOST_PREFIX_OWNER_ATTR, None)
    if owner is None:
        return None
    if owner is not active_window or not is_terminal_input_target(owner):
        _clear_prefix_owner(app)
        return None
    return owner


def _forward_terminal_key(window, key, key_code) -> bool:
    """Encode one host key and forward it directly to the child PTY."""
    if key_code == _backtab_key_code():
        payload = "\x1b[Z"
    else:
        encoder = getattr(window, "_key_to_input", None)
        payload = encoder(key, key_code) if callable(encoder) else None
    if payload is None:
        return False
    forward = getattr(window, "_forward_payload", None)
    if not callable(forward):
        return False
    forward(payload)
    return True


def _toggle_window_menu(app, window) -> bool:
    menu = getattr(window, "window_menu", None)
    if menu is None:
        return False
    menu.active = not bool(getattr(menu, "active", False))
    if menu.active:
        if hasattr(menu, "selected_menu"):
            menu.selected_menu = 0
        if hasattr(menu, "selected_item"):
            menu.selected_item = 0
        app._active_window_menu_owner = window
    elif getattr(app, "_active_window_menu_owner", None) is window:
        app._active_window_menu_owner = None
    return True


def _call_window_method(window, name) -> bool:
    method = getattr(window, name, None)
    if not callable(method):
        return False
    method()
    return True


def _execute_app_action(app, action) -> bool:
    execute = getattr(app, "execute_action", None)
    if not callable(execute):
        return False
    execute(action)
    return True


def _handle_prefix_command(app, window, key, key_code) -> bool:
    """Consume one key after F12 as a RetroTUI host command."""
    _clear_prefix_owner(app)

    if key_code == 27:  # Escape cancels the prefix.
        return True
    if key_code == _prefix_key_code():  # F12, F12 sends a literal F12.
        _forward_terminal_key(window, key, key_code)
        return True
    if key_code == 9:  # F12, Tab changes RetroTUI window focus.
        cycle = getattr(app, "_cycle_focus", None)
        if callable(cycle):
            cycle()
        return True

    command = key.lower() if isinstance(key, str) and len(key) == 1 else None
    if command == "c":
        _call_window_method(window, "_copy_selection")
        return True
    if command == "v":
        handler = getattr(window, "handle_key", None)
        if callable(handler):
            handler(22)  # Preserve the terminal's clipboard implementation.
        return True
    if command == "i":
        _call_window_method(window, "_send_interrupt")
        return True
    if command == "k":
        _call_window_method(window, "_send_terminate")
        return True
    if command == "r":
        _call_window_method(window, "restart_session")
        return True
    if command == "m":
        _toggle_window_menu(app, window)
        return True
    if command == "x":
        _execute_app_action(app, AppAction.CLOSE_WINDOW)
        return True
    if command == "q":
        _execute_app_action(app, AppAction.EXIT)
        return True

    # An unknown command must not silently eat input. Replay the prefix itself
    # and then the current key so the child receives the original sequence.
    _forward_terminal_key(window, _prefix_key_code(), _prefix_key_code())
    _forward_terminal_key(window, key, key_code)
    return True


def handle_terminal_key_policy(app, window, key, key_code=None) -> bool:
    """Apply focused-terminal ownership before global shortcut handling.

    Returns ``True`` when the key was consumed or forwarded. The caller must
    invoke this only after modal/menu layers had a chance to consume input.
    """
    if not is_terminal_input_target(window):
        _clear_prefix_owner(app)
        return False

    if key_code is None:
        key_code = normalize_key_code(key)

    pending = _pending_prefix_owner(app, window)
    if pending is not None:
        return _handle_prefix_command(app, pending, key, key_code)

    if key_code == _prefix_key_code():
        return _arm_prefix(app, window)

    if key_code in _terminal_reserved_key_codes():
        return _forward_terminal_key(window, key, key_code)

    return False

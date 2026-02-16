"""Keyboard routing helpers for RetroTUI."""

import curses

from ..utils import normalize_key_code
from .actions import AppAction


def normalize_app_key(key):
    """Normalize key values from get_wch()/getch() into common control codes."""
    return normalize_key_code(key)


def handle_menu_hotkeys(app, key_code):
    """Handle F10 and Escape interactions for menus."""
    if key_code is None:
        return False

    if key_code == curses.KEY_F10:
        active_win = app.get_active_window()
        if active_win and active_win.window_menu:
            wm = active_win.window_menu
            wm.active = not wm.active
            if wm.active:
                wm.selected_menu = 0
                wm.selected_item = 0
            return True
        if app.menu.active:
            app.menu.active = False
        else:
            app.menu.active = True
            app.menu.selected_menu = 0
            app.menu.selected_item = 0
        return True

    if key_code == 27:
        active_win = app.get_active_window()
        if active_win and active_win.window_menu and active_win.window_menu.active:
            active_win.window_menu.active = False
        elif app.menu.active:
            app.menu.active = False
        return True

    return False


def handle_global_menu_key(app, key_code):
    """Handle keyboard navigation for the global menu."""
    if not app.menu.active:
        return False

    if key_code is None:
        return True

    action = app.menu.handle_key(key_code)
    if action:
        app.execute_action(action)
    return True


def cycle_focus(app):
    """Cycle focus through visible windows."""
    visible_windows = [w for w in app.windows if w.visible]
    if not visible_windows:
        return
    current = next((i for i, w in enumerate(visible_windows) if w.active), -1)
    next_idx = (current + 1) % len(visible_windows)
    for win in app.windows:
        win.active = False
    visible_windows[next_idx].active = True


def handle_active_window_key(app, key):
    """Delegate key input to active window."""
    active_win = app.get_active_window()
    if not active_win:
        return

    result = active_win.handle_key(key)
    app._dispatch_window_result(result, active_win)


def handle_key_event(app, key):
    """Handle keyboard input."""
    key_code = normalize_app_key(key)

    if app._handle_dialog_key(key):
        return

    if key_code == 17:  # Ctrl+Q
        app.execute_action(AppAction.EXIT)
        return

    if app._handle_menu_hotkeys(key_code):
        return

    if app._handle_global_menu_key(key_code):
        return

    if key_code == 9:  # Tab
        active_win = app.get_active_window()
        local_tab = getattr(active_win, 'handle_tab_key', None) if active_win else None
        if callable(local_tab) and local_tab():
            return
        app._cycle_focus()
        return

    app._handle_active_window_key(key)

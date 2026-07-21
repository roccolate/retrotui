"""Keyboard routing helpers for RetroTUI."""

import curses
import logging

from ..utils import normalize_key_code
from .actions import AppAction


LOGGER = logging.getLogger(__name__)


def normalize_app_key(key):
    """Normalize key values from get_wch()/getch() into common control codes."""
    return normalize_key_code(key)


def _get_active_window_menu_owner(app):
    """Return tracked window-menu owner when it is still active."""
    owner = getattr(app, "_active_window_menu_owner", None)
    if owner is None:
        return None
    menu = getattr(owner, "window_menu", None)
    if not menu or not getattr(menu, "active", False):
        app._active_window_menu_owner = None
        return None
    return owner


def _close_tracked_window_menu(app):
    """Close tracked window menu and clear owner pointer."""
    owner = _get_active_window_menu_owner(app)
    if owner is None:
        return False
    menu = getattr(owner, "window_menu", None)
    if menu is not None:
        menu.active = False
    app._active_window_menu_owner = None
    return True


def _close_context_menu(app):
    """Close global context menu when open."""
    ctx = getattr(app, "context_menu", None)
    if not ctx:
        return False
    is_open = getattr(ctx, "is_open", None)
    if callable(is_open):
        if not is_open():
            return False
    elif not getattr(ctx, "active", False):
        return False

    hide = getattr(ctx, "hide", None)
    if callable(hide):
        hide()
    else:
        ctx.active = False
    return True


def _has_any_open_menu_layer(app):
    """Return True when global/window/context menu overlays are currently open."""
    if bool(getattr(getattr(app, "menu", None), "active", False)):
        return True
    if _get_active_window_menu_owner(app) is not None:
        return True
    ctx = getattr(app, "context_menu", None)
    if not ctx:
        return False
    is_open = getattr(ctx, "is_open", None)
    if callable(is_open):
        return bool(is_open())
    return bool(getattr(ctx, "active", False))


def _handle_ctrl_q(app):
    """Apply global Ctrl+Q policy with menu-layer safety."""
    # Close transient layers first to avoid accidental session exits.
    if _close_context_menu(app):
        return True
    if _close_tracked_window_menu(app):
        return True
    if bool(getattr(getattr(app, "menu", None), "active", False)):
        app.menu.active = False
        return True

    app.execute_action(AppAction.EXIT)
    return True


def handle_menu_hotkeys(app, key_code):
    """Handle F10 and Escape interactions for menus."""
    if key_code is None:
        return False

    if key_code == curses.KEY_F10:
        active_win = app.get_active_window()
        if active_win and active_win.window_menu:
            wm = active_win.window_menu
            previous_owner = _get_active_window_menu_owner(app)
            wm.active = not wm.active
            if wm.active:
                wm.selected_menu = 0
                wm.selected_item = 0
                if previous_owner is not None and previous_owner is not active_win:
                    previous_menu = getattr(previous_owner, "window_menu", None)
                    if previous_menu is not None:
                        previous_menu.active = False
                app._active_window_menu_owner = active_win
            elif previous_owner is active_win:
                app._active_window_menu_owner = None
            return True
        if app.menu.active:
            app.menu.active = False
        else:
            _close_tracked_window_menu(app)
            app.menu.active = True
            app.menu.selected_menu = 0
            app.menu.selected_item = 0
        return True

    if key_code == 27:
        if _close_context_menu(app):
            return True
        if _close_tracked_window_menu(app):
            return True
        active_win = app.get_active_window()
        if active_win and active_win.window_menu and active_win.window_menu.active:
            active_win.window_menu.active = False
            if getattr(app, "_active_window_menu_owner", None) is active_win:
                app._active_window_menu_owner = None
            return True
        if app.menu.active:
            app.menu.active = False
            return True
        return False

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


def cycle_focus(app, *, reverse=False):
    """Cycle focus through visible windows.

    Delegates to ``set_active_window`` so the chosen window is also brought
    to the front of the z-order. Without reordering the renderer would draw
    the new active window behind the others (only its title bar attribute
    would change), confusing the user about which window is focused.
    """
    visible_windows = [w for w in app.windows if w.visible]
    if not visible_windows:
        return
    current = next((i for i, w in enumerate(visible_windows) if w.active), -1)
    step = -1 if reverse else 1
    next_idx = (current + step) % len(visible_windows)
    target = visible_windows[next_idx]
    if current >= 0:
        visible_windows[current].active = False
    target.active = True
    # Only promote to the z-order via the WindowManager when the live app
    # has one wired up AND the target window knows about ``always_on_top``
    # (a test stub that lacks it would crash inside the z-order logic).
    wm = getattr(app, "window_mgr", None)
    if wm is None or not hasattr(target, "always_on_top"):
        return
    try:
        wm.set_active_window(target)
    except (AttributeError, ValueError, TypeError):
        # Leave the target focused even if the z-order promotion failed
        # so a buggy WindowManager can't strip focus from the user.
        LOGGER.debug("cycle_focus failed to reorder z-order", exc_info=True)


def handle_active_window_key(app, key):
    """Delegate key input to active window."""
    active_win = app.get_active_window()
    if not active_win:
        return

    result = active_win.handle_key(key)
    app._dispatch_window_result(result, active_win)

    # Keep tracked window-menu owner in sync for keyboard-driven open/close.
    menu = getattr(active_win, "window_menu", None)
    if menu and getattr(menu, "active", False):
        previous_owner = _get_active_window_menu_owner(app)
        if previous_owner is not None and previous_owner is not active_win:
            previous_menu = getattr(previous_owner, "window_menu", None)
            if previous_menu is not None:
                previous_menu.active = False
        app._active_window_menu_owner = active_win
    elif getattr(app, "_active_window_menu_owner", None) is active_win:
        app._active_window_menu_owner = None


def handle_key_event(app, key):
    """Handle keyboard input."""
    key_code = normalize_app_key(key)

    if app._handle_dialog_key(key):
        return

    if app._handle_menu_hotkeys(key_code):
        return

    if app._handle_global_menu_key(key_code):
        return

    if key_code == 17:  # Ctrl+Q
        _handle_ctrl_q(app)
        return

    if key_code == 9:  # Tab
        active_win = app.get_active_window()
        local_tab = getattr(active_win, 'handle_tab_key', None) if active_win else None
        if callable(local_tab) and local_tab():
            return
        app._cycle_focus()
        return

    key_btab = getattr(curses, "KEY_BTAB", 353)
    if key_code == key_btab:  # Shift+Tab — cycle focus backward
        active_win = app.get_active_window()
        local_tab = getattr(active_win, 'handle_tab_key', None) if active_win else None
        if callable(local_tab):
            try:
                consumed = local_tab(reverse=True)
            except TypeError:
                consumed = local_tab()
            if consumed:
                return
        cycle = getattr(app, "_cycle_focus", None)
        if callable(cycle):
            try:
                cycle(reverse=True)
            except TypeError:
                cycle()
            return

    app._handle_active_window_key(key)

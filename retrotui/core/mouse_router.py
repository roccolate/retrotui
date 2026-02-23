"""Mouse routing helpers for RetroTUI."""

import curses
import inspect
import time

from ..constants import (
    DEFAULT_DOUBLE_CLICK_INTERVAL,
    MENU_BAR_HEIGHT,
    CLOCK_CLICK_REGION_WIDTH,
)
from .actions import AppAction

# Module-level curses constant masks (resolved once at import time).
_BUTTON1_CLICKED = getattr(curses, 'BUTTON1_CLICKED', 0)
_BUTTON1_PRESSED = getattr(curses, 'BUTTON1_PRESSED', 0)
_BUTTON1_RELEASED = getattr(curses, 'BUTTON1_RELEASED', 0)
_BUTTON1_DOUBLE_CLICKED = getattr(curses, 'BUTTON1_DOUBLE_CLICKED', 0)
_BUTTON3_PRESSED = getattr(curses, 'BUTTON3_PRESSED', 0)
_BUTTON3_CLICKED = getattr(curses, 'BUTTON3_CLICKED', 0)
_BUTTON3_RELEASED = getattr(curses, 'BUTTON3_RELEASED', 0)
_REPORT_MOUSE_POSITION = getattr(curses, 'REPORT_MOUSE_POSITION', 0)
_BUTTON4_PRESSED = getattr(curses, 'BUTTON4_PRESSED', 0)

_BUTTON1_CLICK_MASK = _BUTTON1_CLICKED | _BUTTON1_PRESSED | _BUTTON1_RELEASED
_BUTTON3_MASK = _BUTTON3_PRESSED | _BUTTON3_CLICKED | _BUTTON3_RELEASED

# Cache for inspect.signature arity checks (handler -> bool).
_HANDLER_ARITY_CACHE: dict = {}


def _handler_accepts_bstate(handler):
    """Return True if handler accepts 3+ positional args (mx, my, bstate)."""
    cached = _HANDLER_ARITY_CACHE.get(handler)
    if cached is not None:
        return cached
    try:
        params = list(inspect.signature(handler).parameters.values())
    except (TypeError, ValueError):
        _HANDLER_ARITY_CACHE[handler] = False
        return False
    positional = 0
    for p in params:
        if p.kind == inspect.Parameter.VAR_POSITIONAL:
            _HANDLER_ARITY_CACHE[handler] = True
            return True
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            positional += 1
    result = positional >= 3
    _HANDLER_ARITY_CACHE[handler] = result
    return result


def _invoke_mouse_handler(handler, mx, my, bstate):
    """Call mouse handlers with backward-compatible signature support."""
    if _handler_accepts_bstate(handler):
        return handler(mx, my, bstate)
    return handler(mx, my)


def _is_button1_click_event(bstate):
    """Return True for discrete button-1 click-like events (not motion reports)."""
    if bstate & _REPORT_MOUSE_POSITION:
        return False
    return bool(bstate & _BUTTON1_CLICK_MASK)


def _is_desktop_double_click(app, icon_idx, bstate):
    """Detect double-click for desktop icons with a time-based fallback."""
    if bstate & _BUTTON1_DOUBLE_CLICKED:
        return True

    if not _is_button1_click_event(bstate):
        return False

    now = time.monotonic()
    last_idx = app._last_icon_click_idx
    last_ts = app._last_icon_click_ts
    interval = app.double_click_interval or DEFAULT_DOUBLE_CLICK_INTERVAL
    is_double = (last_idx == icon_idx) and ((now - last_ts) <= interval)
    app._last_icon_click_idx = icon_idx
    app._last_icon_click_ts = now
    return is_double


def handle_file_drag_drop_mouse(app, mx, my, bstate):
    """Handle file drag-and-drop between windows."""
    return app.drag_drop.handle_mouse(mx, my, bstate)


def handle_drag_resize_mouse(app, mx, my, bstate):
    """Handle active drag or resize operations (O(1) via tracked pointers)."""
    # Drag tracking
    dragging = app._dragging_win
    if dragging is not None:
        if bstate & app.stop_drag_flags:
            dragging.dragging = False
            app._dragging_win = None
            return True
        h, w = app.stdscr.getmaxyx()
        new_x = mx - dragging.drag_offset_x
        new_y = my - dragging.drag_offset_y
        dragging.x = max(0, min(new_x, w - dragging.w))
        dragging.y = max(MENU_BAR_HEIGHT, min(new_y, h - dragging.h - 1))
        return True

    # Resize tracking
    resizing = app._resizing_win
    if resizing is not None:
        if bstate & app.stop_drag_flags:
            resizing.resizing = False
            resizing.resize_edge = None
            app._resizing_win = None
            return True
        h, w = app.stdscr.getmaxyx()
        resizing.apply_resize(mx, my, w, h)
        return True

    return False


def handle_global_menu_mouse(app, mx, my, bstate):
    """Handle mouse interaction when the global menu is active."""
    if not app.menu.active:
        return False
    if bstate & _REPORT_MOUSE_POSITION:
        app.menu.handle_hover(mx, my)
        return True
    if bstate & app.click_flags:
        action = app.menu.handle_click(mx, my)
        if action:
            app.execute_action(action)
        return True
    if app.menu.hit_test_dropdown(mx, my) or my == 0:
        return True
    return False


def handle_window_mouse(app, mx, my, bstate):
    """Route mouse events to windows in z-order."""
    click_flags = app.click_flags
    for win in reversed(app.windows):
        if not win.visible:
            continue

        if win.on_close_button(mx, my) and (bstate & click_flags):
            app.close_window(win)
            return True

        if win.on_minimize_button(mx, my) and (bstate & click_flags):
            app.set_active_window(win)
            win.toggle_minimize()
            visible = [w for w in app.windows if w.visible]
            if visible:
                app.set_active_window(visible[-1])
            return True

        if win.on_maximize_button(mx, my) and (bstate & click_flags):
            app.set_active_window(win)
            h, w = app.stdscr.getmaxyx()
            win.toggle_maximize(w, h)
            return True

        if bstate & _BUTTON1_PRESSED:
            edge = win.on_border(mx, my)
            if edge:
                win.resizing = True
                win.resize_edge = edge
                app._resizing_win = win
                app.set_active_window(win)
                return True

        if win.on_title_bar(mx, my):
            if bstate & _BUTTON1_DOUBLE_CLICKED:
                app.set_active_window(win)
                h, w = app.stdscr.getmaxyx()
                win.toggle_maximize(w, h)
                return True
            if bstate & _BUTTON1_PRESSED:
                if not win.maximized:
                    win.dragging = True
                    win.drag_offset_x = mx - win.x
                    win.drag_offset_y = my - win.y
                    app._dragging_win = win
                app.set_active_window(win)
                return True
            if bstate & _BUTTON1_CLICKED:
                app.set_active_window(win)
                return True

        if (bstate & _REPORT_MOUSE_POSITION) and win.window_menu and win.window_menu.active:
            if win.window_menu.handle_hover(mx, my, win.x, win.y, win.w):
                return True

        if win.window_menu and win.window_menu.active and not win.contains(mx, my):
            if bstate & click_flags:
                win.window_menu.active = False

        if win.contains(mx, my):
            if (bstate & _REPORT_MOUSE_POSITION) and (bstate & _BUTTON1_PRESSED):
                drag_handler = getattr(win, "handle_mouse_drag", None)
                if drag_handler is not None:
                    drag_result = _invoke_mouse_handler(drag_handler, mx, my, bstate)
                    app._dispatch_window_result(drag_result, win)
                    return True

            if bstate & click_flags:
                app.set_active_window(win)
                for other_win in app.windows:
                    other_menu = getattr(other_win, "window_menu", None)
                    if other_win is win or not other_menu or not other_menu.active:
                        continue
                    other_menu.active = False
                result = _invoke_mouse_handler(win.handle_click, mx, my, bstate)
                app._dispatch_window_result(result, win)
                return True

            if bstate & _BUTTON4_PRESSED:
                win.handle_scroll('up', 3)
                return True

            if bstate & app.scroll_down_mask:
                win.handle_scroll('down', 3)
                return True
    return False


def handle_desktop_mouse(app, mx, my, bstate):
    """Handle desktop icon interactions: selection, activation, and dragging."""
    icon_mgr = getattr(app, '_icon_mgr', None)

    # Check for drag release
    if bstate & _BUTTON1_RELEASED:
        if icon_mgr is not None and icon_mgr.is_dragging:
            icon_mgr.end_drag()
            return True

    # Check for drag motion
    is_drag_motion = bool(bstate & _BUTTON1_PRESSED) or \
                     bool((bstate & _REPORT_MOUSE_POSITION) and getattr(app, 'button1_pressed', False))

    if icon_mgr is not None and icon_mgr.is_dragging and is_drag_motion:
        icon_mgr.update_drag(mx, my)
        return True

    icon_idx = app.get_icon_at(mx, my)

    # Double click validation
    if icon_idx >= 0 and _is_desktop_double_click(app, icon_idx, bstate):
        app._last_icon_click_idx = None
        app._last_icon_click_ts = 0.0
        app.execute_action(app.icons[icon_idx]['action'])
        return True

    # Single click or drag start
    if icon_idx >= 0:
        if bstate & _BUTTON1_PRESSED:
            app.selected_icon = icon_idx
            if icon_mgr is not None:
                icon_mgr.start_drag(icon_idx, mx, my)
            return True

        elif _is_button1_click_event(bstate):
            app.selected_icon = icon_idx
            return True

    if icon_idx >= 0 and (bstate & _REPORT_MOUSE_POSITION):
        return True

    # Click on empty desktop
    if _is_button1_click_event(bstate):
        app.selected_icon = -1
        app.menu.active = False

    return True

def handle_mouse_event(app, event):
    """Handle mouse events."""
    try:
        _, mx, my, _, bstate = event
    except (TypeError, ValueError):
        return

    # Track physical button state
    if bstate & _BUTTON1_PRESSED:
        app.button1_pressed = True
    elif bstate & _BUTTON1_RELEASED:
        app.button1_pressed = False
    elif bstate & _BUTTON1_CLICKED:
        app.button1_pressed = False

    # Detect right-click (BUTTON3)
    if bstate & _BUTTON3_MASK:
        handler = getattr(app, 'handle_right_click', None)
        if callable(handler):
            try:
                handled = handler(mx, my, bstate)
            except Exception:
                handled = False
            if handled:
                return

    if app._handle_dialog_mouse(mx, my, bstate):
        return

    if handle_file_drag_drop_mouse(app, mx, my, bstate):
        return

    if my == 0 and (bstate & app.click_flags):
        action = app.menu.handle_click(mx, my)
        if action:
            app.execute_action(action)
        return

    if app._handle_drag_resize_mouse(mx, my, bstate):
        return

    if app._handle_global_menu_mouse(mx, my, bstate):
        return

    h, w = app.stdscr.getmaxyx()
    if my == h - 1 and mx >= w - CLOCK_CLICK_REGION_WIDTH:
        if bstate & (_BUTTON1_CLICKED | _BUTTON1_DOUBLE_CLICKED):
            app.execute_action(AppAction.CLOCK_CALENDAR)
            return

    if (bstate & app.click_flags) and app.handle_taskbar_click(mx, my):
        return

    if app._handle_window_mouse(mx, my, bstate):
        return

    app._handle_desktop_mouse(mx, my, bstate)

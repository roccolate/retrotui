"""Mouse routing helpers for RetroTUI."""

import curses
import inspect
import time

from ..constants import (
    DEFAULT_DOUBLE_CLICK_INTERVAL,
    MENU_BAR_HEIGHT,
    CLOCK_CLICK_REGION_WIDTH,
)


def _invoke_mouse_handler(handler, mx, my, bstate):
    """Call mouse handlers with backward-compatible signature support."""
    try:
        params = inspect.signature(handler).parameters.values()
    except (TypeError, ValueError):
        params = ()

    positional = 0
    has_varargs = False
    for param in params:
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            has_varargs = True
            break
        if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            positional += 1

    if has_varargs or positional >= 3:
        return handler(mx, my, bstate)
    return handler(mx, my)


def _is_button1_click_event(bstate):
    """Return True for discrete button-1 click-like events (not motion reports)."""
    report_flag = getattr(curses, 'REPORT_MOUSE_POSITION', 0)
    if bstate & report_flag:
        return False
    return bool(
        bstate
        & (
            getattr(curses, 'BUTTON1_CLICKED', 0)
            | getattr(curses, 'BUTTON1_PRESSED', 0)
            | getattr(curses, 'BUTTON1_RELEASED', 0)
        )
    )


def _is_desktop_double_click(app, icon_idx, bstate):
    """Detect double-click for desktop icons with a time-based fallback."""
    if bstate & getattr(curses, 'BUTTON1_DOUBLE_CLICKED', 0):
        return True

    if not _is_button1_click_event(bstate):
        return False

    now = time.monotonic()
    last_idx = getattr(app, '_last_icon_click_idx', None)
    last_ts = float(getattr(app, '_last_icon_click_ts', 0.0) or 0.0)
    interval = float(getattr(app, 'double_click_interval', DEFAULT_DOUBLE_CLICK_INTERVAL) or DEFAULT_DOUBLE_CLICK_INTERVAL)
    is_double = (last_idx == icon_idx) and ((now - last_ts) <= interval)
    setattr(app, '_last_icon_click_idx', icon_idx)
    setattr(app, '_last_icon_click_ts', now)
    return is_double


def handle_file_drag_drop_mouse(app, mx, my, bstate):
    """Handle file drag-and-drop between windows."""
    return app.drag_drop.handle_mouse(mx, my, bstate)


def handle_drag_resize_mouse(app, mx, my, bstate):
    """Handle active drag or resize operations."""
    any_dragging = any(w.dragging for w in app.windows)
    if any_dragging:
        if bstate & app.stop_drag_flags:
            for win in app.windows:
                win.dragging = False
            return True
        for win in app.windows:
            if win.dragging:
                h, w = app.stdscr.getmaxyx()
                new_x = mx - win.drag_offset_x
                new_y = my - win.drag_offset_y
                win.x = max(0, min(new_x, w - win.w))
                win.y = max(MENU_BAR_HEIGHT, min(new_y, h - win.h - 1))
                return True
        return True

    any_resizing = any(w.resizing for w in app.windows)
    if any_resizing:
        if bstate & app.stop_drag_flags:
            for win in app.windows:
                win.resizing = False
                win.resize_edge = None
            return True
        for win in app.windows:
            if win.resizing:
                h, w = app.stdscr.getmaxyx()
                win.apply_resize(mx, my, w, h)
                return True
        return True
    return False


def handle_global_menu_mouse(app, mx, my, bstate):
    """Handle mouse interaction when the global menu is active."""
    if not app.menu.active:
        return False
    if bstate & curses.REPORT_MOUSE_POSITION:
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
    for win in reversed(app.windows):
        if not win.visible:
            continue

        click_flags = app.click_flags

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

        if bstate & curses.BUTTON1_PRESSED:
            edge = win.on_border(mx, my)
            if edge:
                win.resizing = True
                win.resize_edge = edge
                app.set_active_window(win)
                return True

        if win.on_title_bar(mx, my):
            if bstate & curses.BUTTON1_DOUBLE_CLICKED:
                app.set_active_window(win)
                h, w = app.stdscr.getmaxyx()
                win.toggle_maximize(w, h)
                return True
            if bstate & curses.BUTTON1_PRESSED:
                if not win.maximized:
                    win.dragging = True
                    win.drag_offset_x = mx - win.x
                    win.drag_offset_y = my - win.y
                app.set_active_window(win)
                return True
            if bstate & curses.BUTTON1_CLICKED:
                app.set_active_window(win)
                return True

        if (bstate & curses.REPORT_MOUSE_POSITION) and win.window_menu and win.window_menu.active:
            if win.window_menu.handle_hover(mx, my, win.x, win.y, win.w):
                return True

        if win.window_menu and win.window_menu.active and not win.contains(mx, my):
            if bstate & click_flags:
                win.window_menu.active = False

        if win.contains(mx, my):
            if (bstate & curses.REPORT_MOUSE_POSITION) and (bstate & curses.BUTTON1_PRESSED) and hasattr(
                win, "handle_mouse_drag"
            ):
                drag_handler = getattr(win, "handle_mouse_drag", None)
                if callable(drag_handler):
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

            if bstate & curses.BUTTON4_PRESSED:
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
    if bstate & getattr(curses, 'BUTTON1_RELEASED', 0):
        if icon_mgr is not None and icon_mgr.is_dragging:
            icon_mgr.end_drag()
            return True

    # Check for drag motion
    is_drag_motion = bool(bstate & getattr(curses, 'BUTTON1_PRESSED', 0)) or \
                     bool((bstate & getattr(curses, 'REPORT_MOUSE_POSITION', 0)) and getattr(app, 'button1_pressed', False))

    if icon_mgr is not None and icon_mgr.is_dragging and is_drag_motion:
        icon_mgr.update_drag(mx, my)
        return True

    icon_idx = app.get_icon_at(mx, my)

    # Double click validation
    if icon_idx >= 0 and _is_desktop_double_click(app, icon_idx, bstate):
        setattr(app, '_last_icon_click_idx', None)
        setattr(app, '_last_icon_click_ts', 0.0)
        app.execute_action(app.icons[icon_idx]['action'])
        return True

    # Single click or drag start
    if icon_idx >= 0:
        if bstate & getattr(curses, 'BUTTON1_PRESSED', 0):
            app.selected_icon = icon_idx
            if icon_mgr is not None:
                icon_mgr.start_drag(icon_idx, mx, my)
            return True

        elif _is_button1_click_event(bstate):
            app.selected_icon = icon_idx
            return True

    if icon_idx >= 0 and (bstate & getattr(curses, 'REPORT_MOUSE_POSITION', 0)):
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
    if bstate & getattr(curses, 'BUTTON1_PRESSED', 0):
        app.button1_pressed = True
    elif bstate & getattr(curses, 'BUTTON1_RELEASED', 0):
        app.button1_pressed = False
    elif bstate & getattr(curses, 'BUTTON1_CLICKED', 0):
        app.button1_pressed = False

    # Detect right-click (BUTTON3) and consult app-level handler if present.
    button3_flags = (
        getattr(curses, 'BUTTON3_PRESSED', 0)
        | getattr(curses, 'BUTTON3_CLICKED', 0)
        | getattr(curses, 'BUTTON3_RELEASED', 0)
    )
    if bstate & button3_flags:
        handler = getattr(app, 'handle_right_click', None)  # Changed from _handle_right_click to handle_right_click
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

    from .actions import AppAction
    h, w = app.stdscr.getmaxyx()
    if my == h - 1 and mx >= w - CLOCK_CLICK_REGION_WIDTH:
        if bstate & (getattr(curses, 'BUTTON1_CLICKED', 0) | getattr(curses, 'BUTTON1_DOUBLE_CLICKED', 0)):
            app.execute_action(AppAction.CLOCK_CALENDAR)
            return

    if (bstate & app.click_flags) and app.handle_taskbar_click(mx, my):
        return

    if app._handle_window_mouse(mx, my, bstate):
        return

    app._handle_desktop_mouse(mx, my, bstate)

"""Mouse routing helpers for RetroTUI."""

import curses
import inspect
import logging
import os
import time

from ..constants import (
    DEFAULT_DOUBLE_CLICK_INTERVAL,
    MENU_BAR_HEIGHT,
    CLOCK_CLICK_REGION_WIDTH,
)
from .actions import AppAction
from .platform.mouse_backend import normalize_mouse_payload

LOGGER = logging.getLogger(__name__)

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

# Enable detailed mouse normalization traces only when debug mode is explicitly on.
_TRACE_MOUSE = bool(os.environ.get("RETROTUI_DEBUG"))
_TRACE_MOUSE_MIN_INTERVAL = float(os.environ.get("RETROTUI_MOUSE_TRACE_MIN_INTERVAL", "0.05"))
_TRACE_MOUSE_LAST_TS = {"value": 0.0}


def _trace_mouse_normalization(raw_event, norm, adjusted_bstate):
    """Emit compact debug traces for raw-to-normalized mouse events."""
    if not _TRACE_MOUSE:
        return
    if not LOGGER.isEnabledFor(logging.DEBUG):
        return
    now = time.monotonic()
    if _TRACE_MOUSE_MIN_INTERVAL > 0:
        elapsed = now - _TRACE_MOUSE_LAST_TS["value"]
        if elapsed < _TRACE_MOUSE_MIN_INTERVAL:
            return
    _TRACE_MOUSE_LAST_TS["value"] = now
    LOGGER.debug(
        "mouse raw=%r backend=%s pos=(%s,%s) bstate=0x%x adjusted=0x%x "
        "click=%s right=%s drag=%s motion=%s passive=%s inferred_motion=%s inferred_right=%s",
        raw_event,
        norm.get("backend"),
        norm.get("mx"),
        norm.get("my"),
        int(norm.get("bstate") or 0),
        int(adjusted_bstate or 0),
        bool(norm.get("is_click_like")),
        bool(norm.get("right_click")),
        bool(norm.get("is_drag")),
        bool(norm.get("is_motion")),
        bool(norm.get("is_passive_noop")),
        bool(norm.get("inferred_motion")),
        bool(norm.get("inferred_right_click")),
    )


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
    interval = getattr(app, "double_click_interval", None) or DEFAULT_DOUBLE_CLICK_INTERVAL
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


def handle_window_mouse(app, mx, my, bstate, norm=None):
    """Route mouse events to windows in z-order."""
    if norm is not None:
        is_click_like = bool(norm.get("is_click_like"))
        is_button1_pressed = bool(norm.get("button1_pressed"))
        is_button1_clicked = bool(norm.get("button1_clicked"))
        is_button1_double = bool(norm.get("button1_double"))
        is_mouse_motion = bool(norm.get("is_motion"))
        scroll_up = bool(norm.get("scroll_up"))
        scroll_down = bool(norm.get("scroll_down"))
    else:
        click_flags = app.click_flags
        is_click_like = bool(bstate & click_flags)
        is_button1_pressed = bool(bstate & _BUTTON1_PRESSED)
        is_button1_clicked = bool(bstate & _BUTTON1_CLICKED)
        is_button1_double = bool(bstate & _BUTTON1_DOUBLE_CLICKED)
        is_mouse_motion = bool(bstate & _REPORT_MOUSE_POSITION)
        scroll_up = bool(bstate & _BUTTON4_PRESSED)
        scroll_down = bool(bstate & app.scroll_down_mask)

    for win in reversed(app.windows):
        if not win.visible:
            continue

        if is_click_like and win.on_close_button(mx, my):
            app.close_window(win)
            return True

        if is_click_like and win.on_minimize_button(mx, my):
            app.set_active_window(win)
            win.toggle_minimize()
            visible = [w for w in app.windows if w.visible]
            if visible:
                app.set_active_window(visible[-1])
            return True

        if is_click_like and win.on_maximize_button(mx, my):
            app.set_active_window(win)
            h, w = app.stdscr.getmaxyx()
            win.toggle_maximize(w, h)
            return True

        if is_button1_pressed:
            edge = win.on_border(mx, my)
            if edge:
                win.resizing = True
                win.resize_edge = edge
                app._resizing_win = win
                app.set_active_window(win)
                return True

        if (is_button1_pressed or is_button1_clicked or is_button1_double) and win.on_title_bar(mx, my):
            if is_button1_double:
                app.set_active_window(win)
                h, w = app.stdscr.getmaxyx()
                win.toggle_maximize(w, h)
                return True
            if is_button1_pressed:
                if not win.maximized:
                    win.dragging = True
                    win.drag_offset_x = mx - win.x
                    win.drag_offset_y = my - win.y
                    app._dragging_win = win
                app.set_active_window(win)
                return True
            if is_button1_clicked:
                app.set_active_window(win)
                return True

        if is_mouse_motion and win.window_menu and win.window_menu.active:
            if win.window_menu.handle_hover(mx, my, win.x, win.y, win.w):
                return True

        if win.window_menu and win.window_menu.active and not win.contains(mx, my):
            if is_click_like:
                win.window_menu.active = False

        if win.contains(mx, my):
            if is_mouse_motion and is_button1_pressed:
                drag_handler = getattr(win, "handle_mouse_drag", None)
                if drag_handler is not None:
                    drag_result = _invoke_mouse_handler(drag_handler, mx, my, bstate)
                    app._dispatch_window_result(drag_result, win)
                    return True

            if is_click_like:
                app.set_active_window(win)
                for other_win in app.windows:
                    other_menu = getattr(other_win, "window_menu", None)
                    if other_win is win or not other_menu or not other_menu.active:
                        continue
                    other_menu.active = False
                result = _invoke_mouse_handler(win.handle_click, mx, my, bstate)
                app._dispatch_window_result(result, win)
                return True

            if scroll_up:
                win.handle_scroll('up', 3)
                return True

            if scroll_down:
                win.handle_scroll('down', 3)
                return True
    return False


def handle_desktop_mouse(app, mx, my, bstate, norm=None):
    """Handle desktop icon interactions: selection, activation, and dragging."""
    icon_mgr = getattr(app, '_icon_mgr', None)

    if norm is not None:
        is_button1_released = bool(norm.get("button1_released"))
        is_button1_pressed = bool(norm.get("button1_pressed"))
        is_drag_motion = bool(norm.get("is_drag"))
        is_mouse_motion = bool(norm.get("is_motion"))
    else:
        is_button1_released = bool(bstate & _BUTTON1_RELEASED)
        is_button1_pressed = bool(bstate & _BUTTON1_PRESSED)
        is_drag_motion = bool(bstate & _BUTTON1_PRESSED) or bool(
            (bstate & _REPORT_MOUSE_POSITION) and getattr(app, 'button1_pressed', False)
        )
        is_mouse_motion = bool(bstate & _REPORT_MOUSE_POSITION)

    # Check for drag release
    if is_button1_released:
        if icon_mgr is not None and icon_mgr.is_dragging:
            icon_mgr.end_drag()
            return True

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
        if is_button1_pressed:
            app.selected_icon = icon_idx
            if icon_mgr is not None:
                icon_mgr.start_drag(icon_idx, mx, my)
            return True

        elif _is_button1_click_event(bstate):
            app.selected_icon = icon_idx
            return True

    if icon_idx >= 0 and is_mouse_motion:
        return True

    # Click on empty desktop
    if _is_button1_click_event(bstate):
        app.selected_icon = -1
        app.menu.active = False

    return True

def handle_mouse_event(app, event):
    """Handle mouse events.

    Returns True when the event likely changed UI state and should trigger redraw.
    """
    norm = normalize_mouse_payload(app, event)
    if norm is None:
        return False
    mx = norm["mx"]
    my = norm["my"]
    bstate = norm["bstate"]
    app._last_mouse_pos = (mx, my)
    app._mouse_norm = norm

    if norm["inferred_motion"]:
        bstate |= _REPORT_MOUSE_POSITION
    if norm["inferred_right_click"]:
        bstate |= _BUTTON3_CLICKED
    _trace_mouse_normalization(event, norm, bstate)

    # Track physical button state
    if norm.get("button1_pressed"):
        app.button1_pressed = True
    elif norm.get("button1_released"):
        app.button1_pressed = False
    elif norm.get("button1_clicked"):
        app.button1_pressed = False

    # Detect right-click.
    if norm.get("right_click"):
        handler = getattr(app, 'handle_right_click', None)
        if callable(handler):
            try:
                handled = handler(mx, my, bstate)
            except Exception:
                handled = False
            if handled:
                return True

    if app._handle_dialog_mouse(mx, my, bstate):
        return True

    if handle_file_drag_drop_mouse(app, mx, my, bstate):
        return True

    if my == 0 and norm.get("is_click_like"):
        action = app.menu.handle_click(mx, my)
        if action:
            app.execute_action(action)
        return True

    if app._handle_drag_resize_mouse(mx, my, bstate):
        return True

    if app._handle_global_menu_mouse(mx, my, bstate):
        return True

    h, w = app.stdscr.getmaxyx()
    if my == h - 1 and mx >= w - CLOCK_CLICK_REGION_WIDTH:
        if norm.get("button1_clicked") or norm.get("button1_double"):
            app.execute_action(AppAction.CLOCK_CALENDAR)
            return True

    if norm.get("is_click_like") and app.handle_taskbar_click(mx, my):
        return True

    if app._handle_window_mouse(mx, my, bstate):
        return True

    # Passive pointer motion with no button/scroll/click semantics is a no-op.
    if norm.get("is_passive_noop"):
        return False

    return bool(app._handle_desktop_mouse(mx, my, bstate))

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
_CURSES_ERROR = getattr(curses, "error", Exception)

_MOUSE_ROUTE_ERRORS = (
    AttributeError,
    LookupError,
    OSError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)

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

_BUTTON1_CLICK_MASK = _BUTTON1_CLICKED | _BUTTON1_PRESSED | _BUTTON1_DOUBLE_CLICKED
_BUTTON3_MASK = _BUTTON3_PRESSED | _BUTTON3_CLICKED | _BUTTON3_RELEASED

# Cache for inspect.signature arity checks keyed by stable callable identity.
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


def _handler_cache_key(handler):
    """Return a stable key for callable arity cache lookups."""
    bound_func = getattr(handler, "__func__", None)
    if bound_func is not None:
        owner = getattr(handler, "__self__", None)
        return (bound_func, getattr(owner, "__class__", None))
    return handler


def _handler_accepts_bstate(handler):
    """Return True if handler accepts 3+ positional args (mx, my, bstate)."""
    cache_key = _handler_cache_key(handler)
    cached = _HANDLER_ARITY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        params = list(inspect.signature(handler).parameters.values())
    except (TypeError, ValueError):
        _HANDLER_ARITY_CACHE[cache_key] = False
        return False
    positional = 0
    for p in params:
        if p.kind == inspect.Parameter.VAR_POSITIONAL:
            _HANDLER_ARITY_CACHE[cache_key] = True
            return True
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            positional += 1
    result = positional >= 3
    _HANDLER_ARITY_CACHE[cache_key] = result
    return result


def _invoke_mouse_handler(handler, mx, my, bstate):
    """Call mouse handlers with backward-compatible signature support."""
    if _handler_accepts_bstate(handler):
        return handler(mx, my, bstate)
    return handler(mx, my)


def _get_active_window_menu_owner(app):
    """Return tracked window-menu owner when its menu is currently active."""
    owner = getattr(app, "_active_window_menu_owner", None)
    if owner is None:
        return None
    menu = getattr(owner, "window_menu", None)
    if not menu or not getattr(menu, "active", False):
        app._active_window_menu_owner = None
        return None
    if not getattr(owner, "visible", False):
        menu.active = False
        app._active_window_menu_owner = None
        return None
    return owner


def _close_tracked_window_menu(app, *, except_win=None):
    """Close tracked window menu unless it belongs to *except_win*."""
    owner = _get_active_window_menu_owner(app)
    if owner is None or owner is except_win:
        return False
    menu = getattr(owner, "window_menu", None)
    if menu is not None:
        menu.active = False
    app._active_window_menu_owner = None
    return True


def _sync_window_menu_owner(app, win):
    """Update tracked owner based on clicked/handled window menu state."""
    menu = getattr(win, "window_menu", None)
    if menu and getattr(menu, "active", False):
        _close_tracked_window_menu(app, except_win=win)
        app._active_window_menu_owner = win
    elif getattr(app, "_active_window_menu_owner", None) is win:
        app._active_window_menu_owner = None


def _clear_window_text_selection(app):
    """Clear text selection state for windows that expose selection helpers."""
    cleared_any = False
    for win in getattr(app, "windows", []):
        clear_selection = getattr(win, "clear_selection", None)
        if not callable(clear_selection):
            continue

        has_state = False
        has_selection = getattr(win, "has_selection", None)
        if callable(has_selection):
            try:
                has_state = bool(has_selection())
            except _MOUSE_ROUTE_ERRORS:
                has_state = False

        if (
            has_state
            or getattr(win, "selection_anchor", None) is not None
            or getattr(win, "selection_cursor", None) is not None
            or bool(getattr(win, "_mouse_selecting", False))
        ):
            try:
                clear_selection()
            except _MOUSE_ROUTE_ERRORS:
                LOGGER.debug("selection clear failed", exc_info=True)
                continue
            cleared_any = True
    return cleared_any


def _title_bar_hit(win, mx, my, norm=None):
    """Return True when pointer should be treated as a title-bar hit.

    In some TTY/GPM streams the reported y coordinate lands one row below
    the visual title bar. We accept that offset only for gpm/fallback backends
    and only on windows without a menu bar to avoid menu-row ambiguity.
    """
    on_title = getattr(win, "on_title_bar", None)
    if callable(on_title) and on_title(mx, my):
        return True

    if norm is None:
        return False
    backend = str(norm.get("backend") or "").lower()
    if backend not in {"gpm", "fallback"}:
        return False
    if getattr(win, "window_menu", None) is not None:
        return False

    wx = int(getattr(win, "x", 0))
    wy = int(getattr(win, "y", 0))
    ww = int(getattr(win, "w", 0))
    if ww <= 0 or my != wy + 1:
        return False
    if mx < wx + 1 or mx > wx + ww - 2:
        return False
    min_btn_offset = int(getattr(win, "MIN_BTN_OFFSET", 10))
    if mx >= wx + ww - min_btn_offset:
        return False
    return True


def _route_selection_drag_owner(app, mx, my, bstate, *, is_mouse_motion, is_button1_pressed):
    """Keep selection drag captured by the window that initiated it.

    Without capture, pointer motion outside window bounds can leak into desktop
    routing (icon/desktop selection) while selecting text in app windows.
    """
    if not (is_mouse_motion and is_button1_pressed):
        return False

    for win in reversed(app.windows):
        if not getattr(win, "visible", False):
            continue
        if not bool(getattr(win, "_mouse_selecting", False)):
            continue
        drag_handler = getattr(win, "handle_mouse_drag", None)
        if drag_handler is None:
            return True
        drag_result = _invoke_mouse_handler(drag_handler, mx, my, bstate)
        app._dispatch_window_result(drag_result, win)
        return True
    return False


def _pointer_capture_owner(app):
    """Return currently captured pointer owner as `(kind, owner)` or `(None, None)`."""
    dragging = getattr(app, "_dragging_win", None)
    if dragging is not None:
        return ("window_drag", dragging)

    resizing = getattr(app, "_resizing_win", None)
    if resizing is not None:
        return ("window_resize", resizing)

    drag_drop = getattr(app, "drag_drop", None)
    if drag_drop is not None and getattr(drag_drop, "payload", None) is not None:
        return ("file_drag", drag_drop)

    icon_mgr = getattr(app, "_icon_mgr", None)
    if icon_mgr is not None and bool(getattr(icon_mgr, "is_dragging", False)):
        return ("icon_drag", icon_mgr)

    # Selection capture applies only while primary button is physically down.
    if not bool(getattr(app, "button1_pressed", False)):
        return (None, None)
    for win in reversed(getattr(app, "windows", ())):
        if not getattr(win, "visible", False):
            continue
        if bool(getattr(win, "_mouse_selecting", False)):
            return ("window_selection", win)

    return (None, None)


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

    if _route_selection_drag_owner(
        app,
        mx,
        my,
        bstate,
        is_mouse_motion=is_mouse_motion,
        is_button1_pressed=is_button1_pressed,
    ):
        return True

    active_menu_owner = _get_active_window_menu_owner(app)
    if is_mouse_motion and active_menu_owner is not None:
        active_menu = getattr(active_menu_owner, "window_menu", None)
        if active_menu and active_menu.handle_hover(mx, my, active_menu_owner.x, active_menu_owner.y, active_menu_owner.w):
            return True

    if is_click_like and active_menu_owner is not None:
        owner_contains = getattr(active_menu_owner, "contains", None)
        if callable(owner_contains) and not owner_contains(mx, my):
            active_menu = getattr(active_menu_owner, "window_menu", None)
            if active_menu is not None:
                active_menu.active = False
            if getattr(app, "_active_window_menu_owner", None) is active_menu_owner:
                app._active_window_menu_owner = None

    for win in reversed(app.windows):
        if not win.visible:
            continue

        if is_click_like and win.on_close_button(mx, my):
            if getattr(app, "_active_window_menu_owner", None) is win:
                app._active_window_menu_owner = None
            app.close_window(win)
            return True

        if is_click_like and win.on_minimize_button(mx, my):
            app.set_active_window(win)
            if getattr(app, "_active_window_menu_owner", None) is win:
                menu = getattr(win, "window_menu", None)
                if menu is not None:
                    menu.active = False
                app._active_window_menu_owner = None
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

        if (is_button1_pressed or is_button1_clicked or is_button1_double) and _title_bar_hit(win, mx, my, norm=norm):
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

        if win.contains(mx, my):
            if is_mouse_motion and is_button1_pressed:
                drag_handler = getattr(win, "handle_mouse_drag", None)
                if drag_handler is not None:
                    drag_result = _invoke_mouse_handler(drag_handler, mx, my, bstate)
                    app._dispatch_window_result(drag_result, win)
                    return True

            if is_click_like:
                app.set_active_window(win)
                _close_tracked_window_menu(app, except_win=win)
                result = _invoke_mouse_handler(win.handle_click, mx, my, bstate)
                app._dispatch_window_result(result, win)
                _sync_window_menu_owner(app, win)
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
        is_button1_down = bool(norm.get("button1_down"))
        is_drag_motion = bool(norm.get("is_drag"))
        is_mouse_motion = bool(norm.get("is_motion"))
    else:
        is_button1_released = bool(bstate & _BUTTON1_RELEASED)
        is_button1_pressed = bool(bstate & _BUTTON1_PRESSED)
        is_button1_down = is_button1_pressed or bool(getattr(app, "button1_pressed", False))
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
        if is_button1_pressed or (is_button1_down and is_drag_motion):
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
    # Keep drag-selection usable on backends that omit BUTTON1_PRESSED during motion.
    if norm.get("is_motion") and norm.get("button1_down"):
        bstate |= _BUTTON1_PRESSED
        norm["button1_pressed"] = True
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

    if app._handle_dialog_mouse(mx, my, bstate):
        return True

    # Detect right-click only after modal dialogs had a chance to consume input.
    if norm.get("right_click"):
        handler = getattr(app, 'handle_right_click', None)
        if callable(handler):
            try:
                handled = handler(mx, my, bstate)
            except _MOUSE_ROUTE_ERRORS:
                LOGGER.debug("right-click handler failed", exc_info=True)
                handled = False
            if handled:
                return True

    capture_kind, _capture_owner = _pointer_capture_owner(app)
    if capture_kind in {"window_drag", "window_resize"}:
        if app._handle_drag_resize_mouse(mx, my, bstate):
            return True
    elif capture_kind == "window_selection":
        if app._handle_window_mouse(mx, my, bstate):
            return True
    elif capture_kind == "icon_drag":
        return bool(app._handle_desktop_mouse(mx, my, bstate))

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

    # Clicking outside all windows should cancel active text selections.
    if norm.get("button1_pressed") or norm.get("button1_clicked") or norm.get("button1_double"):
        _clear_window_text_selection(app)

    # Passive pointer motion with no button/scroll/click semantics is a no-op.
    if norm.get("is_passive_noop"):
        return False

    return bool(app._handle_desktop_mouse(mx, my, bstate))

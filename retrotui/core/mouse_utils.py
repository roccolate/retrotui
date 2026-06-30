"""Mouse routing utility functions: arity inspection, hit testing,
capture ownership, selection state, and event classification predicates."""

import curses
import inspect
import logging
import time

from ..constants import DEFAULT_DOUBLE_CLICK_INTERVAL, _CURSES_ERROR

LOGGER = logging.getLogger(__name__)

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
_REPORT_MOUSE_POSITION = getattr(curses, 'REPORT_MOUSE_POSITION', 0)

_BUTTON1_CLICK_MASK = _BUTTON1_CLICKED | _BUTTON1_PRESSED | _BUTTON1_DOUBLE_CLICKED

# Cache for inspect.signature arity checks keyed by stable callable identity.
_HANDLER_ARITY_CACHE: dict = {}

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
    # A closed window may still be referenced here if its ``close()``
    # raised: ``WindowManager.close_window`` clears the owner when the
    # close succeeds, but we want a defensive sweep on every consumer
    # access so a stale reference is recovered without waiting for the
    # next mouse event that happens to mention ``win.close()``.
    try:
        in_windows = owner in getattr(app, "windows", ())
    except TypeError:
        in_windows = True
    if not in_windows:
        menu.active = False
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


def _clear_selection_capture_state(app):
    """Drop transient selection-capture flags after release-like events."""
    for win in getattr(app, "windows", []):
        if bool(getattr(win, "_mouse_selecting", False)):
            win._mouse_selecting = False


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


def _find_selecting_window(app):
    """Return the window with ``_mouse_selecting`` set, or None.

    Caches the result on the app so subsequent calls (on every
    mouse motion event) are O(1) instead of walking
    ``app.windows``. The cache is invalidated when the flag is
    cleared by a window setting ``_mouse_selecting = False``
    directly (callers should prefer ``_set_mouse_selecting``).
    """
    cached = getattr(app, "_mouse_selecting_window", None)
    if cached is not None and bool(getattr(cached, "_mouse_selecting", False)):
        return cached
    found = None
    for candidate in reversed(getattr(app, "windows", ())):
        if bool(getattr(candidate, "_mouse_selecting", False)):
            found = candidate
            break
    try:
        app._mouse_selecting_window = found
    except (AttributeError, TypeError):
        # Stubs that don't allow attr set still work — the next
        # call will re-scan.
        pass
    return found


def _route_selection_drag_owner(app, mx, my, bstate, *, is_mouse_motion, is_button1_pressed, norm=None):
    """Keep selection drag captured by the window that initiated it."""
    if not (is_mouse_motion and is_button1_pressed):
        return False

    win = _find_selecting_window(app)
    if win is None:
        return False

    if not getattr(win, "visible", False):
        return False

    contains = getattr(win, "contains", None)
    pointer_inside = False
    if callable(contains):
        try:
            pointer_inside = bool(contains(mx, my))
        except _MOUSE_ROUTE_ERRORS:
            pointer_inside = False

    raw_pressed = bool((norm or {}).get("button1_pressed_raw"))
    if not pointer_inside and not raw_pressed:
        win._mouse_selecting = False
        try:
            app._mouse_selecting_window = None
        except (AttributeError, TypeError):
            pass
        return False

    drag_handler = getattr(win, "handle_mouse_drag", None)
    if drag_handler is None:
        return True
    drag_result = _invoke_mouse_handler(drag_handler, mx, my, bstate)
    app._dispatch_window_result(drag_result, win)
    return True


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

    if not bool(getattr(app, "button1_pressed", False)):
        return (None, None)
    # O(1) cached pointer for the selection-drag owner. Falls back to
    # a single linear scan when the cache is stale (e.g. tests that
    # set ``_mouse_selecting`` directly).
    win = _find_selecting_window(app)
    if win is not None:
        return ("window_selection", win)

    return (None, None)


def _is_button1_click_event(bstate):
    """Return True for discrete button-1 click-like events (not motion reports)."""
    if bstate & _REPORT_MOUSE_POSITION:
        return False
    return bool(bstate & _BUTTON1_CLICK_MASK)


def _is_release_like_stop_event(app, bstate, norm=None):
    """Return True when drag/resize/file-drop should stop for current mouse event."""
    if norm is not None:
        if bool(norm.get("button1_released")):
            return True
        if not bool(norm.get("is_motion")) and bool(
            norm.get("button1_clicked") or norm.get("button1_double")
        ):
            return True
        return False
    return bool(bstate & getattr(app, "stop_drag_flags", 0))


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

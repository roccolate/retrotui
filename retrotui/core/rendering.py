"""Rendering helpers for RetroTUI."""

import curses

from ..constants import (
    C_DESKTOP,
    C_ICON,
    C_ICON_SEL,
    C_STATUS,
    C_TASKBAR,
    DESKTOP_PATTERN,
    TASKBAR_TITLE_MAX_LEN,
    ICON_ART_HEIGHT,
    MENU_BAR_HEIGHT,
    BOTTOM_BARS_HEIGHT,
)
from ..utils import safe_addstr, theme_attr

# Cache for desktop pattern line to avoid rebuilding every frame.
_desktop_line_cache = {'key': None, 'line': ''}


def _frame_size(app):
    size = getattr(app, "_frame_size", None)
    if isinstance(size, tuple) and len(size) == 2:
        return size
    return app.stdscr.getmaxyx()


def _resolve_frame_size(app, frame_size):
    if isinstance(frame_size, tuple) and len(frame_size) == 2:
        return frame_size
    return _frame_size(app)


def _taskbar_row(frame_h):
    return frame_h - BOTTOM_BARS_HEIGHT if BOTTOM_BARS_HEIGHT else 0


def _taskbar_bounds(app, width):
    if BOTTOM_BARS_HEIGHT:
        return 1, width

    menu = getattr(app, "menu", None)
    start_x = 1
    menu_right = getattr(menu, "menu_items_right_x", None)
    if callable(menu_right):
        try:
            start_x = max(start_x, int(menu_right()) + 2)
        except (TypeError, ValueError):
            start_x = 1

    end_x = width
    reserved = getattr(menu, "right_reserved_start_x", None)
    if callable(reserved):
        try:
            end_x = min(end_x, max(start_x, int(reserved(width)) - 1))
        except (TypeError, ValueError):
            end_x = width
    return start_x, end_x


def _window_stats(app):
    """Return cached per-frame window stats used by shell bar rendering."""
    window_mgr = getattr(app, "window_mgr", None)
    if window_mgr is not None and hasattr(window_mgr, "window_stats"):
        stats = window_mgr.window_stats()
        return {
            "total": int(stats.get("total", 0)),
            "visible": int(stats.get("visible", 0)),
            "minimized_labels": list(stats.get("minimized_labels", ())),
        }

    cycle = getattr(app, "_render_cycle_id", None)
    cache_cycle = getattr(app, "_render_stats_cycle_id", None)
    cached = getattr(app, "_render_window_stats", None)
    if cycle is not None and cache_cycle == cycle and isinstance(cached, dict):
        return cached

    windows = list(getattr(app, "windows", ()))
    minimized_labels = []
    visible_count = 0
    for win in windows:
        if getattr(win, "visible", False):
            visible_count += 1
        if getattr(win, "minimized", False):
            title = str(getattr(win, "title", ""))
            minimized_labels.append(title[:TASKBAR_TITLE_MAX_LEN])

    stats = {
        "total": len(windows),
        "visible": visible_count,
        "minimized_labels": minimized_labels,
    }
    if cycle is not None:
        app._render_window_stats = stats
        app._render_stats_cycle_id = cycle
    return stats


def _taskbar_buttons(app, width, stats=None, *, start_x=None, end_x=None):
    """Return taskbar button layout as `(start_x, end_x, label, win)` tuples."""
    window_mgr = getattr(app, "window_mgr", None)
    if window_mgr is not None and hasattr(window_mgr, "taskbar_buttons"):
        try:
            return tuple(
                window_mgr.taskbar_buttons(width, start_x=start_x, end_x=end_x)
            )
        except TypeError:
            return tuple(window_mgr.taskbar_buttons(width))

    if stats is None:
        stats = _window_stats(app)

    if start_x is None or end_x is None:
        start_x, end_x = _taskbar_bounds(app, width)

    x = start_x
    buttons = []
    for label in stats["minimized_labels"]:
        btn_w = len(label) + 2  # [label]
        if x + btn_w > end_x:
            break
        buttons.append((x, x + btn_w, label, None))
        x += btn_w + 1
    return tuple(buttons)


def draw_desktop(app, frame_size=None):
    """Draw the desktop background pattern."""
    h, w = _resolve_frame_size(app, frame_size)
    bounds = (h, w)
    attr = theme_attr("desktop")
    pattern = getattr(getattr(app, "theme", None), "desktop_pattern", DESKTOP_PATTERN)

    # Reuse cached line when width and pattern haven't changed.
    cache_key = (w, pattern)
    if _desktop_line_cache['key'] != cache_key:
        _desktop_line_cache['line'] = (pattern * (w // len(pattern) + 1))[:w]
        _desktop_line_cache['key'] = cache_key
    line = _desktop_line_cache['line']

    for row in range(MENU_BAR_HEIGHT, h - BOTTOM_BARS_HEIGHT):
        safe_addstr(app.stdscr, row, 0, line, attr, _bounds=bounds)


def draw_icons(app, frame_size=None):
    """Draw desktop icons (3x4 art + label)."""
    h, w = _resolve_frame_size(app, frame_size)
    bounds = (h, w)
    get_pos = app.get_icon_screen_pos
    # Backwards compat with mock/test stubs that don't accept the
    # ``frame_size`` kwarg. Cached on the app after the first call so we
    # don't pay ``inspect.signature`` per redraw.
    accepts_frame_size = getattr(app, "_get_pos_accepts_frame_size", None)
    if accepts_frame_size is None:
        try:
            import inspect
            accepts_frame_size = "frame_size" in inspect.signature(get_pos).parameters
        except (TypeError, ValueError):
            accepts_frame_size = False
        try:
            app._get_pos_accepts_frame_size = accepts_frame_size
        except (AttributeError, TypeError):
            # Stubs that don't allow attr set still get a working
            # fallback path.
            pass
    for idx, icon in enumerate(app.icons):
        # Use dynamic position helper
        if accepts_frame_size:
            x, y = get_pos(idx, frame_size=frame_size)
        else:
            x, y = get_pos(idx)

        symbol = icon.get("symbol")
        if isinstance(symbol, str) and symbol:
            art_lines = [symbol]
        else:
            art = icon.get("art", ())
            art_lines = [str(line) for line in art] if isinstance(art, (list, tuple)) else []
            if not art_lines:
                art_lines = ["[]"]

        art_height = len(art_lines)
        art_width = max((len(line) for line in art_lines), default=2)
        render_height = max(ICON_ART_HEIGHT, art_height)

        # Clip if off-screen (y)
        if y + render_height >= h - BOTTOM_BARS_HEIGHT:
            continue

        is_selected = idx == app.selected_icon
        attr = theme_attr("icon_selected" if is_selected else "icon")
        if is_selected:
            attr |= curses.A_BOLD

        for row, line in enumerate(art_lines):
            safe_addstr(app.stdscr, y + row, x, line, attr, _bounds=bounds)
        label = str(icon.get("label", "")).center(max(art_width, 2))
        safe_addstr(app.stdscr, y + render_height, x, label, attr, _bounds=bounds)


def draw_taskbar(app, frame_size=None):
    """Draw minimized window buttons on the shell bar."""
    h, w = _resolve_frame_size(app, frame_size)
    bounds = (h, w)
    taskbar_y = _taskbar_row(h)
    attr = theme_attr("taskbar" if BOTTOM_BARS_HEIGHT else "menubar")

    if BOTTOM_BARS_HEIGHT:
        safe_addstr(app.stdscr, taskbar_y, 0, ' ' * w, attr, _bounds=bounds)

    stats = _window_stats(app)
    start_x, end_x = _taskbar_bounds(app, w)
    buttons = _taskbar_buttons(app, w, stats=stats, start_x=start_x, end_x=end_x)
    for start_x, _end_x, label, _win in buttons:
        safe_addstr(app.stdscr, taskbar_y, start_x, f'[{label}]', attr | curses.A_BOLD, _bounds=bounds)


def draw_statusbar(app, version, frame_size=None):
    """Draw legacy bottom status text when a separate bottom bar exists."""
    if not BOTTOM_BARS_HEIGHT:
        return
    h, w = _resolve_frame_size(app, frame_size)
    attr = theme_attr("taskbar")
    stats = _window_stats(app)
    visible = stats["visible"]
    total = stats["total"]
    status_text = f' RetroTUI v{version} | Windows: {visible}/{total} | Mouse: Enabled '

    statusbar_y = _taskbar_row(h)
    start_x, end_x = _taskbar_bounds(app, w)
    buttons = _taskbar_buttons(app, w, stats=stats, start_x=start_x, end_x=end_x)
    left_reserved = buttons[-1][1] + 1 if buttons else 0

    status_x = left_reserved + 1
    max_status_len = w - status_x
    if max_status_len <= 0:
        return
    safe_addstr(app.stdscr, statusbar_y, status_x, status_text[:max_status_len], attr, _bounds=(h, w))

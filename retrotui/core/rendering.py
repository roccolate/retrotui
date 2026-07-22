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
from ..utils import center_text_columns, safe_addstr, theme_attr
from .icon_manager import icon_render_metrics
from .shell_geometry import (
    global_bar_row,
    workspace_bottom_exclusive,
    workspace_top_row,
)

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
    return global_bar_row(frame_h)


def _taskbar_bounds(app, width):
    menu = getattr(app, "menu", None)
    start_x = 1
    menu_right = getattr(menu, "menu_items_right_x", None)
    if callable(menu_right):
        try:
            start_x = max(start_x, int(menu_right()) + 1)
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

    for row in range(workspace_top_row(), workspace_bottom_exclusive(h)):
        safe_addstr(app.stdscr, row, 0, line, attr, _bounds=bounds)


def draw_icons(app, frame_size=None):
    """Draw desktop icons with shared Unicode-aware render geometry."""
    h, w = _resolve_frame_size(app, frame_size)
    bounds = (h, w)
    get_pos = app.get_icon_screen_pos
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
            pass

    for idx, icon in enumerate(app.icons):
        if accepts_frame_size:
            x, y = get_pos(idx, frame_size=frame_size)
        else:
            x, y = get_pos(idx)

        art_lines, render_height, render_width = icon_render_metrics(icon)
        if y + render_height >= workspace_bottom_exclusive(h) or x >= w:
            continue
        visible_width = min(render_width, max(0, w - x))
        if visible_width <= 0:
            continue

        is_selected = idx == app.selected_icon
        attr = theme_attr("icon_selected" if is_selected else "icon")
        if is_selected:
            attr |= curses.A_BOLD

        for row, line in enumerate(art_lines):
            rendered = center_text_columns(line, visible_width, suffix="…")
            safe_addstr(app.stdscr, y + row, x, rendered, attr, _bounds=bounds)
        label = center_text_columns(
            icon.get("label", ""),
            visible_width,
            suffix="…",
        )
        safe_addstr(
            app.stdscr,
            y + render_height,
            x,
            label,
            attr,
            _bounds=bounds,
        )


def draw_taskbar(app, frame_size=None):
    """Draw minimized window buttons on the shell bar."""
    h, w = _resolve_frame_size(app, frame_size)
    bounds = (h, w)
    taskbar_y = _taskbar_row(h)
    attr = theme_attr("taskbar")

    stats = _window_stats(app)
    start_x, end_x = _taskbar_bounds(app, w)
    buttons = _taskbar_buttons(app, w, stats=stats, start_x=start_x, end_x=end_x)
    for start_x, _end_x, label, _win in buttons:
        safe_addstr(app.stdscr, taskbar_y, start_x, f'[{label}]', attr | curses.A_BOLD, _bounds=bounds)


def draw_statusbar(app, version, frame_size=None):
    """Compatibility hook; the classic taskbar owns the only bottom row."""
    return None

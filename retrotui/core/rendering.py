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


def _window_stats(app):
    """Return cached per-frame window stats used by taskbar/statusbar."""
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


def draw_desktop(app, frame_size=None):
    """Draw the desktop background pattern."""
    h, w = _resolve_frame_size(app, frame_size)
    attr = theme_attr("desktop")
    pattern = getattr(getattr(app, "theme", None), "desktop_pattern", DESKTOP_PATTERN)

    # Reuse cached line when width and pattern haven't changed.
    cache_key = (w, pattern)
    if _desktop_line_cache['key'] != cache_key:
        _desktop_line_cache['line'] = (pattern * (w // len(pattern) + 1))[:w]
        _desktop_line_cache['key'] = cache_key
    line = _desktop_line_cache['line']

    for row in range(MENU_BAR_HEIGHT, h - BOTTOM_BARS_HEIGHT + 1):
        safe_addstr(app.stdscr, row, 0, line, attr)


def draw_icons(app, frame_size=None):
    """Draw desktop icons (3x4 art + label)."""
    h, _ = _resolve_frame_size(app, frame_size)
    for idx, icon in enumerate(app.icons):
        # Use dynamic position helper
        x, y = app.get_icon_screen_pos(idx)
        
        # Clip if off-screen (y)
        if y + ICON_ART_HEIGHT >= h - BOTTOM_BARS_HEIGHT:
            continue

        is_selected = idx == app.selected_icon
        attr = theme_attr("icon_selected" if is_selected else "icon")
        if is_selected:
            attr |= curses.A_BOLD
            
        for row, line in enumerate(icon['art']):
            safe_addstr(app.stdscr, y + row, x, line, attr)
        label = icon['label'].center(len(icon['art'][0]))
        safe_addstr(app.stdscr, y + ICON_ART_HEIGHT, x, label, attr)


def draw_taskbar(app, frame_size=None):
    """Draw taskbar row with minimized window buttons."""
    h, w = _resolve_frame_size(app, frame_size)
    taskbar_y = h - BOTTOM_BARS_HEIGHT
    attr = theme_attr("taskbar")
    
    # Always clear the taskbar line
    safe_addstr(app.stdscr, taskbar_y, 0, ' ' * w, attr)
    
    window_mgr = getattr(app, "window_mgr", None)
    if window_mgr is not None and hasattr(window_mgr, "taskbar_buttons"):
        buttons = window_mgr.taskbar_buttons(w)
        for start_x, _end_x, label, _win in buttons:
            safe_addstr(app.stdscr, taskbar_y, start_x, f'[{label}]', attr | curses.A_BOLD)
        return

    stats = _window_stats(app)
    minimized_labels = stats["minimized_labels"]
    if not minimized_labels:
        return
    x = 1
    for label in minimized_labels:
        btn = f'[{label}]'
        if x + len(btn) > w:
            break
        safe_addstr(app.stdscr, taskbar_y, x, btn, attr | curses.A_BOLD)
        x += len(btn) + 1


def draw_statusbar(app, version, frame_size=None):
    """Draw the bottom status bar."""
    h, w = _resolve_frame_size(app, frame_size)
    attr = theme_attr("status")
    stats = _window_stats(app)
    visible = stats["visible"]
    total = stats["total"]
    
    left_status = f' RetroTUI v{version} | Windows: {visible}/{total} | Mouse: Enabled'
    
    statusbar_y = h - BOTTOM_BARS_HEIGHT + 1  # Last row: below taskbar
    # Draw background
    safe_addstr(app.stdscr, statusbar_y, 0, ' ' * w, attr)

    # Draw left text
    safe_addstr(app.stdscr, statusbar_y, 0, left_status, attr)

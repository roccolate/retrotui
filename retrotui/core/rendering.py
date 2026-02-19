"""Rendering helpers for RetroTUI."""

import curses

from ..constants import (
    C_DESKTOP,
    C_ICON,
    C_ICON_SEL,
    C_STATUS,
    C_TASKBAR,
    DESKTOP_PATTERN,
)
from ..utils import safe_addstr, theme_attr


def draw_desktop(app):
    """Draw the desktop background pattern."""
    h, w = app.stdscr.getmaxyx()
    attr = theme_attr("desktop")
    pattern = getattr(getattr(app, "theme", None), "desktop_pattern", DESKTOP_PATTERN)

    for row in range(1, h - 1):
        line = (pattern * (w // len(pattern) + 1))[: w - 1]
        safe_addstr(app.stdscr, row, 0, line, attr)


def draw_icons(app):
    """Draw desktop icons (3x4 art + label)."""
    h, _ = app.stdscr.getmaxyx()
    for idx, icon in enumerate(app.icons):
        # Use dynamic position helper
        x, y = app.get_icon_screen_pos(idx)
        
        # Clip if off-screen (y)
        if y + 3 >= h - 1:
            continue
            
        is_selected = idx == app.selected_icon
        attr = theme_attr("icon_selected" if is_selected else "icon") | curses.A_BOLD
        for row, line in enumerate(icon['art']):
            safe_addstr(app.stdscr, y + row, x, line, attr)
        label = icon['label'].center(len(icon['art'][0]))
        safe_addstr(app.stdscr, y + 3, x, label, attr)


def draw_taskbar(app):
    """Draw taskbar row with minimized window buttons."""
    h, w = app.stdscr.getmaxyx()
    taskbar_y = h - 2
    minimized = [win for win in app.windows if win.minimized]
    if not minimized:
        return
    attr = theme_attr("taskbar")
    safe_addstr(app.stdscr, taskbar_y, 0, ' ' * (w - 1), attr)
    x = 1
    for win in minimized:
        label = win.title[:15]
        btn = f'[{label}]'
        if x + len(btn) >= w - 1:
            break
        safe_addstr(app.stdscr, taskbar_y, x, btn, attr | curses.A_BOLD)
        x += len(btn) + 1


def draw_statusbar(app, version):
    """Draw the bottom status bar."""
    h, w = app.stdscr.getmaxyx()
    attr = theme_attr("status")
    visible = sum(1 for win in app.windows if win.visible)
    from datetime import datetime
    now_str = datetime.now().strftime('%H:%M')
    
    # Left part
    left_status = f' RetroTUI v{version} | Windows: {visible}/{len(app.windows)} | Mouse: Enabled'
    
    # Draw background
    safe_addstr(app.stdscr, h - 1, 0, ' ' * (w - 1), attr)
    
    # Draw left text
    safe_addstr(app.stdscr, h - 1, 0, left_status, attr)
    
    # Draw right clock
    clock_len = len(now_str) + 2
    if w > len(left_status) + clock_len:
         safe_addstr(app.stdscr, h - 1, w - clock_len, now_str, attr | curses.A_BOLD)

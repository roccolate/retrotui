#!/usr/bin/env python3
"""
RetroTUI v0.3.2 — Entorno de escritorio retro estilo Windows 3.1
Funciona en consola Linux sin X11. Soporte de mouse vía GPM o xterm protocol.
"""

import curses
import sys
import time
import os
import locale
import termios
import shutil
import subprocess

# Ensure UTF-8
locale.setlocale(locale.LC_ALL, '')

# ═══════════════════════════════════════════════════════════
# Constants & Theme
# ═══════════════════════════════════════════════════════════

# Box drawing characters (Unicode)
BOX_TL = '╔'
BOX_TR = '╗'
BOX_BL = '╚'
BOX_BR = '╝'
BOX_H  = '═'
BOX_V  = '║'

# Single line for dialogs
SB_TL = '┌'
SB_TR = '┐'
SB_BL = '└'
SB_BR = '┘'
SB_H  = '─'
SB_V  = '│'

# Desktop pattern (Win 3.1 style)
DESKTOP_PATTERN = '░'

# Icons (text representation)
ICONS = [
    {'label': 'Files',    'action': 'filemanager', 'art': ['┌──┐', '│▒▒│', '└──┘']},
    {'label': 'Notepad',  'action': 'notepad',     'art': ['╔══╗', '║≡≡║', '╚══╝']},
    {'label': 'ASCII Vid', 'action': 'asciivideo', 'art': ['┌──┐', '│▶█│', '└──┘']},
    {'label': 'Terminal', 'action': 'terminal',     'art': ['┌──┐', '│>_│', '└──┘']},
    {'label': 'Settings', 'action': 'settings',    'art': ['╭──╮', '│⚙ │', '╰──╯']},
    {'label': 'About',   'action': 'about',        'art': ['╭──╮', '│ ?│', '╰──╯']},
]

# Fallback ASCII icons for non-Unicode terminals
ICONS_ASCII = [
    {'label': 'Files',    'action': 'filemanager', 'art': ['+--+', '|##|', '+--+']},
    {'label': 'Notepad',  'action': 'notepad',     'art': ['+--+', '|==|', '+--+']},
    {'label': 'ASCII Vid', 'action': 'asciivideo', 'art': ['+--+', '|>|#', '+--+']},
    {'label': 'Terminal', 'action': 'terminal',     'art': ['+--+', '|>_|', '+--+']},
    {'label': 'Settings', 'action': 'settings',    'art': ['+--+', '|**|', '+--+']},
    {'label': 'About',   'action': 'about',        'art': ['+--+', '| ?|', '+--+']},
]


# ═══════════════════════════════════════════════════════════
# Color Pairs
# ═══════════════════════════════════════════════════════════

C_DESKTOP       = 1
C_MENUBAR       = 2
C_MENU_ITEM     = 3
C_MENU_SEL      = 4
C_WIN_BORDER    = 5
C_WIN_TITLE     = 6
C_WIN_TITLE_INV = 7
C_WIN_BODY      = 8
C_BUTTON        = 9
C_BUTTON_SEL    = 10
C_DIALOG        = 11
C_STATUS        = 12
C_ICON          = 13
C_ICON_SEL      = 14
C_SCROLLBAR     = 15
C_WIN_INACTIVE  = 16
C_FM_SELECTED   = 17
C_FM_DIR        = 18
C_TASKBAR       = 19


def init_colors():
    """Initialize Windows 3.1 color scheme."""
    curses.start_color()
    curses.use_default_colors()

    if curses.can_change_color() and curses.COLORS >= 256:
        # Custom Win3.1 palette
        curses.init_color(20, 0, 500, 500)      # Teal desktop
        curses.init_color(21, 0, 0, 500)         # Dark blue title
        curses.init_color(22, 800, 800, 800)     # Light gray
        curses.init_color(23, 600, 600, 600)     # Medium gray
        curses.init_pair(C_DESKTOP,       curses.COLOR_CYAN, 20)
        curses.init_pair(C_WIN_TITLE,     curses.COLOR_WHITE, 21)
        curses.init_pair(C_WIN_INACTIVE,  curses.COLOR_WHITE, 23)
        curses.init_pair(C_ICON,          curses.COLOR_BLACK, 20)  # Black on teal
    else:
        curses.init_pair(C_DESKTOP,       curses.COLOR_CYAN, curses.COLOR_CYAN)
        curses.init_pair(C_WIN_TITLE,     curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(C_WIN_INACTIVE,  curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(C_ICON,          curses.COLOR_BLACK, curses.COLOR_CYAN)

    curses.init_pair(C_MENUBAR,       curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_MENU_ITEM,     curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_MENU_SEL,      curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(C_WIN_BORDER,    curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(C_WIN_TITLE_INV, curses.COLOR_BLUE, curses.COLOR_WHITE)
    curses.init_pair(C_WIN_BODY,      curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_BUTTON,        curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_BUTTON_SEL,    curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(C_DIALOG,        curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_STATUS,        curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(C_ICON_SEL,      curses.COLOR_YELLOW, curses.COLOR_BLUE)
    curses.init_pair(C_SCROLLBAR,     curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_FM_SELECTED,   curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(C_FM_DIR,        curses.COLOR_BLUE, curses.COLOR_WHITE)
    curses.init_pair(C_TASKBAR,       curses.COLOR_BLACK, curses.COLOR_WHITE)


# ═══════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════

def safe_addstr(win, y, x, text, attr=0):
    """Write string safely, clipping to window bounds."""
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    max_len = w - x - 1
    if max_len <= 0:
        return
    try:
        win.addnstr(y, x, text, max_len, attr)
    except curses.error:
        pass


def draw_box(win, y, x, h, w, attr=0, double=True):
    """Draw a box with double or single line borders."""
    if double:
        tl, tr, bl, br, hz, vt = BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_H, BOX_V
    else:
        tl, tr, bl, br, hz, vt = SB_TL, SB_TR, SB_BL, SB_BR, SB_H, SB_V

    safe_addstr(win, y, x, tl + hz * (w - 2) + tr, attr)
    for i in range(1, h - 1):
        safe_addstr(win, y + i, x, vt, attr)
        safe_addstr(win, y + i, x + w - 1, vt, attr)
    safe_addstr(win, y + h - 1, x, bl + hz * (w - 2) + br, attr)


def check_unicode_support():
    """Check if terminal supports Unicode."""
    try:
        '╔'.encode(locale.getpreferredencoding())
        return True
    except (UnicodeEncodeError, LookupError):
        return False


# ═══════════════════════════════════════════════════════════
# Window Class
# ═══════════════════════════════════════════════════════════

class Window:
    """A draggable window with title bar and content area."""

    _next_id = 0

    def __init__(self, title, x, y, w, h, content=None, resizable=True):
        self.id = Window._next_id
        Window._next_id += 1
        self.title = title
        self.x = x
        self.y = y
        self.w = max(w, 20)
        self.h = max(h, 6)
        self.content = content or []
        self.resizable = resizable
        self.visible = True
        self.active = False
        self.scroll_offset = 0
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        # Maximize / Minimize state
        self.maximized = False
        self.minimized = False
        self.prev_rect = None  # (x, y, w, h) saved before maximize
        # Resize state
        self.resizing = False
        self.resize_edge = None
        # Optional per-window menu bar (set by subclasses)
        self.window_menu = None

    def close_button_pos(self):
        """Return (x, y) of the close button."""
        return (self.x + self.w - 4, self.y)

    def body_rect(self):
        """Return inner content area (x, y, w, h).
        Accounts for window menu bar if present."""
        menu_offset = 1 if self.window_menu else 0
        return (self.x + 1, self.y + 1 + menu_offset,
                self.w - 2, self.h - 2 - menu_offset)

    def contains(self, mx, my):
        """Check if point is within window bounds."""
        return (self.x <= mx < self.x + self.w and
                self.y <= my < self.y + self.h)

    def on_title_bar(self, mx, my):
        """Check if point is on the title bar (draggable zone, excludes buttons)."""
        return (self.x + 1 <= mx < self.x + self.w - 10 and my == self.y)

    def on_close_button(self, mx, my):
        """Check if point is on the close button [×]."""
        cx = self.x + self.w - 4
        return (cx <= mx <= cx + 2 and my == self.y)

    def on_minimize_button(self, mx, my):
        """Check if point is on the minimize button [─]."""
        bx = self.x + self.w - 10
        return (bx <= mx <= bx + 2 and my == self.y)

    def on_maximize_button(self, mx, my):
        """Check if point is on the maximize button [□]."""
        bx = self.x + self.w - 7
        return (bx <= mx <= bx + 2 and my == self.y)

    def toggle_maximize(self, term_w, term_h):
        """Toggle between maximized and normal state."""
        if self.maximized:
            # Restore previous rect
            if self.prev_rect:
                self.x, self.y, self.w, self.h = self.prev_rect
                self.prev_rect = None
            self.maximized = False
        else:
            # Save current rect and expand to full screen
            self.prev_rect = (self.x, self.y, self.w, self.h)
            self.x = 0
            self.y = 1  # Below menu bar
            self.w = term_w
            self.h = term_h - 2  # Above taskbar + status bar
            self.maximized = True

    def toggle_minimize(self):
        """Toggle between minimized and visible state."""
        if self.minimized:
            self.minimized = False
            self.visible = True
        else:
            self.minimized = True
            self.visible = False
            self.dragging = False
            self.resizing = False

    def on_border(self, mx, my):
        """Detect resize zone on window borders. Returns edge string or None.
        Only bottom, right, and bottom corners are resizable."""
        if self.maximized or not self.resizable:
            return None
        # Bottom-right corner (2×1 area)
        if (self.x + self.w - 2 <= mx <= self.x + self.w - 1 and my == self.y + self.h - 1):
            return 'se'
        # Bottom-left corner (2×1 area)
        if (self.x <= mx <= self.x + 1 and my == self.y + self.h - 1):
            return 'sw'
        # Bottom border
        if (self.x + 2 <= mx <= self.x + self.w - 3 and my == self.y + self.h - 1):
            return 's'
        # Right border
        if (mx == self.x + self.w - 1 and self.y + 1 <= my <= self.y + self.h - 2):
            return 'e'
        # Left border
        if (mx == self.x and self.y + 1 <= my <= self.y + self.h - 2):
            return 'w'
        return None

    def apply_resize(self, mx, my, term_w, term_h):
        """Apply resize based on mouse position and active resize_edge."""
        min_w = 20
        min_h = 7 if self.window_menu else 6
        edge = self.resize_edge
        if edge in ('se', 's', 'e'):
            if 'e' in edge:
                new_w = mx - self.x + 1
                self.w = max(min_w, min(new_w, term_w - self.x))
            if 's' in edge:
                new_h = my - self.y + 1
                self.h = max(min_h, min(new_h, term_h - self.y - 1))
        elif edge == 'sw':
            new_w = (self.x + self.w) - mx
            if new_w >= min_w and mx >= 0:
                self.x = mx
                self.w = new_w
            new_h = my - self.y + 1
            self.h = max(min_h, min(new_h, term_h - self.y - 1))
        elif edge == 'w':
            new_w = (self.x + self.w) - mx
            if new_w >= min_w and mx >= 0:
                self.x = mx
                self.w = new_w

    def draw_frame(self, stdscr):
        """Draw window frame: border, title bar, and buttons. Returns body_attr."""
        border_attr = curses.color_pair(C_WIN_BORDER) if self.active else curses.color_pair(C_WIN_INACTIVE)
        title_attr = curses.color_pair(C_WIN_TITLE) if self.active else curses.color_pair(C_WIN_INACTIVE)
        body_attr = curses.color_pair(C_WIN_BODY)

        # Draw border
        draw_box(stdscr, self.y, self.x, self.h, self.w, border_attr)

        # Title bar text (≡ prefix if window has menu)
        prefix = '≡ ' if self.window_menu else ''
        title_text = f' {prefix}{self.title} '
        max_title = self.w - 12  # Leave room for 3 buttons [─][□][×]
        if len(title_text) > max_title:
            title_text = title_text[:max_title - 3] + '...'
        title_bar = title_text.ljust(self.w - 11)
        safe_addstr(stdscr, self.y, self.x + 1, title_bar, title_attr | curses.A_BOLD)

        # Window buttons: [─][□][×]
        btn_attr = curses.color_pair(C_BUTTON) | curses.A_BOLD
        max_char = '▣' if self.maximized else '□'
        safe_addstr(stdscr, self.y, self.x + self.w - 10, f'[─][{max_char}][×]', btn_attr)

        # Per-window menu bar (below title, above body)
        if self.window_menu:
            self.window_menu.draw_bar(stdscr, self.x, self.y, self.w, self.active)

        return body_attr

    def draw_body(self, stdscr, body_attr):
        """Draw window body: background, content lines, scrollbar."""
        bx, by, bw, bh = self.body_rect()

        # Body background
        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, ' ' * bw, body_attr)

        # Content
        visible_lines = self.content[self.scroll_offset:self.scroll_offset + bh]
        for i, line in enumerate(visible_lines):
            display = line[:bw]
            safe_addstr(stdscr, by + i, bx, display, body_attr)

        # Scrollbar if content exceeds visible area
        if len(self.content) > bh and bh > 1:
            sb_x = self.x + self.w - 2
            total = len(self.content)
            thumb_pos = int(self.scroll_offset / max(1, total - bh) * (bh - 1))
            for i in range(bh):
                ch = '█' if i == thumb_pos else '░'
                safe_addstr(stdscr, by + i, sb_x, ch, curses.color_pair(C_SCROLLBAR))

    def draw(self, stdscr):
        """Draw the window."""
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        self.draw_body(stdscr, body_attr)
        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def scroll_up(self):
        if self.scroll_offset > 0:
            self.scroll_offset -= 1

    def scroll_down(self):
        _, _, _, bh = self.body_rect()
        max_scroll = max(0, len(self.content) - bh)
        if self.scroll_offset < max_scroll:
            self.scroll_offset += 1


# ═══════════════════════════════════════════════════════════
# Menu System
# ═══════════════════════════════════════════════════════════

class Menu:
    """Dropdown menu system."""

    def __init__(self):
        self.items = {
            'File': [
                ('New Window',    'new_window'),
                ('Notepad',       'notepad'),
                ('File Manager',  'filemanager'),
                ('ASCII Video',   'asciivideo'),
                ('Terminal',      'terminal'),
                ('─────────────', None),
                ('Exit  Ctrl+Q',  'exit'),
            ],
            'Edit': [
                ('Preferences', 'settings'),
            ],
            'Help': [
                ('About RetroTUI', 'about'),
                ('Keyboard Help',  'help'),
            ],
        }
        self.menu_names = list(self.items.keys())
        self.active = False
        self.selected_menu = 0
        self.selected_item = 0

    def get_menu_x_positions(self):
        """Calculate x position of each menu name in the menu bar."""
        positions = []
        x = 2
        for name in self.menu_names:
            positions.append(x)
            x += len(name) + 3
        return positions

    def draw_bar(self, stdscr, width):
        """Draw the menu bar."""
        bar_attr = curses.color_pair(C_MENUBAR)
        safe_addstr(stdscr, 0, 0, ' ' * width, bar_attr)
        safe_addstr(stdscr, 0, 0, ' ≡', bar_attr | curses.A_BOLD)

        positions = self.get_menu_x_positions()
        for i, name in enumerate(self.menu_names):
            attr = bar_attr
            if self.active and i == self.selected_menu:
                attr = curses.color_pair(C_MENU_SEL)
            safe_addstr(stdscr, 0, positions[i], f' {name} ', attr)

        # Clock on the right
        clock = time.strftime(' %H:%M:%S ')
        safe_addstr(stdscr, 0, width - len(clock) - 1, clock, bar_attr)

    def draw_dropdown(self, stdscr):
        """Draw the active dropdown menu."""
        if not self.active:
            return

        menu_name = self.menu_names[self.selected_menu]
        items = self.items[menu_name]
        positions = self.get_menu_x_positions()
        x = positions[self.selected_menu]
        y = 1

        # Calculate dropdown width
        max_item_len = max(len(item[0]) for item in items)
        dropdown_w = max_item_len + 4

        # Draw dropdown background
        item_attr = curses.color_pair(C_MENU_ITEM)
        draw_box(stdscr, y, x - 1, len(items) + 2, dropdown_w + 2, item_attr, double=False)

        for i, (label, action) in enumerate(items):
            attr = curses.color_pair(C_MENU_SEL) if i == self.selected_item else item_attr
            if action is None:
                # Separator
                safe_addstr(stdscr, y + 1 + i, x, SB_H * dropdown_w, item_attr)
            else:
                safe_addstr(stdscr, y + 1 + i, x, f' {label.ljust(dropdown_w - 2)} ', attr)

    def get_dropdown_rect(self):
        """Return (x, y, w, h) of the active dropdown area, or None."""
        if not self.active:
            return None
        menu_name = self.menu_names[self.selected_menu]
        items = self.items[menu_name]
        positions = self.get_menu_x_positions()
        x = positions[self.selected_menu]
        max_item_len = max(len(item[0]) for item in items)
        dropdown_w = max_item_len + 4
        # Full area: border row (y=1) through all items + bottom border
        return (x - 1, 1, dropdown_w + 2, len(items) + 2)

    def hit_test_dropdown(self, mx, my):
        """Check if position is within the dropdown area (including border)."""
        rect = self.get_dropdown_rect()
        if rect is None:
            return False
        rx, ry, rw, rh = rect
        return rx <= mx < rx + rw and ry <= my < ry + rh

    def handle_hover(self, mx, my):
        """Handle mouse hover over dropdown — update highlight. Returns True if inside menu area."""
        if not self.active:
            return False
        # On menu bar row — stay active
        if my == 0:
            positions = self.get_menu_x_positions()
            for i, pos in enumerate(positions):
                name = self.menu_names[i]
                if pos <= mx < pos + len(name) + 2:
                    if i != self.selected_menu:
                        self.selected_menu = i
                        self.selected_item = 0
                    return True
            return True  # Still on row 0, don't close
        # Inside dropdown — highlight item
        if self.hit_test_dropdown(mx, my):
            menu_name = self.menu_names[self.selected_menu]
            items = self.items[menu_name]
            idx = my - 2
            if 0 <= idx < len(items) and items[idx][1] is not None:
                self.selected_item = idx
            return True
        return False

    def handle_click(self, mx, my):
        """Handle click on menu bar. Returns action or None."""
        if my == 0:
            positions = self.get_menu_x_positions()
            for i, pos in enumerate(positions):
                name = self.menu_names[i]
                if pos <= mx < pos + len(name) + 2:
                    if self.active and self.selected_menu == i:
                        self.active = False
                    else:
                        self.active = True
                        self.selected_menu = i
                        self.selected_item = 0
                    return None
            self.active = False
            return None

        if self.active:
            menu_name = self.menu_names[self.selected_menu]
            items = self.items[menu_name]
            positions = self.get_menu_x_positions()
            x = positions[self.selected_menu]
            max_item_len = max(len(item[0]) for item in items)
            dropdown_w = max_item_len + 4

            if x - 1 <= mx < x + dropdown_w + 1 and 2 <= my < 2 + len(items):
                idx = my - 2
                if idx < len(items) and items[idx][1] is not None:
                    action = items[idx][1]
                    self.active = False
                    return action
            else:
                self.active = False
        return None


# ═══════════════════════════════════════════════════════════
# Window Menu (per-window menu bar)
# ═══════════════════════════════════════════════════════════

class WindowMenu:
    """Per-window dropdown menu bar, styled like Win 3.1 application menus."""

    def __init__(self, items):
        """items: dict {'MenuName': [('Label', 'action'), ...], ...}"""
        self.items = items
        self.menu_names = list(items.keys())
        self.active = False
        self.selected_menu = 0
        self.selected_item = 0

    def menu_bar_row(self, win_y):
        """Absolute screen row of this menu bar."""
        return win_y + 1

    def get_menu_x_positions(self, win_x):
        """Calculate absolute x positions of each menu name."""
        positions = []
        x = win_x + 2
        for name in self.menu_names:
            positions.append(x)
            x += len(name) + 3
        return positions

    def draw_bar(self, stdscr, win_x, win_y, win_w, is_active):
        """Draw the menu bar row inside the window."""
        bar_y = self.menu_bar_row(win_y)
        bar_attr = curses.color_pair(C_MENUBAR)
        safe_addstr(stdscr, bar_y, win_x + 1, ' ' * (win_w - 2), bar_attr)

        positions = self.get_menu_x_positions(win_x)
        for i, name in enumerate(self.menu_names):
            attr = bar_attr
            if self.active and i == self.selected_menu:
                attr = curses.color_pair(C_MENU_SEL)
            safe_addstr(stdscr, bar_y, positions[i], f' {name} ', attr)

    def draw_dropdown(self, stdscr, win_x, win_y, win_w):
        """Draw the active dropdown menu over the window body."""
        if not self.active:
            return

        menu_name = self.menu_names[self.selected_menu]
        items = self.items[menu_name]
        positions = self.get_menu_x_positions(win_x)
        x = positions[self.selected_menu]
        y = self.menu_bar_row(win_y) + 1

        max_item_len = max(len(item[0]) for item in items)
        dropdown_w = max_item_len + 4

        # Clamp dropdown to not exceed window right edge
        if x - 1 + dropdown_w + 2 > win_x + win_w:
            x = max(win_x + 2, win_x + win_w - dropdown_w - 2)

        item_attr = curses.color_pair(C_MENU_ITEM)
        draw_box(stdscr, y, x - 1, len(items) + 2, dropdown_w + 2, item_attr, double=False)

        for i, (label, action) in enumerate(items):
            attr = curses.color_pair(C_MENU_SEL) if i == self.selected_item else item_attr
            if action is None:
                safe_addstr(stdscr, y + 1 + i, x, SB_H * dropdown_w, item_attr)
            else:
                safe_addstr(stdscr, y + 1 + i, x, f' {label.ljust(dropdown_w - 2)} ', attr)

    def on_menu_bar(self, mx, my, win_x, win_y, win_w):
        """Check if click is on the menu bar row within window bounds."""
        return (my == self.menu_bar_row(win_y) and win_x + 1 <= mx < win_x + win_w - 1)

    def handle_click(self, mx, my, win_x, win_y, win_w):
        """Handle click on menu bar or dropdown. Returns action string or None."""
        bar_y = self.menu_bar_row(win_y)

        # Click on menu bar row
        if my == bar_y:
            positions = self.get_menu_x_positions(win_x)
            for i, pos in enumerate(positions):
                name = self.menu_names[i]
                if pos <= mx < pos + len(name) + 2:
                    if self.active and self.selected_menu == i:
                        self.active = False
                    else:
                        self.active = True
                        self.selected_menu = i
                        self.selected_item = 0
                    return None
            self.active = False
            return None

        # Click on dropdown items
        if self.active:
            menu_name = self.menu_names[self.selected_menu]
            items = self.items[menu_name]
            positions = self.get_menu_x_positions(win_x)
            x = positions[self.selected_menu]
            max_item_len = max(len(item[0]) for item in items)
            dropdown_w = max_item_len + 4

            # Clamp same as draw
            if x - 1 + dropdown_w + 2 > win_x + win_w:
                x = max(win_x + 2, win_x + win_w - dropdown_w - 2)

            if (x - 1 <= mx < x + dropdown_w + 1 and
                    bar_y + 2 <= my < bar_y + 2 + len(items)):
                idx = my - bar_y - 2
                if idx < len(items) and items[idx][1] is not None:
                    action = items[idx][1]
                    self.active = False
                    return action
            else:
                self.active = False
        return None

    def handle_hover(self, mx, my, win_x, win_y, win_w):
        """Update hover highlight. Returns True if inside menu area."""
        if not self.active:
            return False
        bar_y = self.menu_bar_row(win_y)

        if my == bar_y:
            positions = self.get_menu_x_positions(win_x)
            for i, pos in enumerate(positions):
                name = self.menu_names[i]
                if pos <= mx < pos + len(name) + 2:
                    if i != self.selected_menu:
                        self.selected_menu = i
                        self.selected_item = 0
                    return True
            return True

        # Inside dropdown
        menu_name = self.menu_names[self.selected_menu]
        items = self.items[menu_name]
        positions = self.get_menu_x_positions(win_x)
        x = positions[self.selected_menu]
        max_item_len = max(len(item[0]) for item in items)
        dropdown_w = max_item_len + 4

        if x - 1 + dropdown_w + 2 > win_x + win_w:
            x = max(win_x + 2, win_x + win_w - dropdown_w - 2)

        if (x - 1 <= mx < x + dropdown_w + 1 and
                bar_y + 1 <= my < bar_y + 3 + len(items)):
            idx = my - bar_y - 2
            if 0 <= idx < len(items) and items[idx][1] is not None:
                self.selected_item = idx
            return True
        return False

    def handle_key(self, key):
        """Handle keyboard navigation. Returns action, 'close_menu', or None."""
        if not self.active:
            return None
        if key == curses.KEY_LEFT:
            self.selected_menu = (self.selected_menu - 1) % len(self.menu_names)
            self.selected_item = 0
        elif key == curses.KEY_RIGHT:
            self.selected_menu = (self.selected_menu + 1) % len(self.menu_names)
            self.selected_item = 0
        elif key == curses.KEY_UP:
            items = self.items[self.menu_names[self.selected_menu]]
            self.selected_item = (self.selected_item - 1) % len(items)
            while items[self.selected_item][1] is None:
                self.selected_item = (self.selected_item - 1) % len(items)
        elif key == curses.KEY_DOWN:
            items = self.items[self.menu_names[self.selected_menu]]
            self.selected_item = (self.selected_item + 1) % len(items)
            while items[self.selected_item][1] is None:
                self.selected_item = (self.selected_item + 1) % len(items)
        elif key in (curses.KEY_ENTER, 10, 13):
            menu_name = self.menu_names[self.selected_menu]
            items = self.items[menu_name]
            action = items[self.selected_item][1]
            if action:
                self.active = False
                return action
        elif key == 27:  # Escape
            self.active = False
            return 'close_menu'
        return None


# ═══════════════════════════════════════════════════════════
# Dialog
# ═══════════════════════════════════════════════════════════

class Dialog:
    """Modal dialog box."""

    def __init__(self, title, message, buttons=None, width=50):
        self.title = title
        self.message = message
        self.buttons = buttons or ['OK']
        self.selected = 0
        self.width = max(width, len(title) + 8)

        # Word wrap message
        self.lines = []
        inner_w = self.width - 6
        for paragraph in message.split('\n'):
            words = paragraph.split()
            line = ''
            for word in words:
                if len(line) + len(word) + 1 <= inner_w:
                    line = line + ' ' + word if line else word
                else:
                    self.lines.append(line)
                    line = word
            self.lines.append(line)

        self.height = len(self.lines) + 7

        # Pre-initialize click target positions (updated by draw())
        self._btn_y = 0
        self._btn_x_start = 0
        self._dialog_x = 0
        self._dialog_y = 0

    def draw(self, stdscr):
        max_h, max_w = stdscr.getmaxyx()
        x = (max_w - self.width) // 2
        y = (max_h - self.height) // 2

        attr = curses.color_pair(C_DIALOG)
        title_attr = curses.color_pair(C_WIN_TITLE) | curses.A_BOLD

        # Shadow
        shadow_attr = curses.A_DIM
        for row in range(self.height):
            safe_addstr(stdscr, y + row + 1, x + 2, ' ' * self.width, shadow_attr)

        # Dialog background
        for row in range(self.height):
            safe_addstr(stdscr, y + row, x, ' ' * self.width, attr)

        # Border
        draw_box(stdscr, y, x, self.height, self.width, attr, double=True)

        # Title
        title_text = f' {self.title} '
        safe_addstr(stdscr, y, x + 1, title_text.ljust(self.width - 2), title_attr)

        # Message lines
        for i, line in enumerate(self.lines):
            safe_addstr(stdscr, y + 2 + i, x + 3, line, attr)

        # Buttons
        btn_y = y + self.height - 3
        total_btn_width = sum(len(b) + 6 for b in self.buttons) + (len(self.buttons) - 1) * 2
        btn_x = x + (self.width - total_btn_width) // 2

        for i, btn_text in enumerate(self.buttons):
            btn_w = len(btn_text) + 4
            if i == self.selected:
                btn_attr = curses.color_pair(C_BUTTON_SEL) | curses.A_BOLD
                label = f'▸ {btn_text} ◂'
            else:
                btn_attr = curses.color_pair(C_BUTTON)
                label = f'[ {btn_text} ]'
            safe_addstr(stdscr, btn_y, btn_x, label, btn_attr)
            btn_x += btn_w + 2

        # Store button positions for click handling
        self._btn_y = btn_y
        self._btn_x_start = x + (self.width - total_btn_width) // 2
        self._dialog_x = x
        self._dialog_y = y

    def handle_click(self, mx, my):
        """Return button index if clicked, -1 otherwise."""
        if my == self._btn_y:
            btn_x = self._btn_x_start
            for i, btn_text in enumerate(self.buttons):
                btn_w = len(btn_text) + 4
                if btn_x <= mx < btn_x + btn_w:
                    return i
                btn_x += btn_w + 2
        return -1

    def handle_key(self, key):
        """Handle keyboard input. Returns button index or -1."""
        if key == curses.KEY_LEFT:
            self.selected = (self.selected - 1) % len(self.buttons)
        elif key == curses.KEY_RIGHT:
            self.selected = (self.selected + 1) % len(self.buttons)
        elif key in (curses.KEY_ENTER, 10, 13):
            return self.selected
        elif key == 27:  # Escape
            return len(self.buttons) - 1  # Last button (usually Cancel)
        return -1


# ═══════════════════════════════════════════════════════════
# File Entry
# ═══════════════════════════════════════════════════════════

class FileEntry:
    """Represents a file or directory entry in the file manager."""
    __slots__ = ('name', 'is_dir', 'full_path', 'size', 'display_text')

    def __init__(self, name, is_dir, full_path, size=0):
        self.name = name
        self.is_dir = is_dir
        self.full_path = full_path
        self.size = size
        if name == '..':
            self.display_text = '  📁 ..'
        elif is_dir:
            self.display_text = f'  📁 {name}/'
        else:
            self.display_text = f'  📄 {name:<30} {self._format_size():>8}'

    def _format_size(self):
        if self.size > 1048576:
            return f'{self.size / 1048576:.1f}M'
        elif self.size > 1024:
            return f'{self.size / 1024:.1f}K'
        else:
            return f'{self.size}B'


# ═══════════════════════════════════════════════════════════
# File Manager Window
# ═══════════════════════════════════════════════════════════

class FileManagerWindow(Window):
    """Interactive file manager window with directory navigation."""

    def __init__(self, x, y, w, h, start_path=None):
        super().__init__('File Manager', x, y, w, h, content=[])
        self.current_path = os.path.realpath(start_path or os.path.expanduser('~'))
        self.entries = []           # List[FileEntry]
        self.selected_index = 0
        self.show_hidden = False
        self.error_message = None
        self.window_menu = WindowMenu({
            'File': [
                ('Open       Enter', 'fm_open'),
                ('Parent Dir  Bksp', 'fm_parent'),
                ('─────────────',    None),
                ('Close',            'fm_close'),
            ],
            'View': [
                ('Hidden Files   H', 'fm_toggle_hidden'),
                ('Refresh',          'fm_refresh'),
            ],
        })
        self.h = max(self.h, 8)
        self._rebuild_content()

    def _header_lines(self):
        """Number of non-entry header lines at top of content."""
        return 2  # path line + separator line

    def _entry_to_content_index(self, entry_idx):
        """Convert entry index to content list index."""
        return self._header_lines() + entry_idx

    def _content_to_entry_index(self, content_idx):
        """Convert content list index to entry index, or -1 if on header."""
        idx = content_idx - self._header_lines()
        if 0 <= idx < len(self.entries):
            return idx
        return -1

    def _rebuild_content(self):
        """Scan current directory and rebuild content + entries lists."""
        self.entries = []
        self.content = []
        self.error_message = None

        # Header: path bar + separator
        self.content.append(f' 📂 {self.current_path}')
        self.content.append(' ' + '─' * (self.w - 4))

        # Parent directory entry (unless at filesystem root)
        if self.current_path != '/' and os.path.dirname(self.current_path) != self.current_path:
            entry = FileEntry('..', True, os.path.dirname(self.current_path))
            self.entries.append(entry)
            self.content.append(entry.display_text)

        try:
            raw_entries = sorted(os.listdir(self.current_path), key=str.lower)
        except PermissionError:
            self.error_message = 'Permission denied'
            self.content.append('  ⛔ Permission denied')
            self._update_title()
            return
        except OSError as e:
            self.error_message = str(e)
            self.content.append(f'  ⛔ {e}')
            self._update_title()
            return

        dirs = []
        files = []
        for name in raw_entries:
            if not self.show_hidden and name.startswith('.'):
                continue
            full_path = os.path.join(self.current_path, name)
            try:
                if os.path.isdir(full_path):
                    dirs.append(FileEntry(name, True, full_path))
                elif os.path.isfile(full_path):
                    size = os.path.getsize(full_path)
                    files.append(FileEntry(name, False, full_path, size))
            except OSError:
                continue

        for entry in dirs:
            self.entries.append(entry)
            self.content.append(entry.display_text)
        for entry in files:
            self.entries.append(entry)
            self.content.append(entry.display_text)

        if not self.entries:
            self.content.append('  (empty directory)')

        self._update_title()
        self.selected_index = 0
        self.scroll_offset = 0

    def _update_title(self):
        """Update window title to show path basename and entry count."""
        basename = os.path.basename(self.current_path) or '/'
        count = len([e for e in self.entries if e.name != '..'])
        self.title = f'File Manager - {basename} ({count} items)'

    def draw(self, stdscr):
        """Draw file manager with selection highlight."""
        super().draw(stdscr)
        if not self.visible or not self.entries:
            return

        bx, by, bw, bh = self.body_rect()
        sel_content_idx = self._entry_to_content_index(self.selected_index)
        visible_start = self.scroll_offset
        visible_end = self.scroll_offset + bh

        if visible_start <= sel_content_idx < visible_end:
            screen_row = by + (sel_content_idx - self.scroll_offset)
            sel_attr = curses.color_pair(C_FM_SELECTED) | curses.A_BOLD
            display = self.content[sel_content_idx][:bw] if sel_content_idx < len(self.content) else ''
            safe_addstr(stdscr, screen_row, bx, display.ljust(bw), sel_attr)

    def navigate_to(self, path):
        """Navigate to a new directory path."""
        real_path = os.path.realpath(path)
        if os.path.isdir(real_path):
            self.current_path = real_path
            self._rebuild_content()

    def navigate_parent(self):
        """Go to parent directory, re-selecting the dir we came from."""
        parent = os.path.dirname(self.current_path)
        if parent != self.current_path:
            old_name = os.path.basename(self.current_path)
            self.navigate_to(parent)
            for i, entry in enumerate(self.entries):
                if entry.name == old_name:
                    self.selected_index = i
                    self._ensure_visible()
                    break

    def activate_selected(self):
        """Activate currently selected entry. Returns ('dir', path) or ('file', path)."""
        if not self.entries:
            return None
        if self.selected_index >= len(self.entries):
            return None
        entry = self.entries[self.selected_index]
        if entry.is_dir:
            self.navigate_to(entry.full_path)
            return ('dir', entry.full_path)
        else:
            return ('file', entry.full_path)

    def select_up(self):
        """Move selection up by one entry."""
        if self.selected_index > 0:
            self.selected_index -= 1
            self._ensure_visible()

    def select_down(self):
        """Move selection down by one entry."""
        if self.selected_index < len(self.entries) - 1:
            self.selected_index += 1
            self._ensure_visible()

    def _ensure_visible(self):
        """Auto-scroll to keep the selected entry visible."""
        _, _, _, bh = self.body_rect()
        sel_content = self._entry_to_content_index(self.selected_index)
        if sel_content < self.scroll_offset:
            self.scroll_offset = sel_content
        elif sel_content >= self.scroll_offset + bh:
            self.scroll_offset = sel_content - bh + 1

    def toggle_hidden(self):
        """Toggle show/hide hidden files."""
        self.show_hidden = not self.show_hidden
        self._rebuild_content()

    def _execute_menu_action(self, action):
        """Execute a window menu action. Returns signal or None."""
        if action == 'fm_open':
            return self.activate_selected()
        elif action == 'fm_parent':
            self.navigate_parent()
        elif action == 'fm_toggle_hidden':
            self.toggle_hidden()
        elif action == 'fm_refresh':
            self._rebuild_content()
        elif action == 'fm_close':
            return ('action', 'close')
        return None

    def handle_click(self, mx, my):
        """Handle a click within the window body. Returns action result or None."""
        # Window menu intercept
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if action:
                    return self._execute_menu_action(action)
                return None

        bx, by, bw, bh = self.body_rect()
        if not (bx <= mx < bx + bw and by <= my < by + bh):
            return None
        content_idx = self.scroll_offset + (my - by)
        entry_idx = self._content_to_entry_index(content_idx)
        if entry_idx >= 0:
            self.selected_index = entry_idx
            return self.activate_selected()
        return None

    def handle_key(self, key):
        """Handle keyboard input for the file manager.
        Returns ('file', path) if a file is opened, else None."""
        # Window menu keyboard handling
        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key)
            if action == 'close_menu':
                return None
            if action:
                return self._execute_menu_action(action)
            return None

        if key == curses.KEY_UP:
            self.select_up()
        elif key == curses.KEY_DOWN:
            self.select_down()
        elif key in (curses.KEY_ENTER, 10, 13):
            return self.activate_selected()
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            self.navigate_parent()
        elif key == curses.KEY_PPAGE:
            _, _, _, bh = self.body_rect()
            for _ in range(max(1, bh - 2)):
                self.select_up()
        elif key == curses.KEY_NPAGE:
            _, _, _, bh = self.body_rect()
            for _ in range(max(1, bh - 2)):
                self.select_down()
        elif key == curses.KEY_HOME:
            self.selected_index = 0
            self._ensure_visible()
        elif key == curses.KEY_END:
            if self.entries:
                self.selected_index = len(self.entries) - 1
                self._ensure_visible()
        elif key == ord('h') or key == ord('H'):
            self.toggle_hidden()
        return None


# ═══════════════════════════════════════════════════════════
# Notepad Window (Text Editor)
# ═══════════════════════════════════════════════════════════

class NotepadWindow(Window):
    """Editable text editor window with word wrap support."""

    def __init__(self, x, y, w, h, filepath=None):
        title = 'Notepad'
        super().__init__(title, x, y, w, h, content=[])
        self.buffer = ['']  # list[str] — one string per logical line
        self.filepath = filepath
        self.modified = False
        self.cursor_line = 0
        self.cursor_col = 0
        self.view_top = 0    # First visible line in buffer
        self.view_left = 0   # Horizontal scroll offset
        self.wrap_mode = False
        self._wrap_cache = []       # list[(buf_line, start_col, text)]
        self._wrap_cache_w = -1     # Width used to build cache
        self._wrap_stale = True
        self.window_menu = WindowMenu({
            'File': [
                ('New',       'np_new'),
                ('─────────', None),
                ('Close',     'np_close'),
            ],
            'View': [
                ('Word Wrap  Ctrl+W', 'np_toggle_wrap'),
            ],
        })
        self.h = max(self.h, 8)

        if filepath:
            self._load_file(filepath)

    def _load_file(self, filepath):
        """Load file content into buffer."""
        self.filepath = filepath
        filename = os.path.basename(filepath)
        self.title = f'Notepad - {filename}'
        try:
            with open(filepath, 'r', errors='replace') as f:
                raw = f.read()
            self.buffer = raw.split('\n')
            if self.buffer and self.buffer[-1] == '':
                pass  # Keep trailing empty line
        except (PermissionError, OSError):
            self.buffer = ['(Error reading file)']
        self.cursor_line = 0
        self.cursor_col = 0
        self.view_top = 0
        self.view_left = 0
        self.modified = False
        self._wrap_stale = True

    def _invalidate_wrap(self):
        """Mark wrap cache as needing rebuild."""
        self._wrap_stale = True

    def _compute_wrap(self, body_w):
        """Build wrap cache: list of (buf_line_idx, start_col, text) tuples."""
        if not self._wrap_stale and self._wrap_cache_w == body_w:
            return
        self._wrap_cache = []
        self._wrap_cache_w = body_w
        wrap_w = max(1, body_w - 1)  # -1 for scrollbar column
        for i, line in enumerate(self.buffer):
            if not line:
                self._wrap_cache.append((i, 0, ''))
            elif not self.wrap_mode or len(line) <= wrap_w:
                self._wrap_cache.append((i, 0, line))
            else:
                # Word wrap
                pos = 0
                while pos < len(line):
                    chunk = line[pos:pos + wrap_w]
                    self._wrap_cache.append((i, pos, chunk))
                    pos += wrap_w
        self._wrap_stale = False

    def _cursor_to_wrap_row(self, body_w):
        """Find the wrap row that contains the cursor. Returns index into _wrap_cache."""
        self._compute_wrap(body_w)
        wrap_w = max(1, body_w - 1)
        for idx, (buf_line, start_col, text) in enumerate(self._wrap_cache):
            if buf_line == self.cursor_line:
                if self.wrap_mode:
                    if start_col <= self.cursor_col < start_col + wrap_w:
                        return idx
                    if start_col + wrap_w > len(self.buffer[self.cursor_line]):
                        return idx  # Last segment of this line
                else:
                    return idx
        return 0

    def _ensure_cursor_visible(self):
        """Auto-scroll viewport to keep cursor visible."""
        bx, by, bw, bh = self.body_rect()
        body_h = bh - 1  # -1 for status bar row

        if self.wrap_mode:
            self._compute_wrap(bw)
            wrap_row = self._cursor_to_wrap_row(bw)
            if wrap_row < self.view_top:
                self.view_top = wrap_row
            elif wrap_row >= self.view_top + body_h:
                self.view_top = wrap_row - body_h + 1
        else:
            # Vertical
            if self.cursor_line < self.view_top:
                self.view_top = self.cursor_line
            elif self.cursor_line >= self.view_top + body_h:
                self.view_top = self.cursor_line - body_h + 1
            # Horizontal
            col_w = bw - 1  # -1 for scrollbar
            if self.cursor_col < self.view_left:
                self.view_left = self.cursor_col
            elif self.cursor_col >= self.view_left + col_w:
                self.view_left = self.cursor_col - col_w + 1

    def _clamp_cursor(self):
        """Ensure cursor is within valid buffer bounds."""
        if self.cursor_line < 0:
            self.cursor_line = 0
        if self.cursor_line >= len(self.buffer):
            self.cursor_line = len(self.buffer) - 1
        line = self.buffer[self.cursor_line]
        if self.cursor_col > len(line):
            self.cursor_col = len(line)
        if self.cursor_col < 0:
            self.cursor_col = 0

    def draw(self, stdscr):
        """Draw notepad with buffer, cursor, and status bar."""
        if not self.visible:
            return

        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        body_h = bh - 1  # Last row is status bar

        # Body background
        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, ' ' * bw, body_attr)

        if self.wrap_mode:
            self._compute_wrap(bw)
            visible = self._wrap_cache[self.view_top:self.view_top + body_h]
            cursor_wrap_row = self._cursor_to_wrap_row(bw)

            for i, (buf_line, start_col, text) in enumerate(visible):
                display = text[:bw - 1]
                safe_addstr(stdscr, by + i, bx, display, body_attr)
                # Draw cursor
                global_row = self.view_top + i
                if global_row == cursor_wrap_row:
                    cx = self.cursor_col - start_col
                    if 0 <= cx < bw - 1:
                        ch = text[cx] if cx < len(text) else ' '
                        safe_addstr(stdscr, by + i, bx + cx, ch, body_attr | curses.A_REVERSE)
        else:
            col_w = bw - 1  # -1 for scrollbar column
            for i in range(body_h):
                buf_idx = self.view_top + i
                if buf_idx >= len(self.buffer):
                    break
                line = self.buffer[buf_idx]
                display = line[self.view_left:self.view_left + col_w]
                safe_addstr(stdscr, by + i, bx, display, body_attr)
                # Draw cursor
                if buf_idx == self.cursor_line:
                    cx = self.cursor_col - self.view_left
                    if 0 <= cx < col_w:
                        ch = line[self.cursor_col] if self.cursor_col < len(line) else ' '
                        safe_addstr(stdscr, by + i, bx + cx, ch, body_attr | curses.A_REVERSE)

        # Scrollbar
        total_lines = len(self._wrap_cache) if self.wrap_mode else len(self.buffer)
        if total_lines > body_h and body_h > 1:
            sb_x = bx + bw - 1
            thumb_pos = int(self.view_top / max(1, total_lines - body_h) * (body_h - 1))
            for i in range(body_h):
                ch = '█' if i == thumb_pos else '░'
                safe_addstr(stdscr, by + i, sb_x, ch, curses.color_pair(C_SCROLLBAR))

        # Status bar (inside window, last body row)
        status_y = by + bh - 1
        mod_flag = ' [Modified]' if self.modified else ''
        wrap_flag = ' WRAP' if self.wrap_mode else ''
        status = f' Ln {self.cursor_line + 1}, Col {self.cursor_col + 1}{wrap_flag}{mod_flag}'
        safe_addstr(stdscr, status_y, bx, status.ljust(bw)[:bw], curses.color_pair(C_STATUS))

        # Window menu dropdown (on top of body content)
        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def _execute_menu_action(self, action):
        """Execute a window menu action. Returns signal or None."""
        if action == 'np_toggle_wrap':
            self.wrap_mode = not self.wrap_mode
            self.view_left = 0
            self._invalidate_wrap()
            self._ensure_cursor_visible()
        elif action == 'np_new':
            return ('action', 'notepad')
        elif action == 'np_close':
            return ('action', 'close')
        return None

    def handle_key(self, key):
        """Handle keyboard input for the editor. Returns None always."""
        # Window menu keyboard handling
        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key)
            if action == 'close_menu':
                return None
            if action:
                return self._execute_menu_action(action)
            return None

        # Navigation
        if key == curses.KEY_UP:
            if self.cursor_line > 0:
                self.cursor_line -= 1
                self._clamp_cursor()
                self._ensure_cursor_visible()
        elif key == curses.KEY_DOWN:
            if self.cursor_line < len(self.buffer) - 1:
                self.cursor_line += 1
                self._clamp_cursor()
                self._ensure_cursor_visible()
        elif key == curses.KEY_LEFT:
            if self.cursor_col > 0:
                self.cursor_col -= 1
            elif self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = len(self.buffer[self.cursor_line])
            self._ensure_cursor_visible()
        elif key == curses.KEY_RIGHT:
            line = self.buffer[self.cursor_line]
            if self.cursor_col < len(line):
                self.cursor_col += 1
            elif self.cursor_line < len(self.buffer) - 1:
                self.cursor_line += 1
                self.cursor_col = 0
            self._ensure_cursor_visible()
        elif key == curses.KEY_HOME:
            self.cursor_col = 0
            self._ensure_cursor_visible()
        elif key == curses.KEY_END:
            self.cursor_col = len(self.buffer[self.cursor_line])
            self._ensure_cursor_visible()
        elif key == curses.KEY_PPAGE:
            _, _, _, bh = self.body_rect()
            self.cursor_line = max(0, self.cursor_line - (bh - 2))
            self._clamp_cursor()
            self._ensure_cursor_visible()
        elif key == curses.KEY_NPAGE:
            _, _, _, bh = self.body_rect()
            self.cursor_line = min(len(self.buffer) - 1, self.cursor_line + (bh - 2))
            self._clamp_cursor()
            self._ensure_cursor_visible()

        # Editing: Enter
        elif key in (curses.KEY_ENTER, 10, 13):
            line = self.buffer[self.cursor_line]
            before = line[:self.cursor_col]
            after = line[self.cursor_col:]
            self.buffer[self.cursor_line] = before
            self.buffer.insert(self.cursor_line + 1, after)
            self.cursor_line += 1
            self.cursor_col = 0
            self.modified = True
            self._invalidate_wrap()
            self._ensure_cursor_visible()

        # Editing: Backspace
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor_col > 0:
                line = self.buffer[self.cursor_line]
                self.buffer[self.cursor_line] = line[:self.cursor_col - 1] + line[self.cursor_col:]
                self.cursor_col -= 1
                self.modified = True
                self._invalidate_wrap()
            elif self.cursor_line > 0:
                # Merge with previous line
                prev_line = self.buffer[self.cursor_line - 1]
                self.cursor_col = len(prev_line)
                self.buffer[self.cursor_line - 1] = prev_line + self.buffer[self.cursor_line]
                self.buffer.pop(self.cursor_line)
                self.cursor_line -= 1
                self.modified = True
                self._invalidate_wrap()
            self._ensure_cursor_visible()

        # Editing: Delete
        elif key == curses.KEY_DC:
            line = self.buffer[self.cursor_line]
            if self.cursor_col < len(line):
                self.buffer[self.cursor_line] = line[:self.cursor_col] + line[self.cursor_col + 1:]
                self.modified = True
                self._invalidate_wrap()
            elif self.cursor_line < len(self.buffer) - 1:
                # Merge with next line
                self.buffer[self.cursor_line] = line + self.buffer[self.cursor_line + 1]
                self.buffer.pop(self.cursor_line + 1)
                self.modified = True
                self._invalidate_wrap()

        # Toggle: Ctrl+W (key 23)
        elif key == 23:
            self.wrap_mode = not self.wrap_mode
            self.view_left = 0
            self._invalidate_wrap()
            self._ensure_cursor_visible()

        # Printable characters
        elif 32 <= key <= 126:
            ch = chr(key)
            line = self.buffer[self.cursor_line]
            self.buffer[self.cursor_line] = line[:self.cursor_col] + ch + line[self.cursor_col:]
            self.cursor_col += 1
            self.modified = True
            self._invalidate_wrap()
            self._ensure_cursor_visible()

        return None

    def handle_click(self, mx, my):
        """Handle click in the body — place cursor or interact with menu."""
        # Window menu intercept
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if action:
                    return self._execute_menu_action(action)
                return None

        bx, by, bw, bh = self.body_rect()
        body_h = bh - 1  # -1 for status bar

        if not (bx <= mx < bx + bw and by <= my < by + body_h):
            return None

        row_in_view = my - by
        col_in_view = mx - bx

        if self.wrap_mode:
            self._compute_wrap(bw)
            wrap_idx = self.view_top + row_in_view
            if wrap_idx < len(self._wrap_cache):
                buf_line, start_col, text = self._wrap_cache[wrap_idx]
                self.cursor_line = buf_line
                self.cursor_col = min(start_col + col_in_view, len(self.buffer[buf_line]))
            else:
                self.cursor_line = len(self.buffer) - 1
                self.cursor_col = len(self.buffer[self.cursor_line])
        else:
            target_line = self.view_top + row_in_view
            if target_line < len(self.buffer):
                self.cursor_line = target_line
                self.cursor_col = min(self.view_left + col_in_view, len(self.buffer[target_line]))
            else:
                self.cursor_line = len(self.buffer) - 1
                self.cursor_col = len(self.buffer[self.cursor_line])

        self._clamp_cursor()
        return None

    def scroll_up(self):
        """Scroll viewport up (for scroll wheel)."""
        if self.view_top > 0:
            self.view_top -= 1

    def scroll_down(self):
        """Scroll viewport down (for scroll wheel)."""
        _, _, bw, bh = self.body_rect()
        body_h = bh - 1
        total = len(self._wrap_cache) if self.wrap_mode else len(self.buffer)
        max_top = max(0, total - body_h)
        if self.view_top < max_top:
            self.view_top += 1


# ═══════════════════════════════════════════════════════════
# ASCII Video Helpers
# ═══════════════════════════════════════════════════════════

VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.webm', '.avi', '.mov', '.m4v', '.mpg', '.mpeg', '.wmv'
}


def is_video_file(filepath):
    """Return True if filepath extension looks like video."""
    _, ext = os.path.splitext(filepath.lower())
    return ext in VIDEO_EXTENSIONS


# ═══════════════════════════════════════════════════════════
# System Info
# ═══════════════════════════════════════════════════════════

def get_system_info():
    """Get system information for About dialog."""
    info = []
    try:
        uname = os.uname()
        info.append(f'OS: {uname.sysname} {uname.release}')
        info.append(f'Host: {uname.nodename}')
        info.append(f'Arch: {uname.machine}')
    except Exception:
        info.append('OS: Linux')

    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemTotal'):
                    mem_kb = int(line.split()[1])
                    info.append(f'RAM: {mem_kb // 1024} MB')
                    break
    except Exception:
        pass

    info.append(f'Terminal: {os.environ.get("TERM", "unknown")}')
    info.append(f'Shell: {os.path.basename(os.environ.get("SHELL", "unknown"))}')
    info.append(f'Python: {sys.version.split()[0]}')
    return info


# ═══════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════

class RetroTUI:
    """Main application class."""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.running = True
        self.windows = []
        self.menu = Menu()
        self.dialog = None
        self.selected_icon = -1
        self.use_unicode = check_unicode_support()
        self.icons = ICONS if self.use_unicode else ICONS_ASCII

        # Setup curses
        curses.curs_set(0)
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        stdscr.nodelay(False)
        stdscr.timeout(500)  # 500ms for clock updates

        # Disable XON/XOFF flow control so Ctrl+Q/Ctrl+S reach the app
        try:
            fd = sys.stdin.fileno()
            attrs = termios.tcgetattr(fd)
            attrs[0] &= ~termios.IXON   # Disable XON/XOFF output control
            attrs[0] &= ~termios.IXOFF   # Disable XON/XOFF input control
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
        except (termios.error, ValueError, OSError):
            pass  # Not a real terminal or unsupported

        # Enable mouse
        curses.mousemask(
            curses.ALL_MOUSE_EVENTS |
            curses.REPORT_MOUSE_POSITION
        )
        # Enable SGR extended mouse mode for better coordinate support
        # Use 1002 (button-event tracking) — reports motion only while button held
        # This gives us implicit release detection: motion events stop when released
        print('\033[?1002h', end='', flush=True)  # Button-event tracking (drag)
        print('\033[?1006h', end='', flush=True)  # SGR extended mode

        init_colors()

        # Create a welcome window
        h, w = stdscr.getmaxyx()
        welcome_content = [
            '',
            '   ╔══════════════════════════════════════╗',
            '   ║      Welcome to RetroTUI v0.3.2        ║',
            '   ║                                      ║',
            '   ║  A Windows 3.1 style desktop         ║',
            '   ║  environment for the Linux console.  ║',
            '   ║                                      ║',
            '   ║  New in v0.3.2:                      ║',
            '   ║  • ASCII Video Player (mpv/mplayer)   ║',
            '   ║  • Per-window menus (File, View)     ║',
            '   ║  • Text editor (Notepad)             ║',
            '   ║  • Window resize (drag borders)      ║',
            '   ║                                      ║',
            '   ║  Use mouse or keyboard to navigate.  ║',
            '   ║  Press Ctrl+Q to exit.               ║',
            '   ╚══════════════════════════════════════╝',
            '',
        ]
        win = Window('Welcome to RetroTUI', w // 2 - 25, h // 2 - 10, 50, 20,
                      content=welcome_content)
        win.active = True
        self.windows.append(win)

    def cleanup(self):
        """Restore terminal state."""
        print('\033[?1002l', end='', flush=True)
        print('\033[?1006l', end='', flush=True)

    def draw_desktop(self):
        """Draw the desktop background pattern."""
        h, w = self.stdscr.getmaxyx()
        attr = curses.color_pair(C_DESKTOP)
        pattern = DESKTOP_PATTERN

        for row in range(1, h - 1):
            line = (pattern * (w // len(pattern) + 1))[:w - 1]
            safe_addstr(self.stdscr, row, 0, line, attr)

    def draw_icons(self):
        """Draw desktop icons (3x4 art + label)."""
        h, w = self.stdscr.getmaxyx()
        start_x = 3
        start_y = 3
        spacing_y = 5  # 3 lines art + 1 label + 1 gap

        for i, icon in enumerate(self.icons):
            y = start_y + i * spacing_y
            if y + 3 >= h - 1:
                break
            is_sel = (i == self.selected_icon)
            attr = curses.color_pair(C_ICON_SEL if is_sel else C_ICON) | curses.A_BOLD
            # Draw 3-line art
            for row, line in enumerate(icon['art']):
                safe_addstr(self.stdscr, y + row, start_x, line, attr)
            # Draw label centered below art
            label = icon['label'].center(len(icon['art'][0]))
            safe_addstr(self.stdscr, y + 3, start_x, label, attr)

    def draw_taskbar(self):
        """Draw taskbar row with minimized window buttons."""
        h, w = self.stdscr.getmaxyx()
        taskbar_y = h - 2
        minimized = [win for win in self.windows if win.minimized]
        if not minimized:
            return
        attr = curses.color_pair(C_TASKBAR)
        safe_addstr(self.stdscr, taskbar_y, 0, ' ' * (w - 1), attr)
        x = 1
        for win in minimized:
            label = win.title[:15]
            btn = f'[{label}]'
            if x + len(btn) >= w - 1:
                break
            safe_addstr(self.stdscr, taskbar_y, x, btn, attr | curses.A_BOLD)
            x += len(btn) + 1

    def draw_statusbar(self):
        """Draw the bottom status bar."""
        h, w = self.stdscr.getmaxyx()
        attr = curses.color_pair(C_STATUS)
        visible = sum(1 for win in self.windows if win.visible)
        total = len(self.windows)
        status = f' RetroTUI v0.3.2 │ Windows: {visible}/{total} │ Mouse: Enabled │ Ctrl+Q: Exit'
        safe_addstr(self.stdscr, h - 1, 0, status.ljust(w - 1), attr)

    def get_icon_at(self, mx, my):
        """Return icon index at mouse position, or -1."""
        start_x = 3
        start_y = 3
        spacing_y = 5  # Must match draw_icons

        for i in range(len(self.icons)):
            iy = start_y + i * spacing_y
            icon_w = len(self.icons[i]['art'][0])
            if iy <= my <= iy + 3 and start_x <= mx <= start_x + icon_w - 1:
                return i
        return -1

    def set_active_window(self, win):
        """Set a window as active (bring to front)."""
        for w in self.windows:
            w.active = False
        win.active = True
        # Move to end of list (top of z-order)
        self.windows.remove(win)
        self.windows.append(win)

    def close_window(self, win):
        """Close a window."""
        self.windows.remove(win)
        if self.windows:
            self.windows[-1].active = True

    def execute_action(self, action):
        """Execute a menu/icon action."""
        h, w = self.stdscr.getmaxyx()

        if action == 'exit':
            self.dialog = Dialog(
                'Exit RetroTUI',
                'Are you sure you want to exit?\n\nAll windows will be closed.',
                ['Yes', 'No'],
                width=44
            )

        elif action == 'about':
            sys_info = get_system_info()
            msg = ('RetroTUI v0.3.2\n'
                   'A retro desktop environment for Linux console.\n\n'
                   'System Information:\n' +
                   '\n'.join(sys_info) + '\n\n'
                   'Mouse: GPM/xterm protocol\n'
                   'No X11 required!')
            self.dialog = Dialog('About RetroTUI', msg, ['OK'], width=52)

        elif action == 'help':
            msg = ('Keyboard Controls:\n\n'
                   'Tab       - Cycle windows\n'
                   'Escape    - Close menu/dialog\n'
                   'Enter     - Activate selection\n'
                   'Ctrl+Q    - Exit\n'
                   'F10       - Open menu\n'
                   'Arrow keys - Navigate\n'
                   'PgUp/PgDn - Scroll content\n\n'
                   'File Manager:\n\n'
                   'Up/Down   - Move selection\n'
                   'Enter     - Open dir/file\n'
                   'Backspace - Parent directory\n'
                   'H         - Toggle hidden files\n'
                   'Home/End  - First/last entry\n\n'
                   'Notepad Editor:\n\n'
                   'Arrows    - Move cursor\n'
                   'Home/End  - Start/end of line\n'
                   'PgUp/PgDn - Page up/down\n'
                   'Backspace - Delete backward\n'
                   'Delete    - Delete forward\n'
                   'Ctrl+W    - Toggle word wrap\n\n'
                   'Mouse Controls:\n\n'
                   'Click     - Select/activate\n'
                   'Drag title - Move window\n'
                   'Drag border - Resize window\n'
                   'Dbl-click title - Maximize\n'
                   '[─]       - Minimize\n'
                   '[□]       - Maximize/restore\n'
                   'Scroll    - Scroll/select')
            self.dialog = Dialog('Keyboard & Mouse Help', msg, ['OK'], width=46)

        elif action == 'filemanager':
            offset_x = 15 + len(self.windows) * 2
            offset_y = 3 + len(self.windows) * 1
            win = FileManagerWindow(offset_x, offset_y, 58, 22)
            self.windows.append(win)
            self.set_active_window(win)

        elif action == 'notepad':
            offset_x = 20 + len(self.windows) * 2
            offset_y = 4 + len(self.windows) * 1
            win = NotepadWindow(offset_x, offset_y, 60, 20)
            self.windows.append(win)
            self.set_active_window(win)

        elif action == 'asciivideo':
            self.dialog = Dialog(
                'ASCII Video',
                'Reproduce video en la terminal.\n\n'
                'Usa mpv (color) o mplayer (fallback).\n'
                'Abre un video desde File Manager.',
                ['OK'],
                width=50,
            )

        elif action == 'terminal':
            content = [
                f' user@{os.uname().nodename}:~$ _',
                '',
                ' (Terminal emulation placeholder)',
                ' Future: embedded terminal via pty',
            ]
            offset_x = 18 + len(self.windows) * 2
            offset_y = 5 + len(self.windows) * 1
            win = Window('Terminal', offset_x, offset_y, 60, 15, content=content)
            self.windows.append(win)
            self.set_active_window(win)

        elif action == 'settings':
            content = [
                ' ╔═ Display Settings ══════════════════════╗',
                ' ║                                         ║',
                ' ║  Theme: [x] Windows 3.1                 ║',
                ' ║         [ ] DOS / CGA                   ║',
                ' ║         [ ] Windows 95                  ║',
                ' ║                                         ║',
                ' ║  Desktop Pattern: ░ ▒ ▓                 ║',
                ' ║                                         ║',
                ' ║  Colors: 256-color mode                 ║',
                ' ║                                         ║',
                ' ╚═════════════════════════════════════════╝',
            ]
            offset_x = 22 + len(self.windows) * 2
            offset_y = 4 + len(self.windows) * 1
            win = Window('Settings', offset_x, offset_y, 48, 15, content=content)
            self.windows.append(win)
            self.set_active_window(win)

        elif action == 'new_window':
            offset_x = 20 + len(self.windows) * 2
            offset_y = 3 + len(self.windows) * 1
            win = Window(f'Window {Window._next_id}', offset_x, offset_y, 40, 12,
                          content=['', ' New empty window', ''])
            self.windows.append(win)
            self.set_active_window(win)

    def play_ascii_video(self, filepath):
        """Play video in terminal using mpv (preferred) or mplayer (fallback)."""
        mpv = shutil.which('mpv')
        mplayer = shutil.which('mplayer')

        if not mpv and not mplayer:
            self.dialog = Dialog(
                'ASCII Video Error',
                'No se encontró mpv ni mplayer.\n\n'
                'Instala uno de los siguientes:\n'
                '  sudo apt install mpv\n'
                '  sudo apt install mplayer',
                ['OK'],
                width=50,
            )
            return

        # Build command list: try best option first
        if mpv:
            commands = [
                ([mpv, '--vo=tct', '--really-quiet', filepath], 'mpv (tct)'),
                ([mpv, '--vo=tct', '--really-quiet', '--ao=null', filepath], 'mpv (tct, no audio)'),
            ]
        else:
            commands = [
                ([mplayer, '-vo', 'caca', '-really-quiet', filepath], 'mplayer (caca)'),
                ([mplayer, '-vo', 'caca', '-really-quiet', '-ao', 'null', filepath], 'mplayer (caca, no audio)'),
                ([mplayer, '-vo', 'aa', '-really-quiet', '-ao', 'null', filepath], 'mplayer (aa, no audio)'),
            ]

        exit_code = 1
        backend_used = ''
        try:
            curses.def_prog_mode()
            curses.endwin()
            for cmd, name in commands:
                start = time.time()
                result = subprocess.run(cmd)
                elapsed = time.time() - start
                exit_code = result.returncode
                backend_used = name
                if exit_code == 0 or elapsed > 2:
                    break  # Video played (even if audio failed)
        except OSError as e:
            self.dialog = Dialog('ASCII Video Error', f'No se pudo ejecutar:\n{e}', ['OK'], width=58)
            return
        finally:
            try:
                curses.reset_prog_mode()
                self.stdscr.refresh()
            except curses.error:
                pass

    def open_file_viewer(self, filepath):
        """Open file in best viewer: ASCII video or Notepad."""
        h, w = self.stdscr.getmaxyx()
        filename = os.path.basename(filepath)

        if is_video_file(filepath):
            self.play_ascii_video(filepath)
            return

        # Check if file seems to be binary
        try:
            with open(filepath, 'rb') as f:
                chunk = f.read(1024)
                if b'\x00' in chunk:
                    self.dialog = Dialog('Binary File',
                        f'{filename}\n\nThis appears to be a binary file\nand cannot be displayed as text.',
                        ['OK'], width=48)
                    return
        except OSError:
            pass

        # Create NotepadWindow with file
        offset_x = 18 + len(self.windows) * 2
        offset_y = 3 + len(self.windows)
        win_w = min(70, w - 4)
        win_h = min(25, h - 4)
        win = NotepadWindow(offset_x, offset_y, win_w, win_h, filepath=filepath)
        self.windows.append(win)
        self.set_active_window(win)

    def handle_taskbar_click(self, mx, my):
        """Handle click on taskbar row. Returns True if handled."""
        h, w = self.stdscr.getmaxyx()
        taskbar_y = h - 2
        if my != taskbar_y:
            return False
        minimized = [win for win in self.windows if win.minimized]
        if not minimized:
            return False
        x = 1
        for win in minimized:
            label = win.title[:15]
            btn_w = len(label) + 2  # [label]
            if x <= mx < x + btn_w:
                win.toggle_minimize()
                self.set_active_window(win)
                return True
            x += btn_w + 1
        return False

    def handle_mouse(self, event):
        """Handle mouse events."""
        try:
            _, mx, my, _, bstate = event
        except Exception:
            return

        # Dialog takes priority
        if self.dialog:
            if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_DOUBLE_CLICKED):
                result = self.dialog.handle_click(mx, my)
                if result >= 0:
                    btn_text = self.dialog.buttons[result]
                    if self.dialog.title == 'Exit RetroTUI' and btn_text == 'Yes':
                        self.running = False
                    self.dialog = None
            return

        # Menu bar click
        if my == 0 and (bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_DOUBLE_CLICKED)):
            action = self.menu.handle_click(mx, my)
            if action:
                self.execute_action(action)
            return

        # Menu dropdown handling (when menu is active)
        if self.menu.active:
            # Mouse movement — update hover highlight, don't close
            if bstate & curses.REPORT_MOUSE_POSITION:
                self.menu.handle_hover(mx, my)
                return
            # Actual click — select item or close menu
            if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_DOUBLE_CLICKED):
                action = self.menu.handle_click(mx, my)
                if action:
                    self.execute_action(action)
                return
            # For any other mouse event while menu is active, check if inside menu area
            if self.menu.hit_test_dropdown(mx, my) or my == 0:
                return  # Stay active, absorb event

        # Taskbar click — restore minimized windows
        if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_DOUBLE_CLICKED):
            if self.handle_taskbar_click(mx, my):
                return

        # Window dragging — check FIRST, before window clicks
        any_dragging = any(w.dragging for w in self.windows)
        if any_dragging:
            stop_flags = (curses.BUTTON1_CLICKED | curses.BUTTON1_RELEASED |
                          curses.BUTTON1_DOUBLE_CLICKED)
            if bstate & stop_flags:
                for win in self.windows:
                    win.dragging = False
                return
            for win in self.windows:
                if win.dragging:
                    h, w = self.stdscr.getmaxyx()
                    new_x = mx - win.drag_offset_x
                    new_y = my - win.drag_offset_y
                    win.x = max(0, min(new_x, w - win.w))
                    win.y = max(1, min(new_y, h - win.h - 1))
                    return
            return

        # Window resizing — parallel to dragging
        any_resizing = any(w.resizing for w in self.windows)
        if any_resizing:
            stop_flags = (curses.BUTTON1_CLICKED | curses.BUTTON1_RELEASED |
                          curses.BUTTON1_DOUBLE_CLICKED)
            if bstate & stop_flags:
                for win in self.windows:
                    win.resizing = False
                    win.resize_edge = None
                return
            for win in self.windows:
                if win.resizing:
                    h, w = self.stdscr.getmaxyx()
                    win.apply_resize(mx, my, w, h)
                    return
            return

        # Check windows (reverse z-order for top window first)
        for win in reversed(self.windows):
            if not win.visible:
                continue

            click_flags = curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_DOUBLE_CLICKED

            # Close button [×]
            if win.on_close_button(mx, my) and (bstate & click_flags):
                self.close_window(win)
                return

            # Minimize button [─]
            if win.on_minimize_button(mx, my) and (bstate & click_flags):
                self.set_active_window(win)
                win.toggle_minimize()
                # Activate next visible window
                visible = [w for w in self.windows if w.visible]
                if visible:
                    self.set_active_window(visible[-1])
                return

            # Maximize button [□]
            if win.on_maximize_button(mx, my) and (bstate & click_flags):
                self.set_active_window(win)
                h, w = self.stdscr.getmaxyx()
                win.toggle_maximize(w, h)
                return

            # Border resize (check before title bar to capture corners)
            if bstate & curses.BUTTON1_PRESSED:
                edge = win.on_border(mx, my)
                if edge:
                    win.resizing = True
                    win.resize_edge = edge
                    self.set_active_window(win)
                    return

            # Title bar — drag or double-click maximize
            if win.on_title_bar(mx, my):
                if bstate & curses.BUTTON1_DOUBLE_CLICKED:
                    self.set_active_window(win)
                    h, w = self.stdscr.getmaxyx()
                    win.toggle_maximize(w, h)
                    return
                elif bstate & curses.BUTTON1_PRESSED:
                    if not win.maximized:
                        win.dragging = True
                        win.drag_offset_x = mx - win.x
                        win.drag_offset_y = my - win.y
                    self.set_active_window(win)
                    return
                elif bstate & curses.BUTTON1_CLICKED:
                    self.set_active_window(win)
                    return

            # Window menu hover tracking
            if (bstate & curses.REPORT_MOUSE_POSITION) and win.window_menu and win.window_menu.active:
                if win.window_menu.handle_hover(mx, my, win.x, win.y, win.w):
                    return

            # Click outside window with active menu — close menu
            if win.window_menu and win.window_menu.active and not win.contains(mx, my):
                if bstate & click_flags:
                    win.window_menu.active = False
                    # Don't return — let click propagate to other windows

            if win.contains(mx, my):
                if bstate & click_flags:
                    self.set_active_window(win)
                    # Close other windows' menus when clicking on a different window
                    for other_win in self.windows:
                        if other_win is not win and other_win.window_menu and other_win.window_menu.active:
                            other_win.window_menu.active = False
                    # Delegate click to window if it has a handler
                    if hasattr(win, 'handle_click'):
                        result = win.handle_click(mx, my)
                        if result and result[0] == 'file':
                            self.open_file_viewer(result[1])
                        elif result and result[0] == 'action':
                            if result[1] == 'close':
                                self.close_window(win)
                            else:
                                self.execute_action(result[1])
                    return
                # Scroll wheel
                if bstate & curses.BUTTON4_PRESSED:  # Scroll up
                    if hasattr(win, 'select_up'):
                        for _ in range(3):
                            win.select_up()
                    else:
                        win.scroll_up()
                    return
                if bstate & 0x200000:  # Scroll down (BUTTON5)
                    if hasattr(win, 'select_down'):
                        for _ in range(3):
                            win.select_down()
                    else:
                        win.scroll_down()
                    return

        # Desktop icons — check double-click FIRST (bstate includes CLICKED on double-click)
        if bstate & curses.BUTTON1_DOUBLE_CLICKED:
            icon_idx = self.get_icon_at(mx, my)
            if icon_idx >= 0:
                self.execute_action(self.icons[icon_idx]['action'])
                return

        if bstate & curses.BUTTON1_CLICKED or bstate & curses.BUTTON1_PRESSED:
            icon_idx = self.get_icon_at(mx, my)
            if icon_idx >= 0:
                self.selected_icon = icon_idx
                return

        # Click on desktop - deselect
        self.selected_icon = -1
        self.menu.active = False

    def handle_key(self, key):
        """Handle keyboard input."""
        # Dialog takes priority
        if self.dialog:
            result = self.dialog.handle_key(key)
            if result >= 0:
                btn_text = self.dialog.buttons[result]
                if self.dialog.title == 'Exit RetroTUI' and btn_text == 'Yes':
                    self.running = False
                self.dialog = None
            return

        # Global shortcuts
        if key == 17:  # Ctrl+Q
            self.execute_action('exit')
            return

        # F10: window menu (if active window has one) or global menu
        if key == curses.KEY_F10:
            active_win = next((w for w in self.windows if w.active), None)
            if active_win and active_win.window_menu:
                wm = active_win.window_menu
                wm.active = not wm.active
                if wm.active:
                    wm.selected_menu = 0
                    wm.selected_item = 0
                return
            if self.menu.active:
                self.menu.active = False
            else:
                self.menu.active = True
                self.menu.selected_menu = 0
                self.menu.selected_item = 0
            return

        # Escape: close window menu, then global menu
        if key == 27:
            active_win = next((w for w in self.windows if w.active), None)
            if active_win and active_win.window_menu and active_win.window_menu.active:
                active_win.window_menu.active = False
            elif self.menu.active:
                self.menu.active = False
            return

        # Menu navigation
        if self.menu.active:
            if key == curses.KEY_LEFT:
                self.menu.selected_menu = (self.menu.selected_menu - 1) % len(self.menu.menu_names)
                self.menu.selected_item = 0
            elif key == curses.KEY_RIGHT:
                self.menu.selected_menu = (self.menu.selected_menu + 1) % len(self.menu.menu_names)
                self.menu.selected_item = 0
            elif key == curses.KEY_UP:
                items = self.menu.items[self.menu.menu_names[self.menu.selected_menu]]
                self.menu.selected_item = (self.menu.selected_item - 1) % len(items)
                while items[self.menu.selected_item][1] is None:
                    self.menu.selected_item = (self.menu.selected_item - 1) % len(items)
            elif key == curses.KEY_DOWN:
                items = self.menu.items[self.menu.menu_names[self.menu.selected_menu]]
                self.menu.selected_item = (self.menu.selected_item + 1) % len(items)
                while items[self.menu.selected_item][1] is None:
                    self.menu.selected_item = (self.menu.selected_item + 1) % len(items)
            elif key in (curses.KEY_ENTER, 10, 13):
                menu_name = self.menu.menu_names[self.menu.selected_menu]
                items = self.menu.items[menu_name]
                action = items[self.menu.selected_item][1]
                if action:
                    self.menu.active = False
                    self.execute_action(action)
            return

        # Window focus cycling (skip minimized windows)
        if key == 9:  # Tab
            visible_windows = [w for w in self.windows if w.visible]
            if visible_windows:
                current = next((i for i, w in enumerate(visible_windows) if w.active), -1)
                next_idx = (current + 1) % len(visible_windows)
                for w in self.windows:
                    w.active = False
                visible_windows[next_idx].active = True
            return

        # Delegate to active window
        active_win = next((w for w in self.windows if w.active), None)
        if active_win:
            if hasattr(active_win, 'handle_key'):
                result = active_win.handle_key(key)
                if result and result[0] == 'file':
                    self.open_file_viewer(result[1])
                elif result and result[0] == 'action':
                    if result[1] == 'close':
                        self.close_window(active_win)
                    else:
                        self.execute_action(result[1])
            else:
                # Default scroll behavior for regular windows
                if key == curses.KEY_UP or key == curses.KEY_PPAGE:
                    active_win.scroll_up()
                elif key == curses.KEY_DOWN or key == curses.KEY_NPAGE:
                    active_win.scroll_down()

    def run(self):
        """Main event loop."""
        try:
            while self.running:
                # Clear and redraw
                self.stdscr.erase()
                self.draw_desktop()
                self.draw_icons()

                # Draw windows
                for win in self.windows:
                    win.draw(self.stdscr)

                # Menu bar (on top)
                h, w = self.stdscr.getmaxyx()
                self.menu.draw_bar(self.stdscr, w)
                self.menu.draw_dropdown(self.stdscr)

                # Taskbar (minimized windows)
                self.draw_taskbar()

                # Status bar
                self.draw_statusbar()

                # Dialog on top of everything
                if self.dialog:
                    self.dialog.draw(self.stdscr)

                self.stdscr.noutrefresh()
                curses.doupdate()

                # Handle input
                try:
                    key = self.stdscr.getch()
                except curses.error:
                    continue

                if key == -1:
                    continue
                elif key == curses.KEY_MOUSE:
                    try:
                        event = curses.getmouse()
                        self.handle_mouse(event)
                    except curses.error:
                        pass
                elif key == curses.KEY_RESIZE:
                    curses.update_lines_cols()
                    # Reclamp windows to new terminal size
                    new_h, new_w = self.stdscr.getmaxyx()
                    for win in self.windows:
                        win.x = max(0, min(win.x, new_w - min(win.w, new_w)))
                        win.y = max(1, min(win.y, new_h - min(win.h, new_h) - 1))
                else:
                    self.handle_key(key)
        finally:
            self.cleanup()


# ═══════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════

def main(stdscr):
    app = RetroTUI(stdscr)
    app.run()


if __name__ == '__main__':
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # Ensure terminal is restored even on error
        curses.endwin()
        print(f'\nError: {e}')
        import traceback
        traceback.print_exc()

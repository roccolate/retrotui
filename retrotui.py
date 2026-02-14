#!/usr/bin/env python3
"""
RetroTUI v0.2 — Entorno de escritorio retro estilo Windows 3.1
Funciona en consola Linux sin X11. Soporte de mouse vía GPM o xterm protocol.
"""

import curses
import time
import os
import subprocess
import locale

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
DESKTOP_PATTERNS = ['░', '▒', '·']
DESKTOP_PATTERN = '░'

# Icons (text representation)
ICONS = [
    {'symbol': '📁', 'label': 'Files',     'action': 'filemanager'},
    {'symbol': '📝', 'label': 'Notepad',   'action': 'notepad'},
    {'symbol': '💻', 'label': 'Terminal',   'action': 'terminal'},
    {'symbol': '⚙️',  'label': 'Settings',  'action': 'settings'},
    {'symbol': 'ℹ️',  'label': 'About',     'action': 'about'},
]

# Fallback ASCII icons for non-Unicode terminals
ICONS_ASCII = [
    {'symbol': '[D]', 'label': 'Files',     'action': 'filemanager'},
    {'symbol': '[N]', 'label': 'Notepad',   'action': 'notepad'},
    {'symbol': '[>]', 'label': 'Terminal',   'action': 'terminal'},
    {'symbol': '[S]', 'label': 'Settings',  'action': 'settings'},
    {'symbol': '[?]', 'label': 'About',     'action': 'about'},
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
    else:
        curses.init_pair(C_DESKTOP,       curses.COLOR_CYAN, curses.COLOR_CYAN)
        curses.init_pair(C_WIN_TITLE,     curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(C_WIN_INACTIVE,  curses.COLOR_BLACK, curses.COLOR_WHITE)

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
    curses.init_pair(C_ICON,          curses.COLOR_WHITE, curses.COLOR_CYAN)
    curses.init_pair(C_ICON_SEL,      curses.COLOR_YELLOW, curses.COLOR_BLUE)
    curses.init_pair(C_SCROLLBAR,     curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_FM_SELECTED,   curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(C_FM_DIR,        curses.COLOR_BLUE, curses.COLOR_WHITE)


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


def center_text(text, width):
    """Center text within a given width."""
    pad = (width - len(text)) // 2
    return ' ' * max(0, pad) + text


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

    def title_bar_rect(self):
        """Return (x, y, w, h) of the title bar area."""
        return (self.x + 1, self.y, self.w - 2, 1)

    def close_button_pos(self):
        """Return (x, y) of the close button."""
        return (self.x + self.w - 4, self.y)

    def body_rect(self):
        """Return inner content area (x, y, w, h)."""
        return (self.x + 1, self.y + 1, self.w - 2, self.h - 2)

    def contains(self, mx, my):
        """Check if point is within window bounds."""
        return (self.x <= mx < self.x + self.w and
                self.y <= my < self.y + self.h)

    def on_title_bar(self, mx, my):
        """Check if point is on the title bar."""
        return (self.x + 1 <= mx < self.x + self.w - 4 and my == self.y)

    def on_close_button(self, mx, my):
        """Check if point is on the close button."""
        cx, cy = self.close_button_pos()
        return (cx <= mx <= cx + 2 and my == cy)

    def draw(self, stdscr):
        """Draw the window."""
        if not self.visible:
            return

        max_h, max_w = stdscr.getmaxyx()
        border_attr = curses.color_pair(C_WIN_BORDER) if self.active else curses.color_pair(C_WIN_INACTIVE)
        title_attr = curses.color_pair(C_WIN_TITLE) if self.active else curses.color_pair(C_WIN_INACTIVE)
        body_attr = curses.color_pair(C_WIN_BODY)

        # Draw border
        draw_box(stdscr, self.y, self.x, self.h, self.w, border_attr)

        # Title bar
        title_text = f' {self.title} '
        if len(title_text) > self.w - 6:
            title_text = title_text[:self.w - 9] + '...'
        title_bar = title_text.ljust(self.w - 5)
        safe_addstr(stdscr, self.y, self.x + 1, title_bar, title_attr | curses.A_BOLD)

        # Close button
        close_attr = curses.color_pair(C_BUTTON) | curses.A_BOLD
        safe_addstr(stdscr, self.y, self.x + self.w - 4, '[×]', close_attr)

        # Body background
        bx, by, bw, bh = self.body_rect()
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

    def scroll_up(self):
        if self.scroll_offset > 0:
            self.scroll_offset -= 1

    def scroll_down(self):
        _, _, _, bh = self.body_rect()
        if self.scroll_offset < len(self.content) - bh:
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
                ('File Manager',  'filemanager'),
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

    def handle_click(self, mx, my):
        """Handle a click within the window body. Returns action result or None."""
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
    info.append(f'Python: {os.sys.version.split()[0]}')
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

        # Enable mouse
        curses.mousemask(
            curses.ALL_MOUSE_EVENTS |
            curses.REPORT_MOUSE_POSITION
        )
        # Enable SGR extended mouse mode for better coordinate support
        print('\033[?1003h', end='', flush=True)  # Any-event tracking
        print('\033[?1006h', end='', flush=True)  # SGR extended mode

        init_colors()

        # Create a welcome window
        h, w = stdscr.getmaxyx()
        welcome_content = [
            '',
            '   ╔══════════════════════════════════════╗',
            '   ║     Welcome to RetroTUI v0.2         ║',
            '   ║                                      ║',
            '   ║  A Windows 3.1 style desktop         ║',
            '   ║  environment for the Linux console.  ║',
            '   ║                                      ║',
            '   ║  Features:                           ║',
            '   ║  • Mouse support (GPM/xterm)         ║',
            '   ║  • Draggable windows                 ║',
            '   ║  • Dropdown menus                    ║',
            '   ║  • Desktop icons                     ║',
            '   ║  • Keyboard navigation               ║',
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
        print('\033[?1003l', end='', flush=True)
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
        """Draw desktop icons."""
        h, w = self.stdscr.getmaxyx()
        start_x = 3
        start_y = 3
        spacing_y = 3

        for i, icon in enumerate(self.icons):
            y = start_y + i * spacing_y
            if y >= h - 3:
                break
            attr = curses.color_pair(C_ICON_SEL if i == self.selected_icon else C_ICON)
            safe_addstr(self.stdscr, y, start_x, f' {icon["symbol"]} ', attr | curses.A_BOLD)
            safe_addstr(self.stdscr, y + 1, start_x - 1, center_text(icon['label'], 10), attr)

    def draw_statusbar(self):
        """Draw the bottom status bar."""
        h, w = self.stdscr.getmaxyx()
        attr = curses.color_pair(C_STATUS)
        status = f' RetroTUI v0.2 │ Windows: {len(self.windows)} │ Mouse: Enabled │ Ctrl+Q: Exit '
        safe_addstr(self.stdscr, h - 1, 0, status.ljust(w - 1), attr)

    def get_icon_at(self, mx, my):
        """Return icon index at mouse position, or -1."""
        start_x = 2
        start_y = 3
        spacing_y = 3

        for i in range(len(self.icons)):
            iy = start_y + i * spacing_y
            if iy <= my <= iy + 1 and start_x <= mx <= start_x + 8:
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
            msg = ('RetroTUI v0.2\n'
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
                   'Mouse Controls:\n\n'
                   'Click     - Select/activate\n'
                   'Drag      - Move windows\n'
                   'Scroll    - Scroll content')
            self.dialog = Dialog('Keyboard & Mouse Help', msg, ['OK'], width=46)

        elif action == 'filemanager':
            offset_x = 15 + len(self.windows) * 2
            offset_y = 3 + len(self.windows) * 1
            win = FileManagerWindow(offset_x, offset_y, 58, 22)
            self.windows.append(win)
            self.set_active_window(win)

        elif action == 'notepad':
            content = [
                ' ┌─ Untitled - Notepad ──────────────────────┐',
                ' │                                           │',
                ' │  Welcome to RetroTUI Notepad              │',
                ' │                                           │',
                ' │  This is a placeholder for a full         │',
                ' │  text editor implementation.              │',
                ' │                                           │',
                ' │  Future features:                         │',
                ' │  - Text editing with cursor               │',
                ' │  - File open/save                         │',
                ' │  - Search and replace                     │',
                ' │  - Syntax highlighting                    │',
                ' │                                           │',
                ' └───────────────────────────────────────────┘',
            ]
            offset_x = 20 + len(self.windows) * 2
            offset_y = 4 + len(self.windows) * 1
            win = Window('Notepad', offset_x, offset_y, 50, 18, content=content)
            self.windows.append(win)
            self.set_active_window(win)

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

    def open_file_viewer(self, filepath):
        """Open a text file in a read-only Notepad window."""
        h, w = self.stdscr.getmaxyx()
        filename = os.path.basename(filepath)

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

        try:
            with open(filepath, 'r', errors='replace') as f:
                raw_lines = f.readlines()
        except PermissionError:
            self.dialog = Dialog('Error', f'Permission denied:\n{filepath}', ['OK'], width=50)
            return
        except IsADirectoryError:
            return
        except OSError as e:
            self.dialog = Dialog('Error', f'Cannot open file:\n{e}', ['OK'], width=50)
            return

        # Prepare content
        content = []
        max_line_w = 200
        for line in raw_lines[:5000]:
            line = line.rstrip('\n\r').expandtabs(4)
            if len(line) > max_line_w:
                line = line[:max_line_w] + '...'
            content.append(' ' + line)

        if not content:
            content = [' (empty file)']

        # Create window
        offset_x = 18 + len(self.windows) * 2
        offset_y = 3 + len(self.windows)
        win_w = min(max(45, max(len(l) for l in content[:100]) + 4), w - 4)
        win_h = min(len(content) + 2, h - 4, 25)
        win = Window(f'Notepad - {filename}', offset_x, offset_y, win_w, win_h, content=content)
        self.windows.append(win)
        self.set_active_window(win)

    def handle_mouse(self, event):
        """Handle mouse events."""
        try:
            _, mx, my, _, bstate = event
        except Exception:
            return

        # Dialog takes priority
        if self.dialog:
            if bstate & curses.BUTTON1_CLICKED or bstate & curses.BUTTON1_PRESSED:
                result = self.dialog.handle_click(mx, my)
                if result >= 0:
                    btn_text = self.dialog.buttons[result]
                    if self.dialog.title == 'Exit RetroTUI' and btn_text == 'Yes':
                        self.running = False
                    self.dialog = None
            return

        # Menu bar
        if my == 0:
            action = self.menu.handle_click(mx, my)
            if action:
                self.execute_action(action)
            return

        # Menu dropdown
        if self.menu.active:
            action = self.menu.handle_click(mx, my)
            if action:
                self.execute_action(action)
            return

        # Check windows (reverse z-order for top window first)
        for win in reversed(self.windows):
            if not win.visible:
                continue

            if win.on_close_button(mx, my) and (bstate & curses.BUTTON1_CLICKED or bstate & curses.BUTTON1_PRESSED):
                self.close_window(win)
                return

            if win.on_title_bar(mx, my):
                if bstate & curses.BUTTON1_PRESSED:
                    win.dragging = True
                    win.drag_offset_x = mx - win.x
                    win.drag_offset_y = my - win.y
                    self.set_active_window(win)
                    return
                elif bstate & curses.BUTTON1_CLICKED:
                    self.set_active_window(win)
                    return

            if win.contains(mx, my):
                if bstate & curses.BUTTON1_CLICKED or bstate & curses.BUTTON1_PRESSED:
                    self.set_active_window(win)
                    # Delegate click to window if it has a handler
                    if hasattr(win, 'handle_click'):
                        result = win.handle_click(mx, my)
                        if result and result[0] == 'file':
                            self.open_file_viewer(result[1])
                    return
                # Scroll wheel
                if bstate & curses.BUTTON4_PRESSED:  # Scroll up
                    win.scroll_up()
                    return
                if bstate & 0x200000:  # Scroll down (BUTTON5)
                    win.scroll_down()
                    return

        # Window dragging
        if bstate & curses.REPORT_MOUSE_POSITION:
            for win in self.windows:
                if win.dragging:
                    h, w = self.stdscr.getmaxyx()
                    new_x = mx - win.drag_offset_x
                    new_y = my - win.drag_offset_y
                    win.x = max(0, min(new_x, w - win.w))
                    win.y = max(1, min(new_y, h - win.h - 1))
                    return

        if bstate & curses.BUTTON1_RELEASED:
            for win in self.windows:
                win.dragging = False

        # Desktop icons
        if bstate & curses.BUTTON1_CLICKED or bstate & curses.BUTTON1_PRESSED:
            icon_idx = self.get_icon_at(mx, my)
            if icon_idx >= 0:
                self.selected_icon = icon_idx
                return

        # Double click on icon
        if bstate & curses.BUTTON1_DOUBLE_CLICKED:
            icon_idx = self.get_icon_at(mx, my)
            if icon_idx >= 0:
                self.execute_action(self.icons[icon_idx]['action'])
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

        if key == curses.KEY_F10 or key == 27:  # F10 or Escape
            if self.menu.active:
                self.menu.active = False
            elif key == curses.KEY_F10:
                self.menu.active = True
                self.menu.selected_menu = 0
                self.menu.selected_item = 0
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

        # Window focus cycling
        if key == 9:  # Tab
            if self.windows:
                current = next((i for i, w in enumerate(self.windows) if w.active), -1)
                next_idx = (current + 1) % len(self.windows)
                for w in self.windows:
                    w.active = False
                self.windows[next_idx].active = True
            return

        # Delegate to active window
        active_win = next((w for w in self.windows if w.active), None)
        if active_win:
            if hasattr(active_win, 'handle_key'):
                result = active_win.handle_key(key)
                if result and result[0] == 'file':
                    self.open_file_viewer(result[1])
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

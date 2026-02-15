"""
Menu System (Global Menu and Window Menu).
"""
import curses
import time
from ..constants import (
    C_MENUBAR, C_MENU_SEL, C_MENU_ITEM, SB_H
)
from ..utils import safe_addstr, draw_box

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

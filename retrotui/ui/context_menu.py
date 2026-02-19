
"""Context Menu UI component."""

import curses
from ..core.actions import AppAction
from ..utils import theme_attr
from .menu import Menu


class ContextMenu(Menu):
    """
    A context menu that appears at a specific (x, y) location.
    inherits from Menu to reuse drawing and navigation logic.
    """

    def __init__(self, theme):
        super().__init__()
        self.theme = theme
        self.x = 0
        self.y = 0
        self.items = []  # List of dicts: {'label': str, 'action': AppAction, 'separator': bool}
        self.selected_index = 0
        self.active = False
        self._width = 20

    def show(self, x, y, items):
        """Open the context menu at x, y with the given items."""
        self.x = x
        self.y = y
        self.items = items
        self.selected_index = 0
        self.active = True
        
        # Calculate width based on longest item
        max_len = 0
        for item in self.items:
            if item.get('separator'):
                continue
            label = item.get('label', '')
            if len(label) > max_len:
                max_len = len(label)
        self._width = max_len + 4  # padding

        # Ensure menu doesn't go off-screen (requires layout info, will handle in draw/app)
        
    def hide(self):
        """Close the context menu."""
        self.active = False
        self.items = []

    def is_open(self):
        return self.active

    def handle_input(self, key):
        """Handle keyboard input for the context menu."""
        if not self.active:
            return None

        if key == curses.KEY_UP:
            self.selected_index = (self.selected_index - 1) % len(self.items)
            # Skip separators
            while self.items[self.selected_index].get('separator'):
                self.selected_index = (self.selected_index - 1) % len(self.items)
            return None

        if key == curses.KEY_DOWN:
            self.selected_index = (self.selected_index + 1) % len(self.items)
            # Skip separators
            while self.items[self.selected_index].get('separator'):
                self.selected_index = (self.selected_index + 1) % len(self.items)
            return None

        if key in (curses.KEY_ENTER, 10, 13):
            item = self.items[self.selected_index]
            self.hide()
            return item.get('action')

        if key == 27:  # ESC
            self.hide()
            return None

        return None

    def handle_click(self, mx, my):
        """Handle mouse click on the context menu."""
        if not self.active:
            return None

        # Check if click is inside menu bounds
        if self.x <= mx < self.x + self._width and self.y <= my < self.y + len(self.items) + 2:
            # Calculate clicked item index (account for border)
            idx = my - self.y - 1
            if 0 <= idx < len(self.items):
                item = self.items[idx]
                if not item.get('separator'):
                    self.hide()
                    return item.get('action')
        else:
            # Click outside closes menu
            self.hide()
        
        return None

    def draw(self, stdscr):
        """Render the context menu."""
        if not self.active:
            return

        # Ensure we don't draw off-screen
        h, w = stdscr.getmaxyx()
        draw_x = min(self.x, w - self._width)
        draw_y = min(self.y, h - len(self.items) - 2)

        # Draw border and background
        try:
            # Shadow
            # stdscr.attron(self.theme.shadow_attr)
            # for i in range(len(self.items) + 2):
            #    stdscr.addstr(draw_y + 1 + i, draw_x + 2, " " * self._width)
            # stdscr.attroff(self.theme.shadow_attr)

            stdscr.attron(theme_attr('menu_item'))
            
            # Top border
            stdscr.addstr(draw_y, draw_x, "┌" + "─" * (self._width - 2) + "┐")
            
            for i, item in enumerate(self.items):
                row_y = draw_y + 1 + i
                if item.get('separator'):
                    stdscr.addstr(row_y, draw_x, "├" + "─" * (self._width - 2) + "┤")
                else:
                    label = f" {item['label']}".ljust(self._width - 2)
                    if i == self.selected_index:
                        stdscr.attron(theme_attr('menu_selected'))
                        stdscr.addstr(row_y, draw_x + 1, label)
                        stdscr.attroff(theme_attr('menu_selected'))
                        # Draw borders with normal attr
                        stdscr.attron(theme_attr('menu_item'))
                        stdscr.addch(row_y, draw_x, "│")
                        stdscr.addch(row_y, draw_x + self._width - 1, "│")
                    else:
                        stdscr.addstr(row_y, draw_x, "│" + label + "│")

            # Bottom border
            stdscr.addstr(draw_y + len(self.items) + 1, draw_x, "└" + "─" * (self._width - 2) + "┘")

            stdscr.attroff(theme_attr('menu_item'))
        except curses.error:
            pass

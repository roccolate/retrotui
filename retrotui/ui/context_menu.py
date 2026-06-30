
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

    def _selectable_indices(self):
        return [idx for idx, item in enumerate(self.items) if not item.get('separator')]

    def _move_selection(self, step):
        selectable = self._selectable_indices()
        if not selectable:
            return
        if self.selected_index not in selectable:
            self.selected_index = selectable[0]
            return
        pos = selectable.index(self.selected_index)
        self.selected_index = selectable[(pos + step) % len(selectable)]

    def show(self, x, y, items):
        """Open the context menu at x, y with the given items."""
        self.x = x
        self.y = y
        self.items = list(items or [])
        selectable = self._selectable_indices()
        self.selected_index = selectable[0] if selectable else 0
        self.active = True
        
        # Calculate width based on longest item
        max_len = 0
        for item in self.items:
            if item.get('separator'):
                continue
            label = item.get('label', '')
            if len(label) > max_len:
                max_len = len(label)
        self._width = max(4, max_len + 4)  # padding

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
            self._move_selection(-1)
            return None

        if key == curses.KEY_DOWN:
            self._move_selection(1)
            return None

        if key in (curses.KEY_ENTER, 10, 13):
            if not self.items or not (0 <= self.selected_index < len(self.items)):
                return None
            item = self.items[self.selected_index]
            if item.get('separator'):
                return None
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

        # Use the clamped render coordinates cached by ``draw`` when
        # available, so the hit test matches the visible rectangle
        # (the original ``self.x``/``self.y`` may be off-screen if the
        # menu was opened near an edge).
        x0 = getattr(self, "_draw_x", self.x)
        y0 = getattr(self, "_draw_y", self.y)

        # Check if click is inside menu bounds
        if x0 <= mx < x0 + self._width and y0 <= my < y0 + len(self.items) + 2:
            # Calculate clicked item index (account for border)
            idx = my - y0 - 1
            if 0 <= idx < len(self.items):
                item = self.items[idx]
                if not item.get('separator'):
                    self.hide()
                    return item.get('action')
        else:
            # Click outside closes menu
            self.hide()

        return None

    def draw(self, stdscr, frame_size=None):
        """Render the context menu."""
        if not self.active:
            return

        # Ensure we don't draw off-screen. Cache the clamped coordinates
        # so ``handle_click`` can do hit testing against the actual
        # visible rectangle instead of the (possibly off-screen) ones
        # passed to ``show``.
        if frame_size is not None:
            h, w = frame_size
        else:
            h, w = stdscr.getmaxyx()
        draw_x = max(0, min(self.x, w - self._width))
        draw_y = max(0, min(self.y, h - len(self.items) - 2))
        self._draw_x = draw_x
        self._draw_y = draw_y

        # Draw border and background
        try:
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
        except curses.error:
            pass
        finally:
            # Always release the attribute stack, even if a draw call
            # raised mid-block. Otherwise subsequent draws inherit the
            # wrong attributes (visible as color bleed).
            try:
                stdscr.attroff(theme_attr('menu_item'))
            except (curses.error, KeyError):
                pass

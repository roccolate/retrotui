"""
Dialog Component.
"""
import curses
from ..constants import (
    C_DIALOG, C_WIN_TITLE, C_BUTTON, C_BUTTON_SEL
)
from ..utils import safe_addstr, draw_box

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

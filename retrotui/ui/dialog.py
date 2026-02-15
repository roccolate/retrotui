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

class InputDialog(Dialog):
    """Modal dialog with a text input field."""

    def __init__(self, title, message, initial_value='', width=50):
        super().__init__(title, message, ['OK', 'Cancel'], width)
        self.value = initial_value
        # Add space for input box
        self.height += 3
        
        # Cursor pos
        self.cursor_pos = len(initial_value)

    def draw(self, stdscr):
        super().draw(stdscr)
        
        # Input box area
        max_h, max_w = stdscr.getmaxyx()
        x = (max_w - self.width) // 2
        y = (max_h - self.height) // 2
        
        # Input box is below message, above buttons
        # Dialog.draw puts buttons at y + height - 3
        # We need to shift buttons down effectively implies we need to draw input box
        # at y + height - 5 (since we added 3 to height)
        
        input_y = y + self.height - 5
        input_x = x + 4
        input_w = self.width - 8
        
        # Draw input box background
        attr = curses.color_pair(C_WIN_BODY)
        safe_addstr(stdscr, input_y, input_x, ' ' * input_w, attr)
        
        # Draw value
        display_val = self.value[-(input_w - 1):] if len(self.value) >= input_w else self.value
        safe_addstr(stdscr, input_y, input_x, display_val, attr)
        
        # Cursor
        cursor_screen_x = input_x + len(display_val)
        if len(self.value) < input_w:
             cursor_screen_x = input_x + self.cursor_pos
        else:
             cursor_screen_x = input_x + input_w - 1 # End of box
             
        safe_addstr(stdscr, input_y, cursor_screen_x, ' ', attr | curses.A_REVERSE)

    def handle_click(self, mx, my):
        # Delegate to super for buttons
        return super().handle_click(mx, my)

    def handle_key(self, key):
        # Check buttons navigation first? 
        # Actually standard input handling usually consumes arrows for cursor
        # So we might override navigation
        
        if key in (curses.KEY_ENTER, 10, 13):
            # If standard enter, return OK (0)
            return 0
        elif key == 27: # Esc
            return 1 # Cancel
        
        elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:
            if self.cursor_pos > 0:
                self.value = self.value[:self.cursor_pos-1] + self.value[self.cursor_pos:]
                self.cursor_pos -= 1
        elif key == curses.KEY_DC:
            if self.cursor_pos < len(self.value):
                self.value = self.value[:self.cursor_pos] + self.value[self.cursor_pos+1:]
        elif key == curses.KEY_LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
        elif key == curses.KEY_RIGHT:
            if self.cursor_pos < len(self.value):
                self.cursor_pos += 1
        elif 32 <= key <= 126:
            self.value = self.value[:self.cursor_pos] + chr(key) + self.value[self.cursor_pos:]
            self.cursor_pos += 1
            
        return -1

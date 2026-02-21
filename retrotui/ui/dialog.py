"""
Dialog Component.
"""
import curses
from ..utils import safe_addstr, draw_box, normalize_key_code, theme_attr


def _wrap_dialog_message(message, inner_w):
    """Word-wrap a dialog message into a list of lines."""
    lines = []
    for paragraph in str(message).split('\n'):
        words = paragraph.split()
        if not words:
            lines.append('')
            continue
        line = ''
        for word in words:
            needs_space = 1 if line else 0
            if len(line) + len(word) + needs_space <= inner_w:
                line = f'{line} {word}' if line else word
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines or ['']


class Dialog:
    """Modal dialog box."""

    def __init__(self, title, message, buttons=None, width=50):
        self.title = title
        self.message = message
        self.buttons = buttons or ['OK']
        self.selected = 0
        self.width = max(width, len(title) + 8)

        # Word wrap message
        inner_w = self.width - 6
        self.lines = _wrap_dialog_message(message, inner_w)

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

        attr = theme_attr('dialog')
        title_attr = theme_attr('window_title') | curses.A_BOLD

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
                btn_attr = theme_attr('button_selected') | curses.A_BOLD
                label = f'▸ {btn_text} ◂'
            else:
                btn_attr = theme_attr('button')
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
        key_code = normalize_key_code(key)

        if key_code == curses.KEY_LEFT:
            self.selected = (self.selected - 1) % len(self.buttons)
        elif key_code == curses.KEY_RIGHT:
            self.selected = (self.selected + 1) % len(self.buttons)
        elif key_code in (curses.KEY_ENTER, 10, 13):
            return self.selected
        elif key_code == 27:  # Escape
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
        attr = theme_attr('window_body')
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
        key_code = normalize_key_code(key)

        if key_code in (curses.KEY_ENTER, 10, 13):
            # If standard enter, return OK (0)
            return 0
        elif key_code == 27: # Esc
            return 1 # Cancel

        elif key_code in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor_pos > 0:
                self.value = self.value[:self.cursor_pos-1] + self.value[self.cursor_pos:]
                self.cursor_pos -= 1
        elif key_code == curses.KEY_DC:
            if self.cursor_pos < len(self.value):
                self.value = self.value[:self.cursor_pos] + self.value[self.cursor_pos+1:]
        elif key_code == curses.KEY_LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
        elif key_code == curses.KEY_RIGHT:
            if self.cursor_pos < len(self.value):
                self.cursor_pos += 1
        elif isinstance(key, str) and key.isprintable() and key not in ('\n', '\r', '\t'):
            self.value = self.value[:self.cursor_pos] + key + self.value[self.cursor_pos:]
            self.cursor_pos += 1
        elif isinstance(key, int) and 32 <= key <= 126:
            self.value = self.value[:self.cursor_pos] + chr(key) + self.value[self.cursor_pos:]
            self.cursor_pos += 1

        return -1


class MultiSelectDialog(Dialog):
    """Modal dialog with a scrollable list of checkboxes."""

    def __init__(self, title, message, choices, width=54):
        # choices: list of tuples (label, value, is_checked)
        super().__init__(title, message, ['OK', 'Cancel'], width)
        self.choices = [[label, value, bool(checked)] for label, value, checked in choices]
        self.list_offset = 0
        self.list_selected = 0
        self.in_list = True  # Focus starts in list, not on buttons
        self.visible_rows = 6
        self.height += self.visible_rows + 2

    def draw(self, stdscr):
        super().draw(stdscr)
        
        max_h, max_w = stdscr.getmaxyx()
        x = (max_w - self.width) // 2
        y = (max_h - self.height) // 2
        
        list_y = y + len(self.lines) + 4
        list_x = x + 3
        list_w = self.width - 6
        
        attr = theme_attr('window_body')
        sel_attr = attr | curses.A_REVERSE
        
        # Draw list background and border
        draw_box(stdscr, list_y - 1, list_x - 1, self.visible_rows + 2, list_w + 2, attr, double=False)
        
        for i in range(self.visible_rows):
            idx = self.list_offset + i
            if idx < len(self.choices):
                label, _, checked = self.choices[idx]
                mark = '[x]' if checked else '[ ]'
                text = f" {mark} {label}"
                
                row_attr = sel_attr if (self.in_list and idx == self.list_selected) else attr
                safe_addstr(stdscr, list_y + i, list_x, text.ljust(list_w)[:list_w], row_attr)
            else:
                safe_addstr(stdscr, list_y + i, list_x, ' ' * list_w, attr)
                
        # Draw scrollbar if needed
        if len(self.choices) > self.visible_rows:
            sb_x = list_x + list_w
            thumb_pos = int(self.list_offset / max(1, len(self.choices) - self.visible_rows) * (self.visible_rows - 1))
            for i in range(self.visible_rows):
                ch = '█' if i == thumb_pos else '░'
                safe_addstr(stdscr, list_y + i, sb_x, ch, theme_attr('scrollbar'))

    def handle_click(self, mx, my):
        # Delegate down to buttons
        if not self.in_list:
            btn_hit = super().handle_click(mx, my)
            if btn_hit != -1:
                return btn_hit
                
        # Check list clicks
        max_h, max_w = curses.initscr().getmaxyx()
        x = (max_w - self.width) // 2
        y = (max_h - self.height) // 2
        list_y = y + len(self.lines) + 4
        list_x = x + 3
        list_w = self.width - 6
        
        if list_x <= mx <= list_x + list_w and list_y <= my < list_y + self.visible_rows:
            click_idx = self.list_offset + (my - list_y)
            if click_idx < len(self.choices):
                self.in_list = True
                self.list_selected = click_idx
                # Toggle
                self.choices[click_idx][2] = not self.choices[click_idx][2]
                
        # Detect clicks on buttons even if focus is in list
        if my == self._btn_y:
            btn_x = self._btn_x_start
            for i, btn_text in enumerate(self.buttons):
                btn_w = len(btn_text) + 4
                if btn_x <= mx < btn_x + btn_w:
                    self.in_list = False
                    self.selected = i
                    return i
                btn_x += btn_w + 2
                
        return -1

    def handle_key(self, key):
        key_code = normalize_key_code(key)

        if key_code == 27: # Esc
            return 1 # Cancel
            
        if key_code in (curses.KEY_UP, curses.KEY_DOWN):
            if not self.in_list:
                self.in_list = True
                return -1
                
            if key_code == curses.KEY_UP:
                self.list_selected = max(0, self.list_selected - 1)
                if self.list_selected < self.list_offset:
                    self.list_offset = self.list_selected
            elif key_code == curses.KEY_DOWN:
                self.list_selected = min(len(self.choices) - 1, self.list_selected + 1)
                if self.list_selected >= self.list_offset + self.visible_rows:
                    self.list_offset = self.list_selected - self.visible_rows + 1
            return -1
            
        if key_code in (9,): # Tab
            self.in_list = not self.in_list
            return -1
            
        if self.in_list:
            if key_code in (32, 10, 13, curses.KEY_ENTER): # Space or Enter
                if self.choices:
                    self.choices[self.list_selected][2] = not self.choices[self.list_selected][2]
                return -1
        else:
            return super().handle_key(key)
            
        return -1

        return [val for _, val, checked in self.choices if checked]


class ProgressDialog:
    """Modal progress dialog for background operations."""

    SPINNER_FRAMES = ('|', '/', '-', '\\')

    def __init__(self, title, message, width=58):
        self.title = title
        self.message = message
        self.buttons = []
        self.width = max(width, len(title) + 8)
        self.lines = _wrap_dialog_message(message, self.width - 6)
        self.elapsed_seconds = 0.0
        self.height = len(self.lines) + 8

    def set_elapsed(self, seconds):
        """Update elapsed runtime shown by the spinner row."""
        self.elapsed_seconds = max(0.0, float(seconds))

    def draw(self, stdscr):
        max_h, max_w = stdscr.getmaxyx()
        x = (max_w - self.width) // 2
        y = (max_h - self.height) // 2

        attr = theme_attr('dialog')
        title_attr = theme_attr('window_title') | curses.A_BOLD
        info_attr = theme_attr('status') | curses.A_BOLD

        shadow_attr = curses.A_DIM
        for row in range(self.height):
            safe_addstr(stdscr, y + row + 1, x + 2, ' ' * self.width, shadow_attr)

        for row in range(self.height):
            safe_addstr(stdscr, y + row, x, ' ' * self.width, attr)

        draw_box(stdscr, y, x, self.height, self.width, attr, double=True)

        title_text = f' {self.title} '
        safe_addstr(stdscr, y, x + 1, title_text.ljust(self.width - 2), title_attr)

        for i, line in enumerate(self.lines):
            safe_addstr(stdscr, y + 2 + i, x + 3, line[: self.width - 6], attr)

        spinner_idx = int(self.elapsed_seconds * 8) % len(self.SPINNER_FRAMES)
        spinner = self.SPINNER_FRAMES[spinner_idx]
        status = f'Working {spinner}  {self.elapsed_seconds:5.1f}s'
        safe_addstr(stdscr, y + self.height - 3, x + 3, status.ljust(self.width - 6), info_attr)

    def handle_click(self, mx, my):
        """Progress dialogs do not process click actions."""
        _ = (mx, my)
        return -1

    def handle_key(self, key):
        """Progress dialogs do not process keyboard actions."""
        _ = key
        return -1

"""
Notepad Application.
"""
import curses
import os
from ..ui.window import Window
from ..ui.menu import WindowMenu
from ..core.actions import ActionResult, ActionType, AppAction
from ..utils import safe_addstr, draw_box
from ..constants import C_STATUS, C_SCROLLBAR

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
                ('New',           AppAction.NP_NEW),
                ('Save   Ctrl+S', AppAction.NP_SAVE),
                ('Save As...',    AppAction.NP_SAVE_AS),
                ('─────────────', None),
                ('Close',         AppAction.NP_CLOSE),
            ],
            'View': [
                ('Word Wrap  Ctrl+W', AppAction.NP_TOGGLE_WRAP),
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

    def _save_file(self):
        """Save buffer to file. Returns True or ActionResult."""
        if not self.filepath:
            return ActionResult(ActionType.REQUEST_SAVE_AS)
        try:
            with open(self.filepath, 'w') as f:
                f.write('\n'.join(self.buffer))
            self.modified = False
            return True
        except (PermissionError, OSError) as e:
            return ActionResult(ActionType.SAVE_ERROR, str(e))

    def save_as(self, filepath):
        """Set filepath and save."""
        self.filepath = filepath
        self.title = f'Notepad - {os.path.basename(filepath)}'
        return self._save_file()


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

        # Update title with modified indicator
        if self.filepath:
            filename = os.path.basename(self.filepath)
            prefix = '* ' if self.modified else ''
            self.title = f'Notepad - {prefix}{filename}'
        elif self.modified:
            self.title = 'Notepad *'
        else:
            self.title = 'Notepad'

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
        if action == AppAction.NP_TOGGLE_WRAP:
            self.wrap_mode = not self.wrap_mode
            self.view_left = 0
            self._invalidate_wrap()
            self._ensure_cursor_visible()
        elif action == AppAction.NP_SAVE:
            result = self._save_file()
            if result is not True:
                return result
        elif action == AppAction.NP_SAVE_AS:
            return ActionResult(ActionType.REQUEST_SAVE_AS)
        elif action == AppAction.NP_NEW:
            return ActionResult(ActionType.EXECUTE, AppAction.NOTEPAD)
        elif action == AppAction.NP_CLOSE:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
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

        # Save: Ctrl+S (key 19)
        elif key == 19:
            result = self._save_file()
            if result is not True:
                return result

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

"""
Notepad Application.
"""
import curses
import os
from ..ui.window import Window
from ..ui.menu import WindowMenu
from ..core.actions import ActionResult, ActionType, AppAction
from ..core.clipboard import copy_text, paste_text
from ..utils import safe_addstr, normalize_key_code, theme_attr
from ..constants import C_STATUS, C_SCROLLBAR

class NotepadWindow(Window):
    """Editable text editor window with word wrap support."""

    KEY_F6 = getattr(curses, 'KEY_F6', -1)
    KEY_INSERT = getattr(curses, 'KEY_IC', -1)

    def __init__(self, x, y, w, h, filepath=None, wrap_default=False):
        title = 'Notepad'
        super().__init__(title, x, y, w, h, content=[])
        self.buffer = ['']  # list[str] — one string per logical line
        self.filepath = filepath
        self.modified = False
        self.cursor_line = 0
        self.cursor_col = 0
        self.view_top = 0    # First visible line in buffer
        self.view_left = 0   # Horizontal scroll offset
        self.wrap_mode = bool(wrap_default)
        self._wrap_cache = []       # list[(buf_line, start_col, text)]
        self._wrap_cache_w = -1     # Width used to build cache
        self._wrap_stale = True
        self.selection_anchor = None  # (line, col)
        self.selection_cursor = None  # (line, col)
        self._mouse_selecting = False
        self.window_menu = WindowMenu({
            'File': [
                ('New',           AppAction.NP_NEW),
                ('Open... Ctrl+O', AppAction.NP_OPEN),
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
            with open(filepath, 'r', encoding='utf-8', errors='replace', newline='') as f:
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
            with open(self.filepath, 'w', encoding='utf-8', newline='\n') as f:
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

    def open_path(self, filepath):
        """Load a file path into current notepad buffer."""
        path = (filepath or '').strip()
        if not path:
            return None
        self._load_file(os.path.abspath(os.path.expanduser(path)))
        self.clear_selection()
        return None


    def _invalidate_wrap(self):
        """Mark wrap cache as needing rebuild."""
        self._wrap_stale = True

    def clear_selection(self):
        """Clear current text selection."""
        self.selection_anchor = None
        self.selection_cursor = None
        self._mouse_selecting = False

    def has_selection(self):
        """Return True when there is a non-empty text selection."""
        return (
            self.selection_anchor is not None
            and self.selection_cursor is not None
            and self.selection_anchor != self.selection_cursor
        )

    def _selection_bounds(self):
        """Return ordered ((line,col), (line,col)) selection bounds, or None."""
        if not self.has_selection():
            return None
        a = self.selection_anchor
        b = self.selection_cursor
        return (a, b) if a <= b else (b, a)

    def _line_selection_span(self, line_idx, line_len):
        """Return [start,end) selected columns for a buffer line, or None."""
        bounds = self._selection_bounds()
        if bounds is None:
            return None
        (s_line, s_col), (e_line, e_col) = bounds
        if line_idx < s_line or line_idx > e_line:
            return None
        if s_line == e_line:
            start = max(0, min(line_len, s_col))
            end = max(0, min(line_len, e_col))
            if start >= end:
                return None
            return (start, end)
        if line_idx == s_line:
            start = max(0, min(line_len, s_col))
            end = line_len
            if start >= end:
                return None
            return (start, end)
        if line_idx == e_line:
            start = 0
            end = max(0, min(line_len, e_col))
            if start >= end:
                return None
            return (start, end)
        return (0, line_len)

    def _selected_text(self):
        """Return selected text as plain string."""
        bounds = self._selection_bounds()
        if bounds is None:
            return ''
        (s_line, s_col), (e_line, e_col) = bounds
        if s_line == e_line:
            return self.buffer[s_line][s_col:e_col]

        parts = [self.buffer[s_line][s_col:]]
        for line_idx in range(s_line + 1, e_line):
            parts.append(self.buffer[line_idx])
        parts.append(self.buffer[e_line][:e_col])
        return '\n'.join(parts)

    def _delete_selection(self):
        """Delete current selection and place cursor at selection start."""
        bounds = self._selection_bounds()
        if bounds is None:
            return False

        (s_line, s_col), (e_line, e_col) = bounds
        s_col = max(0, min(s_col, len(self.buffer[s_line])))
        e_col = max(0, min(e_col, len(self.buffer[e_line])))

        if s_line == e_line:
            line = self.buffer[s_line]
            self.buffer[s_line] = line[:s_col] + line[e_col:]
        else:
            first = self.buffer[s_line][:s_col]
            last = self.buffer[e_line][e_col:]
            self.buffer[s_line] = first + last
            del self.buffer[s_line + 1:e_line + 1]

        self.cursor_line = s_line
        self.cursor_col = s_col
        self._clamp_cursor()

        self.modified = True
        self._invalidate_wrap()
        self.clear_selection()
        self._ensure_cursor_visible()
        return True

    def _cut_current_line(self):
        """Cut current line to clipboard."""
        if not (0 <= self.cursor_line < len(self.buffer)):
            return

        copy_text(self.buffer[self.cursor_line])
        if len(self.buffer) == 1:
            self.buffer[0] = ''
            self.cursor_line = 0
            self.cursor_col = 0
        else:
            self.buffer.pop(self.cursor_line)
            if self.cursor_line >= len(self.buffer):
                self.cursor_line = len(self.buffer) - 1
            self.cursor_col = min(self.cursor_col, len(self.buffer[self.cursor_line]))

        self.modified = True
        self._invalidate_wrap()
        self.clear_selection()
        self._ensure_cursor_visible()

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

    def _insert_text(self, text):
        """Insert plain text at cursor position, supporting multiline paste."""
        if not text:
            return

        normalized = text.replace('\r\n', '\n').replace('\r', '\n')
        current = self.buffer[self.cursor_line]
        before = current[:self.cursor_col]
        after = current[self.cursor_col:]
        parts = normalized.split('\n')

        if len(parts) == 1:
            self.buffer[self.cursor_line] = before + parts[0] + after
            self.cursor_col += len(parts[0])
        else:
            self.buffer[self.cursor_line] = before + parts[0]
            insert_at = self.cursor_line + 1
            for middle in parts[1:-1]:
                self.buffer.insert(insert_at, middle)
                insert_at += 1
            self.buffer.insert(insert_at, parts[-1] + after)
            self.cursor_line = insert_at
            self.cursor_col = len(parts[-1])

        self.modified = True
        self._invalidate_wrap()
        self._ensure_cursor_visible()

    def _set_cursor_from_screen(self, mx, my):
        """Place cursor using screen coordinates inside body area."""
        bx, by, bw, _ = self.body_rect()
        row_in_view = my - by
        col_in_view = mx - bx

        if self.wrap_mode:
            self._compute_wrap(bw)
            wrap_idx = self.view_top + row_in_view
            if wrap_idx < len(self._wrap_cache):
                buf_line, start_col, _ = self._wrap_cache[wrap_idx]
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
                span = self._line_selection_span(buf_line, len(self.buffer[buf_line]))
                if span is not None:
                    span_start = max(span[0], start_col)
                    span_end = min(span[1], start_col + len(text))
                    span = (span_start, span_end)
                self._draw_selection_span(
                    stdscr, by + i, bx, bw,
                    self.buffer[buf_line], start_col, span,
                    body_attr | curses.A_REVERSE,
                )
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
                span = self._line_selection_span(buf_idx, len(line))
                if span is not None:
                    span_start = max(span[0], self.view_left)
                    span_end = min(span[1], self.view_left + col_w)
                    span = (span_start, span_end)
                self._draw_selection_span(
                    stdscr, by + i, bx, bw,
                    line, self.view_left, span,
                    body_attr | curses.A_REVERSE,
                )
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
                safe_addstr(stdscr, by + i, sb_x, ch, theme_attr('scrollbar'))

        # Status bar (inside window, last body row)
        status_y = by + bh - 1
        mod_flag = ' [Modified]' if self.modified else ''
        wrap_flag = ' WRAP' if self.wrap_mode else ''
        status = f' Ln {self.cursor_line + 1}, Col {self.cursor_col + 1}{wrap_flag}{mod_flag}'
        safe_addstr(stdscr, status_y, bx, status.ljust(bw)[:bw], theme_attr('status'))

        # Window menu dropdown (on top of body content)
        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def _draw_selection_span(self, stdscr, screen_y, body_x, body_w, line_text, start_col, span, sel_attr):
        """Draw selection highlight characters for a span on one screen line."""
        if span is None:
            return
        sel_start, sel_end = span
        for abs_col in range(sel_start, sel_end):
            local_col = abs_col - start_col
            if 0 <= local_col < body_w - 1:
                ch = line_text[abs_col] if abs_col < len(line_text) else ' '
                safe_addstr(stdscr, screen_y, body_x + local_col, ch, sel_attr)

    def execute_action(self, action):
        """Execute a window menu action. Returns signal or None."""
        if action == AppAction.NP_TOGGLE_WRAP:
            self.wrap_mode = not self.wrap_mode
            self.view_left = 0
            self._invalidate_wrap()
            self._ensure_cursor_visible()
            return ActionResult(ActionType.UPDATE_CONFIG, {'word_wrap_default': self.wrap_mode})
        elif action == AppAction.NP_OPEN:
            return ActionResult(ActionType.REQUEST_OPEN_PATH)
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
        key_code = normalize_key_code(key)

        # Window menu keyboard handling
        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self.execute_action(action)
            return None

        # Clear selection: Esc
        if key_code == 27:
            self.clear_selection()
            return None

        # Select all: Ctrl+A
        if key_code == 1:
            if not self.buffer:
                self.buffer = ['']
            last_line = len(self.buffer) - 1
            last_col = len(self.buffer[last_line])
            self.selection_anchor = (0, 0)
            self.selection_cursor = (last_line, last_col)
            self.cursor_line = last_line
            self.cursor_col = last_col
            self._ensure_cursor_visible()
            return None

        # Cut: Ctrl+X
        if key_code == 24:
            if self.has_selection():
                selected = self._selected_text()
                if selected:
                    copy_text(selected)
                self._delete_selection()
            else:
                self._cut_current_line()
            return None

        # Navigation
        if key_code == curses.KEY_UP:
            self.clear_selection()
            if self.cursor_line > 0:
                self.cursor_line -= 1
                self._clamp_cursor()
                self._ensure_cursor_visible()
        elif key_code == curses.KEY_DOWN:
            self.clear_selection()
            if self.cursor_line < len(self.buffer) - 1:
                self.cursor_line += 1
                self._clamp_cursor()
                self._ensure_cursor_visible()
        elif key_code == curses.KEY_LEFT:
            self.clear_selection()
            if self.cursor_col > 0:
                self.cursor_col -= 1
            elif self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = len(self.buffer[self.cursor_line])
            self._ensure_cursor_visible()
        elif key_code == curses.KEY_RIGHT:
            self.clear_selection()
            line = self.buffer[self.cursor_line]
            if self.cursor_col < len(line):
                self.cursor_col += 1
            elif self.cursor_line < len(self.buffer) - 1:
                self.cursor_line += 1
                self.cursor_col = 0
            self._ensure_cursor_visible()
        elif key_code == curses.KEY_HOME:
            self.clear_selection()
            self.cursor_col = 0
            self._ensure_cursor_visible()
        elif key_code == curses.KEY_END:
            self.clear_selection()
            self.cursor_col = len(self.buffer[self.cursor_line])
            self._ensure_cursor_visible()
        elif key_code == curses.KEY_PPAGE:
            self.clear_selection()
            _, _, _, bh = self.body_rect()
            self.cursor_line = max(0, self.cursor_line - (bh - 2))
            self._clamp_cursor()
            self._ensure_cursor_visible()
        elif key_code == curses.KEY_NPAGE:
            self.clear_selection()
            _, _, _, bh = self.body_rect()
            self.cursor_line = min(len(self.buffer) - 1, self.cursor_line + (bh - 2))
            self._clamp_cursor()
            self._ensure_cursor_visible()

        # Editing: Enter
        elif key_code in (curses.KEY_ENTER, 10, 13):
            if self.has_selection():
                self._delete_selection()
            else:
                self.clear_selection()
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
        elif key_code in (curses.KEY_BACKSPACE, 127, 8):
            if self.has_selection():
                self._delete_selection()
            elif self.cursor_col > 0:
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
        elif key_code == curses.KEY_DC:
            if self.has_selection():
                self._delete_selection()
            else:
                self.clear_selection()
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

        # Open: Ctrl+O (key 15)
        elif key_code == 15:
            return ActionResult(ActionType.REQUEST_OPEN_PATH)

        # Save: Ctrl+S (key 19)
        elif key_code == 19:
            result = self._save_file()
            if result is not True:
                return result

        # Copy line: F6 / Insert (Ctrl+Ins fallback where modifiers collapse)
        elif key_code in (self.KEY_F6, self.KEY_INSERT):
            text = self._selected_text()
            if text:
                copy_text(text)
            elif 0 <= self.cursor_line < len(self.buffer):
                copy_text(self.buffer[self.cursor_line])

        # Paste: Ctrl+V (key 22)
        elif key_code == 22:
            if self.has_selection():
                self._delete_selection()
            self._insert_text(paste_text())

        # Toggle: Ctrl+W (key 23)
        elif key_code == 23:
            self.clear_selection()
            self.wrap_mode = not self.wrap_mode
            self.view_left = 0
            self._invalidate_wrap()
            self._ensure_cursor_visible()

        # Printable characters
        elif isinstance(key, str) and key.isprintable() and key not in ('\n', '\r', '\t'):
            if self.has_selection():
                self._delete_selection()
            else:
                self.clear_selection()
            ch = key
            line = self.buffer[self.cursor_line]
            self.buffer[self.cursor_line] = line[:self.cursor_col] + ch + line[self.cursor_col:]
            self.cursor_col += 1
            self.modified = True
            self._invalidate_wrap()
            self._ensure_cursor_visible()
        elif isinstance(key, int) and 32 <= key <= 126:
            if self.has_selection():
                self._delete_selection()
            else:
                self.clear_selection()
            ch = chr(key)
            line = self.buffer[self.cursor_line]
            self.buffer[self.cursor_line] = line[:self.cursor_col] + ch + line[self.cursor_col:]
            self.cursor_col += 1
            self.modified = True
            self._invalidate_wrap()
            self._ensure_cursor_visible()

        return None

    def handle_click(self, mx, my, bstate=None):
        """Handle click in the body: place cursor, menu actions and selection start."""
        # Window menu intercept
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if action:
                    return self.execute_action(action)
                return None

        bx, by, bw, bh = self.body_rect()
        body_h = bh - 1  # -1 for status bar

        if not (bx <= mx < bx + bw and by <= my < by + body_h):
            self._mouse_selecting = False
            return None

        self._set_cursor_from_screen(mx, my)
        cursor_pos = (self.cursor_line, self.cursor_col)
        has_button1 = bool(
            bstate
            and (
                bstate & curses.BUTTON1_PRESSED
                or bstate & curses.BUTTON1_CLICKED
                or bstate & curses.BUTTON1_DOUBLE_CLICKED
            )
        )
        if has_button1:
            self.selection_anchor = cursor_pos
            self.selection_cursor = cursor_pos
            self._mouse_selecting = bool(bstate & curses.BUTTON1_PRESSED)
        else:
            self.clear_selection()
        return None

    def handle_mouse_drag(self, mx, my, bstate):
        """Extend selection while primary mouse button is pressed."""
        if not (bstate & curses.BUTTON1_PRESSED):
            self._mouse_selecting = False
            return None

        bx, by, bw, bh = self.body_rect()
        body_h = bh - 1  # -1 for status bar
        if not (bx <= mx < bx + bw and by <= my < by + body_h):
            return None

        self._set_cursor_from_screen(mx, my)
        cursor_pos = (self.cursor_line, self.cursor_col)
        if self.selection_anchor is None:
            self.selection_anchor = cursor_pos
        self.selection_cursor = cursor_pos
        self._mouse_selecting = True
        return None

    def handle_right_click(self, mx, my, bstate):
        """Handle right-click: show context menu."""
        bx, by, bw, bh = self.body_rect()
        if not (bx <= mx < bx + bw and by <= my < by + bh):
             return False

        # Move cursor to click position if not already selecting
        # For simple notepad, let's always move cursor to click position
        self._set_cursor_from_screen(mx, my)
        self._ensure_cursor_visible()
            
        # Actions for context menu
        # We use lambdas or AppActions where possible
        items = [
            {'label': 'Cut Line', 'action': self._cut_current_line},
            {'label': 'Copy Line', 'action': lambda: copy_text(self.buffer[self.cursor_line]) if self.buffer else None},
            {'label': 'Paste', 'action': lambda: self._insert_text(paste_text())},
            {'label': 'Select All', 'action': lambda: self.handle_key(1)}, # Ctrl+A
            {'separator': True},
            {'label': 'Save', 'action': AppAction.NP_SAVE},
            {'label': 'Save As...', 'action': AppAction.NP_SAVE_AS},
            {'separator': True},
            {'label': 'Word Wrap', 'action': AppAction.NP_TOGGLE_WRAP},
            {'label': 'Close', 'action': AppAction.NP_CLOSE},
        ]
        if self.has_selection():
             # Update Copy/Cut to work on selection if it exists
             items[0] = {'label': 'Cut Selection', 'action': lambda: (copy_text(self._selected_text()), self._delete_selection())}
             items[1] = {'label': 'Copy Selection', 'action': lambda: copy_text(self._selected_text())}

        return items

    def get_context_menu_items(self, mx=None, my=None, bstate=None):
        """Deprecated."""
        return []

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

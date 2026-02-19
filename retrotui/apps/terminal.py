"""
Embedded terminal window implementation.
"""
import curses
import shlex

from ..constants import C_SCROLLBAR, C_STATUS
from ..core.actions import ActionResult, ActionType, AppAction
from ..core.clipboard import copy_text, paste_text
from ..core.terminal_session import TerminalSession
from ..core.ansi import AnsiStateMachine
from ..ui.menu import WindowMenu
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr


class TerminalWindow(Window):
    """PTY-backed terminal window with ANSI color support and scrollback."""

    DEFAULT_SCROLLBACK = 2000
    MENU_CLEAR = 'term_clear'
    MENU_COPY = 'term_copy'
    MENU_INTERRUPT = 'term_interrupt'
    MENU_TERMINATE = 'term_terminate'
    MENU_RESTART = 'term_restart'

    def __init__(self, x, y, w, h, shell=None, cwd=None, env=None, max_scrollback=DEFAULT_SCROLLBACK):
        super().__init__('Terminal', x, y, w, h, content=[])
        self.shell = shell
        self.cwd = cwd
        self.env = dict(env or {})
        self.max_scrollback = max(100, int(max_scrollback))

        self._session = None
        self._session_error = None
        
        self.ansi = AnsiStateMachine()

        # Buffer storage: list of list of (char, attr) tuples
        self._scroll_lines = [] 
        self._line_cells = [] 
        self._cursor_col = 0
        self.scrollback_offset = 0
        
        self.selection_anchor = None  # (line_idx, col)
        self.selection_cursor = None  # (line_idx, col)
        self._mouse_selecting = False

        self.window_menu = WindowMenu({
            'Terminal': [
                ('Clear Scrollback', self.MENU_CLEAR),
                ('Copy Selection F8', self.MENU_COPY),
                ('Interrupt Process F6', self.MENU_INTERRUPT),
                ('Terminate Process F7', self.MENU_TERMINATE),
                ('Restart Shell', self.MENU_RESTART),
                ('-------------', None),
                ('Close', AppAction.CLOSE_WINDOW),
            ],
        })

    def clear_selection(self):
        """Clear text selection state."""
        self.selection_anchor = None
        self.selection_cursor = None
        self._mouse_selecting = False

    def has_selection(self):
        """Return True when there is a non-empty selection."""
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
        """Return [start,end) selected cols for one line, or None."""
        bounds = self._selection_bounds()
        if not bounds:
            return None
        (start_line, start_col), (end_line, end_col) = bounds
        if line_idx < start_line or line_idx > end_line:
            return None

        if start_line == end_line:
            start = max(0, min(line_len, start_col))
            end = max(0, min(line_len, end_col))
            if end <= start:
                return None
            return (start, end)

        if line_idx == start_line:
            start = max(0, min(line_len, start_col))
            end = line_len
            if end <= start:
                return None
            return (start, end)

        if line_idx == end_line:
            start = 0
            end = max(0, min(line_len, end_col))
            if end <= start:
                return None
            return (start, end)

        return (0, line_len)

    def _get_line_text(self, line_cells):
        """Helper to convert cell list to plain string."""
        return ''.join(c[0] for c in line_cells)

    def _selected_text(self):
        """Return selected text as plain string."""
        bounds = self._selection_bounds()
        if not bounds:
            return ''
        (start_line, start_col), (end_line, end_col) = bounds
        lines = self._all_lines()
        if not lines:
            return ''

        start_line = max(0, min(start_line, len(lines) - 1))
        end_line = max(0, min(end_line, len(lines) - 1))
        if end_line < start_line:
            return ''

        if start_line == end_line:
            line_str = self._get_line_text(lines[start_line])
            return line_str[max(0, start_col):max(0, end_col)]

        chunks = []
        first_str = self._get_line_text(lines[start_line])
        chunks.append(first_str[max(0, start_col):])
        for idx in range(start_line + 1, end_line):
            chunks.append(self._get_line_text(lines[idx]))
        last_str = self._get_line_text(lines[end_line])
        chunks.append(last_str[:max(0, end_col)])
        return '\n'.join(chunks)

    def _cursor_from_screen(self, mx, my):
        """Convert body coordinates to terminal line/column cursor."""
        bx, by, bw, bh = self.body_rect()
        text_cols, text_rows = max(1, bw - 1), max(1, bh - 1)
        if not (bx <= mx < bx + text_cols and by <= my < by + text_rows):
            return None

        _, start_idx, total_lines = self._visible_slice(text_rows)
        if total_lines <= 0:
            return None

        row = my - by
        line_idx = max(0, min(total_lines - 1, start_idx + row))
        all_lines = self._all_lines()
        line_cells = all_lines[line_idx] if line_idx < len(all_lines) else []
        col = max(0, min(len(line_cells), mx - bx))
        return (line_idx, col)

    def _copy_selection(self):
        """Copy selection to shared clipboard (or current line fallback)."""
        text = self._selected_text()
        if not text:
            # Fallback copy current line text
            text = self._get_line_text(self._line_cells)
        if text:
            copy_text(text)

    def _text_area_size(self):
        """Return (cols, rows) available for terminal text rendering."""
        _, _, bw, bh = self.body_rect()
        return max(1, bw - 1), max(1, bh - 1)

    def _ensure_session(self):
        """Create and start PTY session once when needed."""
        if self._session is not None or self._session_error is not None:
            return
        if not TerminalSession.is_supported():
            self._session_error = 'Embedded terminal is not supported on this platform.'
            return

        cols, rows = self._text_area_size()
        session = TerminalSession(shell=self.shell, cwd=self.cwd, env=self.env, cols=cols, rows=rows)
        try:
            session.start()
        except (RuntimeError, OSError) as exc:
            self._session_error = str(exc)
            return

        self._session = session

    # OLD _strip_ansi removed, replaced by self.ansi usage

    def _write_char(self, ch, attr):
        """Write one character with attribute at current cursor."""
        if self._cursor_col < len(self._line_cells):
            self._line_cells[self._cursor_col] = (ch, attr)
        else:
            # Pad with spaces if cursor jumped ahead
            while len(self._line_cells) < self._cursor_col:
                self._line_cells.append((' ', 0))
            self._line_cells.append((ch, attr))
        self._cursor_col += 1

    def _append_newline(self):
        """Commit current line to scrollback."""
        # We store the list of cells directly
        self._scroll_lines.append(list(self._line_cells))
        self._line_cells = []
        self._cursor_col = 0
        overflow = len(self._scroll_lines) - self.max_scrollback
        if overflow > 0:
            del self._scroll_lines[:overflow]

    def _erase_line(self, mode):
        """Apply CSI K (erase in line) mode."""
        # Use default attr (0) for erased cells? Or current ansi attr?
        # Usually erase uses current background color.
        fill_attr = self.ansi.attr
        
        if mode == 2: # Clear entire line
            self._line_cells = []
            self._cursor_col = 0
            return

        if mode == 1: # Clear from beginning to cursor
            end = min(len(self._line_cells), self._cursor_col + 1)
            for i in range(end):
                self._line_cells[i] = (' ', fill_attr)
            return

        # mode 0 (default): erase from cursor to end
        if self._cursor_col < len(self._line_cells):
            # Truncate or fill with spaces?
            # Standard terminals fill with spaces (and background color).
            # If we just truncate, we lose background color extending to right.
            # For simplicity in this TUI, truncating is cleaner for implementation 
            # unless we implement fixed-width line buffers.
            # Let's truncate for now to avoid management hell.
            del self._line_cells[self._cursor_col:]

    def _apply_csi(self, params, final):
        """Handle CSI controls for layout (attributes handled by AnsiStateMachine)."""
        # params is a list of ints
        
        def _num(index, default):
            if index >= len(params):
                return default
            return params[index]

        if final == 'D':  # Cursor left
            self._cursor_col = max(0, self._cursor_col - max(1, _num(0, 1)))
            return
        if final == 'C':  # Cursor right
            self._cursor_col = max(0, self._cursor_col + max(1, _num(0, 1)))
            return
        if final == 'G':  # Cursor horizontal absolute (1-based)
            self._cursor_col = max(0, _num(0, 1) - 1)
            return
        if final in ('H', 'f'):  # Cursor position (row;col) - we only support column
            # We are single-line editable, row moves usually ignored or just clear?
            # Implies we handle full screen addressable terminal?
            # Our simple terminal is a rolling logger + single line edit mostly.
            # But "real" programs use H to move around.
            # Since we only render `_scroll_lines` (history) + `_line_cells` (current),
            # we can't easily support moving UP into history to edit it.
            # We treat H as setting column only for the current line.
            col = _num(1, 1)
            self._cursor_col = max(0, col - 1)
            return
        if final == 'K':  # Erase in line
            self._erase_line(_num(0, 0))
            return
        if final == 'P':  # Delete character(s) at cursor
            count = max(1, _num(0, 1))
            if self._cursor_col < len(self._line_cells):
                del self._line_cells[self._cursor_col:self._cursor_col + count]
            return
        if final == 'J': # Erase in display
            # 2J = clear screen. `clear` command uses this.
            mode = _num(0, 0)
            if mode == 2:
                self._scroll_lines = []
                self._line_cells = []
                self._cursor_col = 0
                self.scrollback_offset = 0

    def _consume_output(self, text):
        """Feed text to ANSI state machine and update buffer."""
        if not text:
            return
        
        prev_total = len(self._all_lines())
        prev_offset = self.scrollback_offset
        # if text: self.clear_selection() # Optional: clear selection on output? 
        # Standard terminals usually don't clear selection on output, only on input.
        
        for kind, data, attr in self.ansi.parse_chunk(text):
            if kind == 'TEXT':
                self._write_char(data, attr)
            elif kind == 'CONTROL':
                if data == '\n':
                    self._append_newline()
                elif data == '\r':
                    self._cursor_col = 0
                elif data == '\b':
                    self._cursor_col = max(0, self._cursor_col - 1)
                elif data == '\t':
                    spaces = 4 - (self._cursor_col % 4)
                    current_attr = self.ansi.attr
                    for _ in range(spaces):
                        self._write_char(' ', current_attr)
            elif kind == 'CSI':
                # data is final char, attr is params list
                self._apply_csi(attr, data)
        
        # Smart scrolling: if we were at the bottom, stay at the bottom.
        # If we were scrolled up, try to maintain relative position?
        # Actually standard behavior: if at bottom, autoscroll. If up, stay put.
        # "at bottom" means scrollback_offset == 0.
        
        if prev_offset > 0:
            # We were looking at history.
            new_total = len(self._all_lines())
            appended = max(0, new_total - prev_total)
            if appended > 0:
                # To keep viewing the same lines, we must increase offset?
                # scrollback_offset is "lines back from end".
                # If we add N lines to end, and want to show same lines,
                # we must increase offset by N.
                _, text_rows = self._text_area_size()
                max_offset = self._max_scrollback_offset(text_rows)
                self.scrollback_offset = min(max_offset, prev_offset + appended)

    def _all_lines(self):
        """Return all lines including current editable line (as lists of cells)."""
        # _scroll_lines is list of lists
        # _line_cells is list
        return self._scroll_lines + [list(self._line_cells)]

    def _max_scrollback_offset(self, text_rows):
        return max(0, len(self._all_lines()) - max(1, text_rows))

    def _visible_slice(self, text_rows):
        text_rows = max(1, text_rows)
        lines = self._all_lines()
        total = len(lines)
        max_offset = max(0, total - text_rows)
        
        if self.scrollback_offset > max_offset:
            self.scrollback_offset = max_offset
            
        start = max(0, total - text_rows - self.scrollback_offset)
        return lines[start:start + text_rows], start, total

    @staticmethod
    def _fit_line(line_cells, width):
        """Clip/pad one cell list to exact width."""
        # Returns list of (char, attr)
        # Pad with (space, 0)
        clipped = line_cells[:width]
        if len(clipped) < width:
            clipped.extend([(' ', 0)] * (width - len(clipped)))
        return clipped

    def _draw_scrollback_bar(self, stdscr, x, y, rows, start_idx, total_lines):
        if total_lines <= rows or rows <= 1:
            return
        thumb_pos = int(start_idx / max(1, total_lines - rows) * (rows - 1))
        for i in range(rows):
            ch = '█' if i == thumb_pos else '░'
            safe_addstr(stdscr, y + i, x, ch, theme_attr('scrollbar'))

    def _draw_live_cursor(self, stdscr, x, y, text_cols, text_rows, start_idx, total_lines, body_attr):
        if not self.active or self.scrollback_offset != 0:
            return
        if total_lines <= 0:
            return

        cursor_line_idx = total_lines - 1
        if not (start_idx <= cursor_line_idx < start_idx + text_rows):
            return

        row = y + (cursor_line_idx - start_idx)
        col = max(0, self._cursor_col)
        if col >= text_cols:
            col = text_cols - 1

        # Retrieve char at cursor
        current_cells = self._line_cells
        if col < len(current_cells):
            ch, attr = current_cells[col]
        else:
            ch, attr = ' ', 0

        # Combine attributes: cell attr | window body attr | reverse for cursor
        # Note: if cell has its own attr (color), use it. 
        # If cell attr is 0, use body_attr.
        effective_attr = attr if attr else body_attr
        
        if ch == ' ':
            safe_addstr(stdscr, row, x + col, '_', effective_attr | curses.A_BOLD)
            return

        safe_addstr(stdscr, row, x + col, ch, effective_attr | curses.A_REVERSE | curses.A_BOLD)

    def _draw_selection(self, stdscr, x, y, text_cols, start_idx, visible_lines, body_attr):
        """Draw reverse-video overlay for selected text."""
        # visible_lines is list of cell-lists
        if not self.has_selection():
            return
        for row, line_cells in enumerate(visible_lines):
            line_idx = start_idx + row
            span = self._line_selection_span(line_idx, len(line_cells))
            if not span:
                continue
            start, end = span
            if start >= text_cols:
                continue
            start = max(0, start)
            end = min(max(start, end), text_cols)
            if end <= start:
                continue
            
            # For selection, we just invert the range
            for col in range(start, end):
                if col < len(line_cells):
                    ch, attr = line_cells[col]
                else:
                    ch, attr = ' ', 0
                effective_attr = attr if attr else body_attr
                safe_addstr(stdscr, y + row, x + col, ch, effective_attr | curses.A_REVERSE | curses.A_BOLD)

    def draw(self, stdscr):
        """Draw terminal body, live output, scrollback and status line."""
        if not self.visible:
            return

        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        text_cols, text_rows = max(1, bw - 1), max(1, bh - 1)

        # Clear background
        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, ' ' * bw, body_attr)

        self._ensure_session()
        if self._session is not None:
            self._session.resize(text_cols, text_rows)
            chunk = self._session.read()
            if chunk:
                self._consume_output(chunk)
            self._session.poll_exit()
        elif self._session_error and not self._scroll_lines and not self._line_cells:
            self._consume_output(self._session_error + '\n')

        visible, start_idx, total_lines = self._visible_slice(text_rows)
        
        # Render visible lines
        # visible is list of lists of (char, attr)
        for i, line_cells in enumerate(visible):
            # Fit line to width
            fitted = self._fit_line(line_cells, text_cols)
            for j, (ch, attr) in enumerate(fitted):
                # Use cell attribute if present, else body_attr
                # Also ensure we don't crash on weird attributes
                safe_addstr(stdscr, by + i, bx + j, ch, attr if attr else body_attr)

        self._draw_selection(stdscr, bx, by, text_cols, start_idx, visible, body_attr)
        self._draw_live_cursor(stdscr, bx, by, text_cols, text_rows, start_idx, total_lines, body_attr)
        self._draw_scrollback_bar(stdscr, bx + text_cols, by, text_rows, start_idx, total_lines)

        if self._session_error:
            state = 'ERR'
        elif self._session is None:
            state = 'INIT'
        elif self._session.running:
            state = 'RUN'
        else:
            state = 'EXIT'
        live_state = 'LIVE' if self.scrollback_offset == 0 else f'BACK {self.scrollback_offset}'
        status = f' {state}  {live_state} '
        safe_addstr(stdscr, by + bh - 1, bx, status.ljust(bw)[:bw], theme_attr('status'))

        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def _key_to_input(self, key, key_code):
        """Translate curses key events to terminal input bytes."""
        special = {
            getattr(curses, 'KEY_UP', None): '\x1b[A',
            getattr(curses, 'KEY_DOWN', None): '\x1b[B',
            getattr(curses, 'KEY_RIGHT', None): '\x1b[C',
            getattr(curses, 'KEY_LEFT', None): '\x1b[D',
            getattr(curses, 'KEY_HOME', None): '\x1b[H',
            getattr(curses, 'KEY_END', None): '\x1b[F',
            getattr(curses, 'KEY_PPAGE', None): '\x1b[5~',
            getattr(curses, 'KEY_NPAGE', None): '\x1b[6~',
            getattr(curses, 'KEY_IC', None): '\x1b[2~',
            getattr(curses, 'KEY_DC', None): '\x1b[3~',
        }
        if key_code in special and special[key_code] is not None:
            return special[key_code]
        if key_code in (getattr(curses, 'KEY_ENTER', -1), 10, 13):
            return '\r'
        if key_code in (getattr(curses, 'KEY_BACKSPACE', -1), 127, 8):
            return '\x7f'
        if key_code == 9:
            return '\t'
        if isinstance(key_code, int) and 1 <= key_code <= 26:
            return chr(key_code)
        if isinstance(key, str):
            if key in ('\n', '\r'):
                return '\r'
            if key == '\t':
                return '\t'
            if len(key) == 1 and key.isprintable():
                return key
            return None
        if isinstance(key, int) and 32 <= key <= 126:
            return chr(key)
        return None

    def execute_action(self, action):
        """Execute terminal window menu action."""
        if action == self.MENU_CLEAR:
            self._scroll_lines = []
            self._line_cells = []
            self._cursor_col = 0
            self.scrollback_offset = 0
            self.clear_selection()
            return None
        if action == self.MENU_COPY:
            self._copy_selection()
            return None
        if action == self.MENU_INTERRUPT:
            self._send_interrupt()
            return None
        if action == self.MENU_TERMINATE:
            self._send_terminate()
            return None
        if action == self.MENU_RESTART:
            self.restart_session()
            return None
        if action == AppAction.CLOSE_WINDOW:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

    def _send_interrupt(self):
        """Interrupt foreground process without using host Ctrl+C."""
        self._ensure_session()
        if self._session is None or not self._session.running:
            return
        self.scrollback_offset = 0
        try:
            sender = getattr(self._session, 'interrupt', None)
            if callable(sender):
                if sender():
                    return
            else:
                self._session.write('\x03')
                return
            self._session.write('\x03')
        except OSError as exc:
            self._session_error = str(exc)

    def _send_terminate(self):
        """Terminate foreground process group (fallback: interrupt)."""
        self._ensure_session()
        if self._session is None or not self._session.running:
            return
        self.scrollback_offset = 0
        try:
            sender = getattr(self._session, 'terminate', None)
            if callable(sender):
                if sender():
                    return
            self._session.write('\x03')
        except OSError as exc:
            self._session_error = str(exc)

    def _forward_payload(self, payload):
        """Write one payload chunk into the PTY session when available."""
        if payload is None or payload == '':
            return
        self._ensure_session()
        if self._session is None or not self._session.running:
            return
        self.scrollback_offset = 0
        try:
            self._session.write(payload)
        except OSError as exc:
            self._session_error = str(exc)

    def accept_dropped_path(self, path):
        """Accept file drop payload by inserting a shell-safe path token."""
        if path is None:
            return None
        token = shlex.quote(str(path))
        if not token:
            return None
        self._forward_payload(token + ' ')
        return None

    def handle_key(self, key):
        """Handle keyboard input and forward supported keys to the PTY."""
        key_code = normalize_key_code(key)

        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self.execute_action(action)
            return None

        if key_code == getattr(curses, 'KEY_F6', -1):
            self._send_interrupt()
            return None
        if key_code == getattr(curses, 'KEY_F7', -1):
            self._send_terminate()
            return None
        if key_code == getattr(curses, 'KEY_F8', -1):
            self._copy_selection()
            return None

        if key_code == getattr(curses, 'KEY_PPAGE', -1):
            _, text_rows = self._text_area_size()
            self.handle_scroll('up', max(1, text_rows - 1))
            return None
        if key_code == getattr(curses, 'KEY_NPAGE', -1):
            _, text_rows = self._text_area_size()
            self.handle_scroll('down', max(1, text_rows - 1))
            return None

        if key_code == 22:
            self._forward_payload(paste_text())
            return None

        payload = self._key_to_input(key, key_code)
        if payload is None:
            return None

        self._forward_payload(payload)
        return None

    def handle_click(self, mx, my, bstate=None):
        """Handle click inside terminal window/menu."""
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if action:
                    return self.execute_action(action)
                return None

        bx, by, bw, bh = self.body_rect()
        text_cols, text_rows = max(1, bw - 1), max(1, bh - 1)
        if bx <= mx < bx + text_cols and by <= my < by + text_rows:
            if bstate is not None:
                has_button1 = bool(
                    bstate
                    & (
                        getattr(curses, 'BUTTON1_PRESSED', 0)
                        | getattr(curses, 'BUTTON1_CLICKED', 0)
                        | getattr(curses, 'BUTTON1_DOUBLE_CLICKED', 0)
                    )
                )
                if has_button1:
                    cursor_pos = self._cursor_from_screen(mx, my)
                    if cursor_pos is not None:
                        self.selection_anchor = cursor_pos
                        self.selection_cursor = cursor_pos
                        self._mouse_selecting = bool(bstate & getattr(curses, 'BUTTON1_PRESSED', 0))
                else:
                    self.clear_selection()
        elif bstate is not None and (
            bstate
            & (
                getattr(curses, 'BUTTON1_CLICKED', 0)
                | getattr(curses, 'BUTTON1_PRESSED', 0)
                | getattr(curses, 'BUTTON1_DOUBLE_CLICKED', 0)
            )
        ):
            self.clear_selection()
        return None

    def handle_right_click(self, mx, my, bstate):
        """Show context menu on right click."""
        bx, by, bw, bh = self.body_rect()
        if not (bx <= mx < bx + bw and by <= my < by + bh):
            return False

        items = []
        if self.has_selection():
            items.append({'label': 'Copy Selection', 'action': self.MENU_COPY})

        items.append({'label': 'Paste', 'action': lambda: self._forward_payload(paste_text())})
        items.append({'separator': True})
        items.append({'label': 'Clear Scrollback', 'action': self.MENU_CLEAR})
        items.append({'label': 'Restart Shell', 'action': self.MENU_RESTART})
        items.append({'separator': True})
        items.append({'label': 'Properties', 'action': None})
        items.append({'label': 'Close', 'action': AppAction.CLOSE_WINDOW})
        
        return items

    def handle_mouse_drag(self, mx, my, bstate):
        """Extend selection while primary mouse button is pressed."""
        if not (bstate & getattr(curses, 'BUTTON1_PRESSED', 0)):
            self._mouse_selecting = False
            return None
        cursor_pos = self._cursor_from_screen(mx, my)
        if cursor_pos is None:
            return None
        if self.selection_anchor is None:
            self.selection_anchor = cursor_pos
        self.selection_cursor = cursor_pos
        self._mouse_selecting = True
        return None

    def handle_scroll(self, direction, steps=1):
        """Scroll terminal scrollback with mouse wheel."""
        count = max(1, steps)
        _, text_rows = self._text_area_size()
        max_offset = self._max_scrollback_offset(text_rows)
        if direction == 'up':
            self.scrollback_offset = min(max_offset, self.scrollback_offset + count)
        elif direction == 'down':
            self.scrollback_offset = max(0, self.scrollback_offset - count)

    def restart_session(self):
        """Reset scrollback state and start a fresh shell session lazily."""
        self.close()
        self._session_error = None
        self.ansi = AnsiStateMachine() # Reset ansi state
        self._scroll_lines = []
        self._line_cells = []
        self._cursor_col = 0
        self.scrollback_offset = 0

    def close(self):
        """Release PTY resources when terminal window is closed."""
        if self._session is not None:
            self._session.close()
            self._session = None

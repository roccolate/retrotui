"""
Embedded terminal window implementation.
"""
import curses

from ..constants import C_SCROLLBAR, C_STATUS
from ..core.actions import ActionResult, ActionType, AppAction
from ..core.clipboard import paste_text
from ..core.terminal_session import TerminalSession
from ..ui.menu import WindowMenu
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr


class TerminalWindow(Window):
    """PTY-backed terminal window with basic ANSI parsing and scrollback."""

    DEFAULT_SCROLLBACK = 2000
    MENU_CLEAR = 'term_clear'
    MENU_RESTART = 'term_restart'

    def __init__(self, x, y, w, h, shell=None, cwd=None, env=None, max_scrollback=DEFAULT_SCROLLBACK):
        super().__init__('Terminal', x, y, w, h, content=[])
        self.shell = shell
        self.cwd = cwd
        self.env = dict(env or {})
        self.max_scrollback = max(100, int(max_scrollback))

        self._session = None
        self._session_error = None
        self._ansi_pending = ''

        self._scroll_lines = []
        self._line_chars = []
        self._cursor_col = 0
        self.scrollback_offset = 0

        self.window_menu = WindowMenu({
            'Terminal': [
                ('Clear Scrollback', self.MENU_CLEAR),
                ('Restart Shell', self.MENU_RESTART),
                ('-------------', None),
                ('Close', AppAction.CLOSE_WINDOW),
            ],
        })

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

    def _strip_ansi(self, text):
        """Strip ANSI/VT100 escape sequences and keep partial sequences buffered."""
        data = self._ansi_pending + (text or '')
        out = []
        idx = 0
        data_len = len(data)

        while idx < data_len:
            ch = data[idx]
            if ch != '\x1b':
                out.append(ch)
                idx += 1
                continue

            if idx + 1 >= data_len:
                break

            marker = data[idx + 1]

            # CSI sequence: ESC [ ... final-byte
            if marker == '[':
                end = idx + 2
                while end < data_len and not ('@' <= data[end] <= '~'):
                    end += 1
                if end >= data_len:
                    break
                idx = end + 1
                continue

            # OSC sequence: ESC ] ... BEL or ESC \
            if marker == ']':
                end = idx + 2
                found = False
                while end < data_len:
                    if data[end] == '\x07':
                        end += 1
                        found = True
                        break
                    if data[end] == '\x1b' and end + 1 < data_len and data[end + 1] == '\\':
                        end += 2
                        found = True
                        break
                    end += 1
                if not found:
                    break
                idx = end
                continue

            # Two-byte escape sequence.
            idx += 2

        self._ansi_pending = data[idx:]
        return ''.join(out)

    def _write_char(self, ch):
        """Write one printable character at the current terminal cursor column."""
        if self._cursor_col < len(self._line_chars):
            self._line_chars[self._cursor_col] = ch
        else:
            while len(self._line_chars) < self._cursor_col:
                self._line_chars.append(' ')
            self._line_chars.append(ch)
        self._cursor_col += 1

    def _append_newline(self):
        """Commit current line to scrollback and move cursor to next line."""
        self._scroll_lines.append(''.join(self._line_chars))
        self._line_chars = []
        self._cursor_col = 0
        overflow = len(self._scroll_lines) - self.max_scrollback
        if overflow > 0:
            del self._scroll_lines[:overflow]

    def _erase_line(self, mode):
        """Apply CSI K (erase in line) mode."""
        if mode == 2:
            self._line_chars = []
            self._cursor_col = 0
            return

        if mode == 1:
            end = min(len(self._line_chars), self._cursor_col + 1)
            for i in range(end):
                self._line_chars[i] = ' '
            return

        # mode 0 (default): erase from cursor to end
        if self._cursor_col < len(self._line_chars):
            del self._line_chars[self._cursor_col:]

    def _apply_csi(self, params, final):
        """Handle the subset of CSI controls needed for shell line editing."""
        parts = params.split(';') if params else []

        def _num(index, default):
            if index >= len(parts):
                return default
            token = parts[index]
            if not token or not token.isdigit():
                return default
            return int(token)

        if final == 'D':  # Cursor left
            self._cursor_col = max(0, self._cursor_col - max(1, _num(0, 1)))
            return
        if final == 'C':  # Cursor right
            self._cursor_col = max(0, self._cursor_col + max(1, _num(0, 1)))
            return
        if final == 'G':  # Cursor horizontal absolute (1-based)
            self._cursor_col = max(0, _num(0, 1) - 1)
            return
        if final in ('H', 'f'):  # Cursor position (row;col), we only track column
            col = _num(1, 1) if len(parts) > 1 else 1
            self._cursor_col = max(0, col - 1)
            return
        if final == 'K':  # Erase in line
            self._erase_line(_num(0, 0))
            return

    def _consume_output(self, text):
        """Apply terminal output stream to local scrollback buffer."""
        data = self._ansi_pending + (text or '')
        self._ansi_pending = ''
        idx = 0
        data_len = len(data)

        while idx < data_len:
            ch = data[idx]
            if ch == '\x1b':
                if idx + 1 >= data_len:
                    break

                marker = data[idx + 1]
                if marker == '[':
                    end = idx + 2
                    while end < data_len and not ('@' <= data[end] <= '~'):
                        end += 1
                    if end >= data_len:
                        break
                    self._apply_csi(data[idx + 2:end], data[end])
                    idx = end + 1
                    continue

                if marker == ']':
                    end = idx + 2
                    found = False
                    while end < data_len:
                        if data[end] == '\x07':
                            end += 1
                            found = True
                            break
                        if data[end] == '\x1b' and end + 1 < data_len and data[end + 1] == '\\':
                            end += 2
                            found = True
                            break
                        end += 1
                    if not found:
                        break
                    idx = end
                    continue

                # Two-byte escape sequence: ignore.
                idx += 2
                continue

            if ch == '\n':
                self._append_newline()
            elif ch == '\r':
                self._cursor_col = 0
            elif ch == '\b':
                self._cursor_col = max(0, self._cursor_col - 1)
            elif ch == '\t':
                spaces = 4 - (self._cursor_col % 4)
                for _ in range(spaces):
                    self._write_char(' ')
            elif ch >= ' ' and ch != '\x7f':
                self._write_char(ch)
            idx += 1

        self._ansi_pending = data[idx:]

    def _all_lines(self):
        """Return all lines including current editable line."""
        return self._scroll_lines + [''.join(self._line_chars)]

    def _max_scrollback_offset(self, text_rows):
        """Maximum scrollback offset based on current buffer length."""
        return max(0, len(self._all_lines()) - max(1, text_rows))

    def _visible_slice(self, text_rows):
        """Return (visible_lines, start_index, total_lines)."""
        text_rows = max(1, text_rows)
        lines = self._all_lines()
        total = len(lines)
        max_offset = max(0, total - text_rows)
        if self.scrollback_offset > max_offset:
            self.scrollback_offset = max_offset
        start = max(0, total - text_rows - self.scrollback_offset)
        return lines[start:start + text_rows], start, total

    @staticmethod
    def _fit_line(text, width):
        """Clip/pad one text line to exact width in terminal cells."""
        return text[:width].ljust(width)

    def _draw_scrollback_bar(self, stdscr, x, y, rows, start_idx, total_lines):
        """Draw a one-column scrollbar for scrollback position."""
        if total_lines <= rows or rows <= 1:
            return
        thumb_pos = int(start_idx / max(1, total_lines - rows) * (rows - 1))
        for i in range(rows):
            ch = '█' if i == thumb_pos else '░'
            safe_addstr(stdscr, y + i, x, ch, theme_attr('scrollbar'))

    def _draw_live_cursor(self, stdscr, x, y, text_cols, text_rows, start_idx, total_lines, body_attr):
        """Draw a visual cursor on the current editable line when in LIVE mode."""
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

        line_text = ''.join(self._line_chars)
        ch = line_text[col] if col < len(line_text) else ' '
        if ch == ' ':
            # Some terminals do not show reverse-video spaces clearly.
            safe_addstr(stdscr, row, x + col, '_', body_attr | curses.A_BOLD)
            return

        safe_addstr(stdscr, row, x + col, ch, body_attr | curses.A_REVERSE | curses.A_BOLD)

    def draw(self, stdscr):
        """Draw terminal body, live output, scrollback and status line."""
        if not self.visible:
            return

        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        text_cols, text_rows = max(1, bw - 1), max(1, bh - 1)

        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, ' ' * bw, body_attr)

        self._ensure_session()
        if self._session is not None:
            self._session.resize(text_cols, text_rows)
            chunk = self._session.read()
            if chunk:
                self._consume_output(chunk)
            self._session.poll_exit()
        elif self._session_error and not self._scroll_lines and not self._line_chars:
            self._consume_output(self._session_error + '\n')

        visible, start_idx, total_lines = self._visible_slice(text_rows)
        for i, line in enumerate(visible):
            safe_addstr(stdscr, by + i, bx, self._fit_line(line, text_cols), body_attr)

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

    def _execute_menu_action(self, action):
        """Execute terminal window menu action."""
        if action == self.MENU_CLEAR:
            self._scroll_lines = []
            self._line_chars = []
            self._cursor_col = 0
            self.scrollback_offset = 0
            return None
        if action == self.MENU_RESTART:
            self.restart_session()
            return None
        if action == AppAction.CLOSE_WINDOW:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

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

    def handle_key(self, key):
        """Handle keyboard input and forward supported keys to the PTY."""
        key_code = normalize_key_code(key)

        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self._execute_menu_action(action)
            return None

        if key_code == 22:
            self._forward_payload(paste_text())
            return None

        payload = self._key_to_input(key, key_code)
        if payload is None:
            return None

        self._forward_payload(payload)
        return None

    def handle_click(self, mx, my):
        """Handle click inside terminal window/menu."""
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if action:
                    return self._execute_menu_action(action)
                return None

        bx, by, bw, bh = self.body_rect()
        if bx <= mx < bx + bw and by <= my < by + bh:
            self.scrollback_offset = 0
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
        self._ansi_pending = ''
        self._scroll_lines = []
        self._line_chars = []
        self._cursor_col = 0
        self.scrollback_offset = 0

    def close(self):
        """Release PTY resources when terminal window is closed."""
        if self._session is not None:
            self._session.close()
            self._session = None

"""
Embedded terminal window implementation.
"""
import curses
import shlex
from collections import deque

from ..constants import C_SCROLLBAR, C_STATUS
from ..core.actions import ActionResult, ActionType, AppAction
from ..core.clipboard import copy_text, paste_text
from ..core.terminal_session import TerminalScreen, TerminalScreenBuffer, TerminalSession
from ..core.ansi import AnsiStateMachine
from ..ui.menu import WindowMenu
from ..ui.selectable_text import SelectableTextMixin
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr


class _ScrollbackBuffer(TerminalScreenBuffer):
    """TerminalScreenBuffer variant that captures rows into a shared deque.

    The normal-screen buffer is the live source of truth. Rows enter scrollback
    only when they actually scroll off the top, whether overflow was caused by
    an explicit newline or by word-wrap. Newlines that merely advance within
    the visible grid must not copy a row that the grid still owns.
    """

    __slots__ = ("_scrollback",)

    def __init__(self, rows, cols, scrollback, default_attr=0):
        super().__init__(rows, cols, default_attr=default_attr)
        self._scrollback = scrollback
        self.set_scroll_sink(scrollback.append)


# DEC private mouse modes that the child program can enable to receive
# mouse events as ANSI escape sequences. ``1006`` (SGR encoding) is the
# modern default; ``1000``/``1002``/``1003`` are the legacy X11 modes that
# use byte-encoded coordinates. ``1005`` (UTF-8) and ``1015`` (urxvt) are
# tracked but rendered with the SGR encoding — close enough for the common
# cases and clearly wrong only for clients that probe the mode byte exactly.
_MOUSE_REPORT_MODES = frozenset({1000, 1002, 1003, 1005, 1006, 1015})


class TerminalWindow(SelectableTextMixin, Window):
    """PTY-backed terminal window with ANSI color support and scrollback."""

    # PTY sessions are services: minimizing the window must not suspend reads.
    tick_when_hidden = True
    DEFAULT_SCROLLBACK = 2000
    MAX_OUTPUT_PER_FRAME = 8192  # Compatibility name: max chars processed per service tick.
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
        self._reported_session_error = False
        self._last_pty_size = None
        self._pending_output = ''

        self.ansi = AnsiStateMachine()

        # v0.9.5: the normal-screen and alt-screen are now two TerminalScreenBuffer
        # cells inside a single ``TerminalScreen``. The normal-screen buffer
        # captures rows into ``self._scrollback`` as they scroll off the top,
        # so the ANSI state machine writes through ``put_char`` / ``line_feed``
        # / ``clear_screen`` and the buffer stays the source of truth.
        text_cols, text_rows = self._text_area_size()
        self._scrollback: deque = deque(maxlen=self.max_scrollback)
        self._normal_buf = _ScrollbackBuffer(
            text_rows, text_cols, scrollback=self._scrollback
        )
        self._alt_buf = TerminalScreenBuffer(text_rows, text_cols)
        self._screen = TerminalScreen.__new__(TerminalScreen)
        self._screen._normal = self._normal_buf
        self._screen._alt = self._alt_buf
        self._screen._active = self._normal_buf

        # DEC private mouse modes enabled by the child via CSI ?nh.
        # When non-empty the child wants raw mouse events, so RetroTUI
        # forwards clicks/drags/scroll instead of using them for selection
        # and window control. This is what makes full-screen TUI apps like
        # vim/htop receive the mouse — and it's the GPM-compat switch:
        # when no mode is set, RetroTUI keeps the mouse for menus/selection.
        self._mouse_modes: set = set()

        self.scrollback_offset = 0

        self._init_selection()

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

    # ------------------------------------------------------------------
    # Backward-compatible state properties. The buffer is the source of
    # truth; these mirror the legacy field names so existing callers and
    # tests keep working while reads/writes route through the buffer.
    # ------------------------------------------------------------------

    @property
    def _alt_screen(self) -> bool:
        return self._screen.alt_screen

    @_alt_screen.setter
    def _alt_screen(self, value: bool):
        # Reset the user's scrollback offset when switching modes so
        # the next ``ctrl-W`` / ``Normal`` exit doesn't leave the user
        # offset into pre-existing scrollback (e.g. alt-screen exits
        # mid-session). TUI programs expect a clean view.
        self.scrollback_offset = 0
        self._screen.set_alt_screen(bool(value))

    @property
    def _cursor_col(self) -> int:
        return self._screen.cursor_col

    @_cursor_col.setter
    def _cursor_col(self, value: int):
        self._screen.set_cursor(self._screen.cursor_row, int(value))

    @property
    def _cursor_row(self) -> int:
        return self._screen.cursor_row

    @_cursor_row.setter
    def _cursor_row(self, value: int):
        self._screen.set_cursor(int(value), self._screen.cursor_col)

    @property
    def _alt_cursor_row(self) -> int:
        return self._screen._alt.cursor_row

    @_alt_cursor_row.setter
    def _alt_cursor_row(self, value: int):
        self._screen._alt.set_cursor(int(value), self._screen._alt.cursor_col)

    @property
    def _alt_cursor_col(self) -> int:
        return self._screen._alt.cursor_col

    @_alt_cursor_col.setter
    def _alt_cursor_col(self, value: int):
        self._screen._alt.set_cursor(self._screen._alt.cursor_row, int(value))

    @property
    def _line_cells(self) -> list:
        """Return the cells of the row that holds the cursor.

        Normal-screen: the cursor always sits on the bottom row. Alt-screen:
        the row at the current cursor position. The list is rstripped to
        keep the legacy contract where the row is only as long as the
        non-space content (the underlying buffer keeps the full width).
        """
        row = self._screen._active.get_row(self._screen._active.cursor_row)
        trimmed = list(row)
        while trimmed and trimmed[-1] == (" ", self._screen._active._default_attr):
            trimmed.pop()
        return trimmed

    @_line_cells.setter
    def _line_cells(self, value: list):
        active = self._screen._active
        # Legacy callers expect ``_line_cells`` to map onto the "current"
        # line (the bottom of the visible window). On the buffer we model
        # that as the last row; recenter the cursor there so reads via
        # ``cursor_row`` / ``cursor_col`` agree with what was written.
        row = active.rows - 1
        active.set_cursor(row, active.cursor_col)
        row_cells = list(value)
        if len(row_cells) < active.cols:
            row_cells.extend([(" ", active._default_attr)] * (active.cols - len(row_cells)))
        elif len(row_cells) > active.cols:
            row_cells = row_cells[:active.cols]
        active._grid[row] = row_cells

    @property
    def _scroll_lines(self) -> list:
        """Return the legacy committed-line view without duplicate storage.

        ``self._scrollback`` owns only rows that have left the visible grid.
        Older callers expected this property to also expose completed rows that
        are still visible, so they are appended as a transient view and capped
        to ``max_scrollback``. Rendering never consumes this compatibility view.
        """
        lines = list(self._scrollback)
        if not self._alt_screen:
            lines.extend(
                self._normal_buf.get_row(row)
                for row in range(self._normal_buf.cursor_row)
            )
        if self.max_scrollback > 0 and len(lines) > self.max_scrollback:
            lines = lines[-self.max_scrollback:]
        return lines

    @_scroll_lines.setter
    def _scroll_lines(self, value: list):
        # Replace the scrollback deque contents (keeping the maxlen cap) and
        # rebind the sink so future overflow cannot append into the old deque.
        self._scrollback = deque(list(value), maxlen=self.max_scrollback)
        self._normal_buf._scrollback = self._scrollback
        self._normal_buf.set_scroll_sink(self._scrollback.append)

    @property
    def _alt_lines(self) -> list:
        return [self._screen._alt.get_row(r) for r in range(self._screen._alt.rows)]

    @_alt_lines.setter
    def _alt_lines(self, value: list):
        alt = self._screen._alt
        new_rows = len(value)
        new_cols = max((len(row) for row in value), default=alt.cols)
        if new_rows == 0:
            # Preserve the buffer's column count so the cell writes below stay
            # in range when ``value`` is empty.
            new_cols = max(new_cols, alt.cols)
        alt.resize(new_rows, new_cols)
        for r in range(alt.rows):
            if r < len(value):
                row = list(value[r])
                if len(row) < alt.cols:
                    row.extend([(" ", alt._default_attr)] * (alt.cols - len(row)))
                alt._grid[r] = row[:alt.cols]
            else:
                alt._grid[r] = [(" ", alt._default_attr) for _ in range(alt.cols)]


    def _sync_screen_size(self):
        """Resize both buffers to match the current text area dimensions."""
        text_cols, text_rows = self._text_area_size()
        if (
            self._normal_buf.rows == text_rows
            and self._normal_buf.cols == text_cols
        ):
            return
        self._normal_buf.resize(text_rows, text_cols)
        self._alt_buf.resize(text_rows, text_cols)

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
            self._set_session_error(exc)
            return

        self._session = session

    def _set_session_error(self, exc):
        """Record a PTY/session error for one visible status line."""
        message = str(exc) or exc.__class__.__name__
        if message != self._session_error:
            self._session_error = message
            self._reported_session_error = False

    def _drain_pending_output(self):
        """Process one bounded output chunk without using curses APIs."""
        if not self._pending_output:
            return False
        to_process = self._pending_output[:self.MAX_OUTPUT_PER_FRAME]
        self._pending_output = self._pending_output[self.MAX_OUTPUT_PER_FRAME:]
        self._consume_output(to_process)
        return True

    def tick(self):
        """Poll and consume PTY output outside the render path."""
        changed = False
        self._ensure_session()
        text_cols, text_rows = self._text_area_size()
        if self._session is not None:
            try:
                size = (text_cols, text_rows)
                if size != self._last_pty_size:
                    self._session.resize(text_cols, text_rows)
                    self._last_pty_size = size
                flush_writes = getattr(self._session, 'flush_pending_writes', None)
                if callable(flush_writes):
                    flush_writes()
                chunk = self._session.read()
                if chunk:
                    self._pending_output += chunk
                    changed = True
                self._session.poll_exit()
            except (OSError, RuntimeError) as exc:
                self._set_session_error(exc)
        if self._session_error and not self._reported_session_error:
            self._pending_output += self._session_error + '\n'
            self._reported_session_error = True
            changed = True
        return self._drain_pending_output() or changed

    # OLD _strip_ansi removed, replaced by self.ansi usage

    def _write_char(self, ch, attr):
        """Write one character with attribute at current cursor via the buffer."""
        self._sync_screen_size()
        self._screen.put_char(ch, attr=attr)

    # _advance_alt_cursor used to be a vestigial helper kept for legacy
    # call sites; nothing references it any more, and the buffer's
    # ``put_char`` already wraps with a scroll if needed.

    def _append_newline(self):
        """Advance using LF+CR and let the buffer own scrollback capture.

        Rows are appended to history only when ``line_feed`` scrolls them off
        the top. A newline inside the visible grid merely moves the cursor and
        therefore cannot duplicate a row that is still present on screen.
        """
        self._screen.line_feed()
        self._screen.carriage_return()

    def _erase_line(self, mode):
        """Apply CSI K (erase in line) mode using the active buffer."""
        active = self._screen._active
        if mode == 2:
            active.clear_line()
            return
        if mode == 1:
            for c in range(0, active.cursor_col + 1):
                active._grid[active.cursor_row][c] = (" ", active._default_attr)
            return
        for c in range(active.cursor_col, active.cols):
            active._grid[active.cursor_row][c] = (" ", active._default_attr)

    def _erase_display(self, mode):
        """Apply CSI J (erase in display) for the active buffer."""
        active = self._screen._active
        if mode == 2:
            self._screen.clear_screen("all")
            self.scrollback_offset = 0
            return
        if mode == 1:
            self._screen.clear_screen("above")
            return
        self._screen.clear_screen("below")

    def _apply_csi(self, params, final):
        """Handle CSI controls for layout (attributes handled by AnsiStateMachine)."""
        def _num(index, default):
            if index >= len(params):
                return default
            return params[index]

        if final == 'h':
            mode = _num(0, 0)
            if mode in (1049, 1047, 47):
                self._alt_screen = True
            elif mode in _MOUSE_REPORT_MODES:
                self._mouse_modes.add(mode)
            return
        if final == 'l':
            mode = _num(0, 0)
            if mode in (1049, 1047, 47):
                self._alt_screen = False
            elif mode in _MOUSE_REPORT_MODES:
                self._mouse_modes.discard(mode)
            return

        active = self._screen._active
        rows, cols = active.rows, active.cols

        if final == 'A':
            active.set_cursor(max(0, active.cursor_row - max(1, _num(0, 1))), active.cursor_col)
            return
        if final == 'B':
            active.set_cursor(min(rows - 1, active.cursor_row + max(1, _num(0, 1))), active.cursor_col)
            return
        if final == 'D':
            active.set_cursor(active.cursor_row, max(0, active.cursor_col - max(1, _num(0, 1))))
            return
        if final == 'C':
            active.set_cursor(active.cursor_row, min(cols - 1, active.cursor_col + max(1, _num(0, 1))))
            return
        if final == 'G':
            active.set_cursor(active.cursor_row, min(cols - 1, max(0, _num(0, 1) - 1)))
            return
        if final in ('H', 'f'):
            row = max(0, min(rows - 1, _num(0, 1) - 1))
            col = max(0, min(cols - 1, _num(1, 1) - 1))
            active.set_cursor(row, col)
            return
        if final == 'K':
            self._erase_line(_num(0, 0))
            return
        if final == 'P':
            count = max(1, _num(0, 1))
            row = active.cursor_row
            col = active.cursor_col
            line = active._grid[row]
            if col < len(line):
                # Only consume characters that exist inside the row; pad
                # the rest so the row never grows past ``cols`` and the
                # ``TerminalScreenBuffer`` invariant stays intact.
                removable = min(count, max(0, len(line) - col))
                del line[col:col + removable]
                line.extend([(" ", active._default_attr)] * removable)
            return
        if final == 'J':
            self._erase_display(_num(0, 0))
            return

    def _consume_output(self, text):
        """Feed text to ANSI state machine and update buffer."""
        if not text:
            return

        self._sync_screen_size()

        prev_total = len(self._all_lines())
        prev_offset = self.scrollback_offset

        for kind, data, attr in self.ansi.parse_chunk(text):
            if kind == 'TEXT':
                self._write_char(data, attr)
            elif kind == 'CONTROL':
                if data == '\n':
                    self._append_newline()
                elif data == '\r':
                    self._screen.carriage_return()
                elif data == '\b':
                    self._screen.backspace()
                elif data == '\t':
                    spaces = 8 - (self._screen.cursor_col % 8)
                    for _ in range(spaces):
                        self._write_char(' ', self.ansi.attr)
            elif kind == 'CSI':
                # data is final char, attr is params list
                self._apply_csi(attr, data)

        if prev_offset > 0:
            new_total = len(self._all_lines())
            appended = max(0, new_total - prev_total)
            if appended > 0:
                _, text_rows = self._text_area_size()
                max_offset = self._max_scrollback_offset(text_rows)
                self.scrollback_offset = min(max_offset, prev_offset + appended)

    def _all_lines_count(self):
        """Return just the number of lines (avoids building the full list)."""
        if self._alt_screen:
            return self._screen._alt.rows
        return len(self._scrollback) + self._normal_buf.rows

    def _all_lines(self):
        """Return all lines including current editable line (as lists of cells)."""
        if self._alt_screen:
            return [self._screen._alt.get_row(r) for r in range(self._screen._alt.rows)]
        normal_rows = [self._normal_buf.get_row(r) for r in range(self._normal_buf.rows)]
        return list(self._scrollback) + normal_rows

    def _max_scrollback_offset(self, text_rows):
        return max(0, self._all_lines_count() - max(1, text_rows))

    def _visible_slice(self, text_rows):
        text_rows = max(1, text_rows)
        # Caller is expected to have already clamped ``scrollback_offset``
        # (typically via the caller that triggered this read). Keeping
        # the clamp here would re-write state from a pure read path.
        lines = self._all_lines()
        total = len(lines)
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

        active = self._screen._active
        cursor_line_idx = active.cursor_row
        col = active.cursor_col

        if self._alt_screen:
            row = y + cursor_line_idx
            if row >= y + text_rows:
                return
            if cursor_line_idx < active.rows:
                line = active.get_row(cursor_line_idx)
                if col < len(line):
                    ch, attr = line[col]
                else:
                    ch, attr = ' ', 0
            else:
                ch, attr = ' ', 0
        else:
            # In normal mode the cursor lives on the bottom row of the buffer;
            # map that to the position in ``total_lines`` (scrollback + buffer).
            buffer_first_line_idx = total_lines - active.rows
            line_idx = buffer_first_line_idx + cursor_line_idx
            if not (start_idx <= line_idx < start_idx + text_rows):
                return
            row = y + (line_idx - start_idx)
            line = active.get_row(cursor_line_idx)
            if col < len(line):
                ch, attr = line[col]
            else:
                ch, attr = ' ', 0

        if col >= text_cols:
            col = text_cols - 1

        effective_attr = attr if attr else body_attr

        if ch == ' ':
            safe_addstr(stdscr, row, x + col, '_', effective_attr | curses.A_BOLD)
            return

        safe_addstr(stdscr, row, x + col, ch, effective_attr | curses.A_REVERSE | curses.A_BOLD)

    def _draw_selection(self, stdscr, x, y, text_cols, start_idx, visible_lines, body_attr):
        """Draw reverse-video overlay for selected text (run-batched)."""
        if not self.has_selection():
            return
        for row, line_cells in enumerate(visible_lines):
            line_idx = start_idx + row
            span = self._line_selection_span(line_idx, len(line_cells))
            if not span:
                continue
            start, end = span
            start = max(0, start)
            end = min(end, text_cols)
            if end <= start:
                continue
            # Run-based batching: group consecutive cells with same attr
            first = line_cells[start] if start < len(line_cells) else (' ', 0)
            run_attr = (first[1] or body_attr) | curses.A_REVERSE | curses.A_BOLD
            run_start = start
            run_chars: list[str] = []
            for col in range(start, end):
                if col < len(line_cells):
                    ch, attr = line_cells[col]
                else:
                    ch, attr = ' ', 0
                effective = (attr or body_attr) | curses.A_REVERSE | curses.A_BOLD
                if effective != run_attr:
                    safe_addstr(stdscr, y + row, x + run_start, ''.join(run_chars), run_attr)
                    run_start = col
                    run_chars = [ch]
                    run_attr = effective
                else:
                    run_chars.append(ch)
            if run_chars:
                safe_addstr(stdscr, y + row, x + run_start, ''.join(run_chars), run_attr)

    def draw(self, stdscr):
        """Draw terminal body, live output, scrollback and status line."""
        if not self.visible:
            return

        _ = self.draw_frame(stdscr)
        body_attr = theme_attr('terminal') if self.active else theme_attr('window_inactive')
        bx, by, bw, bh = self.body_rect()
        text_cols, text_rows = max(1, bw - 1), max(1, bh - 1)

        # Clear background (reuse single blank string across rows).
        blank = ' ' * bw
        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, blank, body_attr)

        if getattr(self, '_alt_screen', False):
            # The alt-screen buffer owns its own row count. Resize once
            # when the viewport dimensions change; the previous
            # property-set/loop (O(rows²) per frame) walked every row
            # copying identical content every iteration.
            alt = self._screen._alt
            if alt.rows != text_rows or alt.cols != text_cols:
                alt.resize(text_rows, text_cols)
                # Re-initialise the resized grid with blank cells so
                # the alt screen is empty after a viewport change.
                blank_cell = (' ', alt._default_attr)
                for r in range(alt.rows):
                    alt._grid[r] = [blank_cell] * alt.cols

        # PTY output is consumed by ``tick`` so minimized windows continue
        # draining without entering the curses render path.

        visible, start_idx, total_lines = self._visible_slice(text_rows)

        # Render visible lines using run-based batching: group consecutive
        # cells with the same attribute into single safe_addstr calls.
        for i, line_cells in enumerate(visible):
            fitted = self._fit_line(line_cells, text_cols)
            if not fitted:
                continue
            run_start = 0
            run_chars = []
            run_attr = fitted[0][1] or body_attr
            for j, (ch, a) in enumerate(fitted):
                effective = a if a else body_attr
                if effective != run_attr:
                    safe_addstr(stdscr, by + i, bx + run_start, ''.join(run_chars), run_attr)
                    run_start = j
                    run_chars = [ch]
                    run_attr = effective
                else:
                    run_chars.append(ch)
            if run_chars:
                safe_addstr(stdscr, by + i, bx + run_start, ''.join(run_chars), run_attr)

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
        function_keys = {
            1: '\x1bOP',
            2: '\x1bOQ',
            3: '\x1bOR',
            4: '\x1bOS',
            5: '\x1b[15~',
            6: '\x1b[17~',
            7: '\x1b[18~',
            8: '\x1b[19~',
            9: '\x1b[20~',
            10: '\x1b[21~',
            11: '\x1b[23~',
            12: '\x1b[24~',
        }
        for number, sequence in function_keys.items():
            curses_key = getattr(curses, f'KEY_F{number}', None)
            if curses_key is not None:
                special[curses_key] = sequence
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
            self._scrollback.clear()
            self._normal_buf.clear_screen("all")
            self._alt_buf.clear_screen("all")
            self._screen.set_cursor(0, 0)
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
            self._session.write('\x03')
        except OSError as exc:
            self._session_error = str(exc)
            self._reported_session_error = False

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
            self._reported_session_error = False

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
            self._reported_session_error = False

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

        if key_code == 3:
            # Copy selected text on Ctrl+C; otherwise behave as terminal interrupt.
            if self.has_selection():
                self._copy_selection()
            else:
                self._send_interrupt()
            return None

        if key_code == getattr(curses, 'KEY_PPAGE', -1):
            if getattr(self, '_alt_screen', False):
                self._forward_payload(self._key_to_input(key, key_code))
                return None
            _, text_rows = self._text_area_size()
            self.handle_scroll('up', max(1, text_rows - 1))
            return None
        if key_code == getattr(curses, 'KEY_NPAGE', -1):
            if getattr(self, '_alt_screen', False):
                self._forward_payload(self._key_to_input(key, key_code))
                return None
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

        # Mouse pass-through: when the child has enabled any DEC mouse
        # reporting mode, encode the click as an SGR mouse sequence and
        # forward it to the PTY. RetroTUI's selection/window logic stays
        # out of the way so the TUI app receives the event.
        if bstate is not None and self._mouse_modes:
            forwarded = self._encode_mouse_event(mx, my, bstate, motion=False)
            if forwarded is not None:
                self._forward_payload(forwarded)
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
                    # Jump to live view so the user can see what they select.
                    self.scrollback_offset = 0
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
        # Mouse pass-through: forward motion events to the child when it's
        # in mouse reporting mode (SGR mode appends ``;Cx;CyM`` per move).
        if self._mouse_modes and (bstate & getattr(curses, 'BUTTON1_PRESSED', 0)):
            forwarded = self._encode_mouse_event(mx, my, bstate, motion=True)
            if forwarded is not None:
                self._forward_payload(forwarded)
                return None

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
        # Mouse pass-through: forward scroll wheel as a mouse-encoded event
        # when the child wants mouse (BUTTON4/5 → Cb 64/65 in SGR mode).
        if self._mouse_modes:
            if direction == 'up':
                self._forward_mouse_wheel('up')
                return
            if direction == 'down':
                self._forward_mouse_wheel('down')
                return

        count = max(1, steps)
        _, text_rows = self._text_area_size()
        max_offset = self._max_scrollback_offset(text_rows)
        if direction == 'up':
            self.scrollback_offset = min(max_offset, self.scrollback_offset + count)
        elif direction == 'down':
            self.scrollback_offset = max(0, self.scrollback_offset - count)

    # ------------------------------------------------------------------
    # Mouse pass-through helpers
    # ------------------------------------------------------------------

    def _mouse_body_position(self, mx, my):
        """Return (col, row) inside the terminal body, or ``None``."""
        bx, by, bw, bh = self.body_rect()
        text_cols, text_rows = max(1, bw - 1), max(1, bh - 1)
        if not (bx <= mx < bx + text_cols and by <= my < by + text_rows):
            return None
        col = max(0, min(text_cols, mx - bx))
        row = max(0, min(text_rows, my - by))
        return col, row

    def _encode_mouse_event(self, mx, my, bstate, *, motion=False):
        """Encode a mouse event as an SGR mouse escape sequence.

        Returns the bytes to send to the child, or ``None`` when the event
        should not be forwarded (e.g. pure motion without any button down
        when the child has only enabled press/release tracking).

        The SGR button codes follow xterm:
            0 = left, 1 = middle, 2 = right,
            32 = motion-without-button,
            32 + button = motion-with-button,
            64 = scroll up, 65 = scroll down.
        """
        pos = self._mouse_body_position(mx, my)
        if pos is None:
            return None
        col, row = pos

        b1 = getattr(curses, 'BUTTON1_PRESSED', 0)
        b1_clicked = getattr(curses, 'BUTTON1_CLICKED', 0)
        b1_double = getattr(curses, 'BUTTON1_DOUBLE_CLICKED', 0)
        b1_released = getattr(curses, 'BUTTON1_RELEASED', 0)
        b2 = getattr(curses, 'BUTTON2_PRESSED', 0)
        b3 = getattr(curses, 'BUTTON3_PRESSED', 0)

        cb = None
        suffix = "M"
        if bstate & b1:
            cb = 0
        elif bstate & b2:
            cb = 1
        elif bstate & b3:
            cb = 2
        elif bstate & (b1_clicked | b1_double):
            cb = 0
        elif bstate & b1_released:
            cb = 0
            suffix = "m"
        elif motion:
            # Pure motion (no button down): only when ?1003h is enabled.
            if 1003 in self._mouse_modes:
                cb = 32
            else:
                return None
        else:
            return None

        # Motion with a button held: only forward when ?1002h / ?1003h
        # explicitly enabled (1000/1006 alone = press/release only).
        if motion and cb in (0, 1, 2):
            if not (1002 in self._mouse_modes or 1003 in self._mouse_modes):
                return None
            cb += 32

        return f"\x1b[<{cb};{col + 1};{row + 1}{suffix}"

    def _forward_mouse_wheel(self, direction):
        """Forward a scroll-wheel tick as SGR button 64/65 (no coords)."""
        cb = 64 if direction == 'up' else 65
        self._forward_payload(f"\x1b[<{cb};1;1M")

    def restart_session(self):
        """Reset scrollback state and start a fresh shell session lazily."""
        if self.close() is False:
            return False
        self._session_error = None
        self._reported_session_error = False
        self._last_pty_size = None
        self._pending_output = ''
        self.ansi = AnsiStateMachine()
        self._scroll_lines = []
        self._normal_buf.clear_screen("all")
        self._alt_buf.clear_screen("all")
        self._screen.set_alt_screen(False)
        self._screen.set_cursor(0, 0)
        # The fresh child has not re-enabled mouse reporting yet.
        self._mouse_modes = set()
        self.scrollback_offset = 0
        return True

    def close(self):
        """Release PTY resources only after the child is verified stopped."""
        session = self._session
        if session is not None:
            if session.close() is False:
                self._set_session_error(
                    RuntimeError("Terminal child is still alive; close was cancelled.")
                )
                return False
            self._session = None
        self._pending_output = ''
        self._last_pty_size = None
        return True

"""
Notepad Application.
"""
import curses
import os
import unicodedata
from ..ui.selectable_text import SelectableTextMixin
from ..ui.window import Window
from ..ui.menu import WindowMenu
from ..core.actions import ActionResult, ActionType, AppAction, SaveConfirmPayload
from ..core.clipboard import copy_text, paste_text
from ..utils import safe_addstr, normalize_key_code, theme_attr
from ..constants import C_STATUS, C_SCROLLBAR, WIN_MIN_WIDTH


def _cell_width(ch):
    """Return terminal cell width for one character."""
    if not ch:
        return 0
    if unicodedata.combining(ch):
        return 0
    if unicodedata.east_asian_width(ch) in ('W', 'F'):
        return 2
    return 1


def _text_cell_width(text):
    return sum(_cell_width(ch) for ch in text)


def _fit_text_to_cells(text, max_cells):
    if max_cells <= 0:
        return ''
    out = []
    used = 0
    for ch in text:
        width = _cell_width(ch)
        if used + width > max_cells:
            break
        out.append(ch)
        used += width
    return ''.join(out)


def _cell_offset_for_col(text, char_col):
    """Return display-cell offset for a character index."""
    char_col = max(0, min(char_col, len(text)))
    return _text_cell_width(text[:char_col])


def _char_col_for_cell_offset(text, cell_offset):
    """Return nearest character index for a display-cell offset."""
    target = max(0, int(cell_offset))
    used = 0
    for pos, ch in enumerate(text):
        width = _cell_width(ch)
        if used + width > target:
            return pos
        used += width
    return len(text)


def _wrap_line_to_cells(buf_line_idx, line, wrap_w):
    """Return wrapped chunks as (line index, char start, text)."""
    if not line:
        return [(buf_line_idx, 0, '')]
    if wrap_w <= 0 or _text_cell_width(line) <= wrap_w:
        return [(buf_line_idx, 0, line)]

    chunks = []
    start = 0
    used = 0
    for pos, ch in enumerate(line):
        width = _cell_width(ch)
        if used > 0 and used + width > wrap_w:
            chunks.append((buf_line_idx, start, line[start:pos]))
            start = pos
            used = 0
        used += width
        if width >= wrap_w:
            chunks.append((buf_line_idx, start, line[start:pos + 1]))
            start = pos + 1
            used = 0
    if start < len(line):
        chunks.append((buf_line_idx, start, line[start:]))
    return chunks


class NotepadWindow(SelectableTextMixin, Window):
    """Editable text editor window with word wrap support."""

    KEY_F6 = getattr(curses, 'KEY_F6', -1)
    KEY_INSERT = getattr(curses, 'KEY_IC', -1)
    UNDO_MAX_STATES = 100
    UNDO_MAX_CHARS = 1_000_000

    def __init__(self, x, y, w, h, filepath=None, wrap_default=False):
        title = 'Notepad'
        # Defensive clamp on both dimensions so direct callers (tests,
        # programmatic use) can't shrink the window below the safe
        # render minimum. Action-runner already clamps before spawning
        # (see action_runner._spawn_registered_app), so this only matters
        # for callers that bypass that path.
        super().__init__(title, x, y, max(WIN_MIN_WIDTH, w), max(8, h), content=[])
        self.buffer = ['']  # list[str] — one string per logical line
        self.filepath = filepath
        self.modified = False
        self._title_cache_key = None
        self.cursor_line = 0
        self.cursor_col = 0
        self.view_top = 0    # First visible line in buffer
        self.view_left = 0   # Horizontal scroll offset
        self.wrap_mode = bool(wrap_default)
        self._undo_stack = []
        self._redo_stack = []
        self._search_mode = False
        self._search_query = ''
        self._force_close = False
        self._close_confirm_pending = False
        self._open_path_confirm_pending = None
        # Per-line wrap cache: ``self._wrap_line_cache[i]`` holds the
        # wrapped chunks for ``self.buffer[i]`` (or ``None`` when
        # stale). The list always has the same length as
        # ``self.buffer`` so insert/delete keeps the indices in sync.
        # ``self._wrap_cache_w`` tracks the wrap width; any width
        # change invalidates the whole cache.
        self._wrap_line_cache = []
        self._wrap_cache_w = None
        self._init_selection()
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
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._force_close = False
        self._close_confirm_pending = False
        self._open_path_confirm_pending = None
        # Whole buffer was replaced; reset the per-line cache list.
        self._wrap_line_cache = [None] * len(self.buffer)
        self._wrap_cache_w = None
        self._update_title()

    def _save_file(self):
        """Save buffer to file. Returns True or ActionResult."""
        if not self.filepath:
            return ActionResult(ActionType.REQUEST_SAVE_AS)
        try:
            from ..utils import atomic_write_text
            atomic_write_text(
                self.filepath,
                '\n'.join(self.buffer),
                encoding='utf-8',
            )
        except (PermissionError, OSError) as e:
            return ActionResult(ActionType.SAVE_ERROR, str(e))
        self.modified = False
        self._force_close = False
        self._close_confirm_pending = False
        self._update_title()
        return True

    def save_as(self, filepath):
        """Set filepath and save."""
        self.filepath = filepath
        result = self._save_file()
        self._update_title()
        return result

    def _update_title(self):
        """Refresh the title only when filepath or modified state changes."""
        key = (self.filepath, self.modified)
        if key == self._title_cache_key:
            return
        if self.filepath:
            filename = os.path.basename(self.filepath)
            prefix = '* ' if self.modified else ''
            self.title = f'Notepad - {prefix}{filename}'
        elif self.modified:
            self.title = 'Notepad *'
        else:
            self.title = 'Notepad'
        self._title_cache_key = key

    def open_path(self, filepath):
        """Load a file path into current notepad buffer."""
        path = (filepath or '').strip()
        if not path:
            return None
        # Guard against silently destroying unsaved work when another
        # window or dialog calls ``open_path`` on us. Force-close (during
        # app shutdown, terminal reset, etc.) bypasses the prompt.
        if self.modified and not self._force_close and not self._open_path_confirm_pending:
            self._open_path_confirm_pending = (
                os.path.abspath(os.path.expanduser(path))
            )
            return ActionResult(
                ActionType.REQUEST_SAVE_CONFIRM,
                payload=SaveConfirmPayload(
                    on_discard=self._do_open_path_force,
                    on_cancel=self._cancel_open_path,
                    message=(
                        f"{self.title} has unsaved changes.\n"
                        "Discard them and open the new file?"
                    ),
                ),
            )
        self._do_open_path(os.path.abspath(os.path.expanduser(path)))
        return None

    def _do_open_path(self, path):
        self._open_path_confirm_pending = None
        self._load_file(path)
        self.clear_selection()

    def _do_open_path_force(self):
        """Discard current buffer and open the pending path."""
        pending = self._open_path_confirm_pending
        self._open_path_confirm_pending = None
        if pending:
            self._do_open_path(pending)

    def _cancel_open_path(self):
        """Cancel a pending destructive open request."""
        self._open_path_confirm_pending = None

    def request_close(self):
        """Return a confirmation request when the buffer is modified."""
        if not self.modified or self._force_close:
            return True
        if self._close_confirm_pending:
            return False
        self._close_confirm_pending = True
        return ActionResult(
            ActionType.REQUEST_SAVE_CONFIRM,
            payload=SaveConfirmPayload(
                on_discard=self._confirm_close,
                on_cancel=self._cancel_close_request,
                message=(
                    f"{self.title} has unsaved changes.\n"
                    "Discard them and close the window?"
                ),
            ),
        )

    def _confirm_close(self):
        self._close_confirm_pending = False
        self._force_close = True
        return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)

    def _cancel_close_request(self):
        self._close_confirm_pending = False


    def _invalidate_wrap(self, line_idx=None):
        """Invalidate cached wrapped line data.

        ``line_idx`` marks a single line dirty (cheap; only that line
        is recomputed on the next draw). Without ``line_idx`` the entire
        cache is marked dirty — used for width changes.
        """
        if (
            line_idx is not None
            and 0 <= line_idx < len(self._wrap_line_cache)
        ):
            self._wrap_line_cache[line_idx] = None
        else:
            for i in range(len(self._wrap_line_cache)):
                self._wrap_line_cache[i] = None

    def _sync_wrap_cache_to_buffer(self):
        """Reconcile the per-line wrap cache with ``self.buffer`` length.

        Called after ``insert``/``pop`` on the buffer. The cache list
        is grown with ``None`` entries for new lines and shrunk to
        match the shorter buffer. Lines whose index changed (because
        of an insert/delete) are marked dirty so their ``line_idx``
        field is re-baked on the next compute pass.
        """
        n = len(self.buffer)
        cur = len(self._wrap_line_cache)
        if cur == n:
            return
        if cur < n:
            # Lines were added; the new range is dirty.
            self._wrap_line_cache.extend([None] * (n - cur))
        else:
            # Lines were removed. Drop the tail entries; for any line
            # at index ``>= n`` that previously stored chunks, the
            # ``line_idx`` baked into each chunk now disagrees with its
            # real buffer position. Mark all surviving entries dirty
            # because the per-line cache list is now shorter and any
            # previously-valid ``line_idx`` past the deletion point has
            # shifted; recomputing is the safe path.
            del self._wrap_line_cache[n:]
            for i in range(len(self._wrap_line_cache)):
                self._wrap_line_cache[i] = None

    def _compute_wrap(self, body_w):
        """Build wrapped-line cache for compatibility and tests.

        Iterates the buffer once and uses the per-line cache. Only
        the lines marked ``None`` (stale) are recomputed; the rest are
        O(1) lookups. The result is a flat list of chunks preserving
        the line index, suitable for the existing cursor/scroll math.
        """
        wrap_w = max(1, int(body_w) - 1)
        # The cache is anchored to a wrap width. A width change requires
        # invalidating every line (the per-line chunks depend on width).
        if self._wrap_cache_w != body_w:
            self._invalidate_wrap()
            self._wrap_cache_w = body_w
        chunks = []
        for idx, line in enumerate(self.buffer):
            cached = (
                self._wrap_line_cache[idx]
                if idx < len(self._wrap_line_cache)
                else None
            )
            if cached is None:
                cached = _wrap_line_to_cells(idx, line, wrap_w)
                if idx < len(self._wrap_line_cache):
                    self._wrap_line_cache[idx] = cached
                else:
                    # ``buffer`` was grown without a sync call (defensive).
                    while len(self._wrap_line_cache) <= idx:
                        self._wrap_line_cache.append(None)
                    self._wrap_line_cache[idx] = cached
            chunks.extend(cached)
        return chunks

    def _cursor_to_wrap_row(self, body_w):
        """Return wrapped row index containing the cursor."""
        if not self.wrap_mode:
            return max(0, min(self.cursor_line, len(self.buffer) - 1))
        if not (0 <= self.cursor_line < len(self.buffer)):
            return 0
        chunks = self._compute_wrap(body_w)
        fallback = 0
        for idx, (line_idx, start_col, text) in enumerate(chunks):
            if line_idx != self.cursor_line:
                continue
            fallback = idx
            end_col = start_col + len(text)
            if start_col <= self.cursor_col <= end_col:
                return idx
        return fallback

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

    def _buffer_char_count(self, buffer=None):
        """Return approximate buffer size used for undo pressure limits."""
        target = self.buffer if buffer is None else buffer
        return sum(len(line) + 1 for line in target)

    def _state_for_undo(self, clear_history=True):
        """Build an undo state unless the current buffer is too large to copy."""
        if self._buffer_char_count() > self.UNDO_MAX_CHARS:
            if clear_history:
                self._undo_stack.clear()
                self._redo_stack.clear()
            return None
        return {
            'buffer': self.buffer.copy(),
            'cursor_line': self.cursor_line,
            'cursor_col': self.cursor_col,
            'modified': self.modified
        }

    def _trim_history_stack(self, stack):
        """Keep undo/redo history within state-count and character budgets."""
        total = sum(self._buffer_char_count(state['buffer']) for state in stack)
        while stack and (len(stack) > self.UNDO_MAX_STATES or total > self.UNDO_MAX_CHARS):
            removed = stack.pop(0)
            total -= self._buffer_char_count(removed['buffer'])

    def _push_undo(self):
        self._force_close = False
        self._close_confirm_pending = False
        state = self._state_for_undo()
        if state is None:
            return
        self._undo_stack.append(state)
        self._redo_stack.clear()
        self._trim_history_stack(self._undo_stack)

    def undo(self):
        if not self._undo_stack: return None
        redo_state = self._state_for_undo(clear_history=False)
        if redo_state is not None:
            self._redo_stack.append(redo_state)
            self._trim_history_stack(self._redo_stack)
        state = self._undo_stack.pop()
        self.buffer = state['buffer']
        self.cursor_line = state['cursor_line']
        self.cursor_col = state['cursor_col']
        self.modified = state['modified']
        # ``buffer`` is a fresh list; rebuild the per-line cache list
        # so the indices match the new content. (Mark all dirty so
        # the next draw recomputes from scratch.)
        self._wrap_line_cache = [None] * len(self.buffer)
        self._ensure_cursor_visible()
        return None

    def redo(self):
        if not self._redo_stack: return None
        undo_state = self._state_for_undo(clear_history=False)
        if undo_state is not None:
            self._undo_stack.append(undo_state)
            self._trim_history_stack(self._undo_stack)
        state = self._redo_stack.pop()
        self.buffer = state['buffer']
        self.cursor_line = state['cursor_line']
        self.cursor_col = state['cursor_col']
        self.modified = state['modified']
        # ``buffer`` is a fresh list; rebuild the per-line cache list
        # so the indices match the new content.
        self._wrap_line_cache = [None] * len(self.buffer)
        self._ensure_cursor_visible()
        return None

    def _delete_selection(self):
        """Delete current selection and place cursor at selection start.

        Callers are responsible for ``_push_undo()`` *before* invoking
        this so a selection-replace operation produces a single undo
        entry. The methods that need that behaviour are
        ``_key_backspace``/``_key_delete``/``_key_enter``/
        ``_key_printable``/``_key_paste``/``_handle_cut_selection``.
        """
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
        # Selection delete can shrink the buffer by many lines. Sync
        # the per-line cache list to the new length; the surviving
        # line at ``s_line`` now has different content, so it's marked
        # dirty explicitly. Other surviving lines keep their cached
        # chunks (chunk counts shift by the deleted line count, but
        # the line_idx we cached is correct relative to the truncated
        # list — recomputation on the next draw handles the renumbering
        # when the wrapper inserts the live index).
        self._invalidate_wrap(s_line)
        self._sync_wrap_cache_to_buffer()
        self.clear_selection()
        self._ensure_cursor_visible()
        return True

    def _cut_current_line(self):
        """Cut current line to clipboard."""
        if not (0 <= self.cursor_line < len(self.buffer)):
            return

        self._push_undo()
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
        # ``cursor_line`` points to the line that lost content; the
        # truncated list is reconciled by ``_sync_wrap_cache_to_buffer``.
        self._invalidate_wrap(self.cursor_line)
        self._sync_wrap_cache_to_buffer()
        self.clear_selection()
        self._ensure_cursor_visible()

    def _get_wrapped_lines_for(self, buf_line_idx, wrap_w):
        line = self.buffer[buf_line_idx]
        if not self.wrap_mode:
            return [(buf_line_idx, 0, line)]
        return _wrap_line_to_cells(buf_line_idx, line, wrap_w)

    def _get_visible_wrapped_chunks(self, start_logical, max_chunks, wrap_w):
        if self.wrap_mode:
            chunks = self._compute_wrap(wrap_w + 1)
        else:
            chunks = [(i, 0, line) for i, line in enumerate(self.buffer)]
        return chunks[start_logical:start_logical + max_chunks]

    def _ensure_cursor_visible(self):
        """Auto-scroll viewport to keep cursor visible."""
        bx, by, bw, bh = self.body_rect()
        body_h = bh - 1  # -1 for status bar row

        if self.wrap_mode:
            cursor_row = self._cursor_to_wrap_row(bw)
            if cursor_row < self.view_top:
                self.view_top = cursor_row
            elif cursor_row >= self.view_top + body_h:
                self.view_top = cursor_row - body_h + 1
            self.view_left = 0
            return

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

        self._push_undo()
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
        # Multi-line insert: invalidate everything and sync. Re-baking
        # the per-line chunks for subsequent lines would otherwise be
        # needed because their ``line_idx`` field would now disagree
        # with the new buffer index.
        self._invalidate_wrap()
        self._sync_wrap_cache_to_buffer()
        self._ensure_cursor_visible()

    def _set_cursor_from_screen(self, mx, my):
        """Place cursor using screen coordinates inside body area."""
        bx, by, bw, _ = self.body_rect()
        row_in_view = my - by
        col_in_view = mx - bx

        if self.wrap_mode:
            wrap_w = max(1, bw - 1)
            chunks = self._get_visible_wrapped_chunks(self.view_top, row_in_view + 1, wrap_w)
            if row_in_view < len(chunks):
                buf_line, start_col, _ = chunks[row_in_view]
                self.cursor_line = buf_line
                chunk_text = self.buffer[buf_line][start_col:]
                self.cursor_col = min(
                    start_col + _char_col_for_cell_offset(chunk_text, col_in_view),
                    len(self.buffer[buf_line]),
                )
            else:
                self.cursor_line = len(self.buffer) - 1
                self.cursor_col = len(self.buffer[self.cursor_line])
        else:
            target_line = self.view_top + row_in_view
            if target_line < len(self.buffer):
                self.cursor_line = target_line
                visible_text = self.buffer[target_line][self.view_left:]
                self.cursor_col = min(
                    self.view_left + _char_col_for_cell_offset(visible_text, col_in_view),
                    len(self.buffer[target_line]),
                )
            else:
                self.cursor_line = len(self.buffer) - 1
                self.cursor_col = len(self.buffer[self.cursor_line])
        self._clamp_cursor()

    def draw(self, stdscr):
        """Draw notepad with buffer, cursor, and status bar."""
        if not self.visible:
            return

        self._update_title()

        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        body_h = bh - 1  # Last row is status bar

        # Body background
        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, ' ' * bw, body_attr)

        if self.wrap_mode:
            wrap_w = max(1, bw - 1)
            visible = self._get_visible_wrapped_chunks(self.view_top, body_h, wrap_w)

            for i, (buf_line, start_col, text) in enumerate(visible):
                display = _fit_text_to_cells(text, bw - 1)
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
                if buf_line == self.cursor_line and start_col <= self.cursor_col <= start_col + len(text):
                    rel_col = self.cursor_col - start_col
                    cx = _cell_offset_for_col(text, rel_col)
                    if 0 <= cx < bw - 1:
                        ch = text[rel_col] if rel_col < len(text) else ' '
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
                    visible_prefix = line[self.view_left:self.cursor_col]
                    cx = _text_cell_width(visible_prefix)
                    if 0 <= cx < col_w:
                        ch = line[self.cursor_col] if self.cursor_col < len(line) else ' '
                        safe_addstr(stdscr, by + i, bx + cx, ch, body_attr | curses.A_REVERSE)

        # Scrollbar
        total_lines = len(self.buffer)
        if total_lines > body_h and body_h > 1:
            sb_x = bx + bw - 1
            thumb_pos = int(self.view_top / max(1, total_lines - body_h) * (body_h - 1))
            for i in range(body_h):
                ch = '█' if i == thumb_pos else '░'
                safe_addstr(stdscr, by + i, sb_x, ch, theme_attr('scrollbar'))

        # Status bar (inside window, last body row)
        status_y = by + bh - 1
        if getattr(self, '_search_mode', False):
            status = f' Search: {getattr(self, "_search_query", "")}_'
            safe_addstr(stdscr, status_y, bx, status.ljust(bw)[:bw], theme_attr('status') | curses.A_REVERSE)
        else:
            mod_flag = ' [Modified]' if self.modified else ''
            wrap_flag = ' WRAP' if self.wrap_mode else ''
            status = f' Ln {self.cursor_line + 1}, Col {self.cursor_col + 1}{wrap_flag}{mod_flag}'
            safe_addstr(stdscr, status_y, bx, status.ljust(bw)[:bw], theme_attr('status'))

        # Window menu dropdown (on top of body content)
        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def _draw_selection_span(self, stdscr, screen_y, body_x, body_w, line_text, start_col, span, sel_attr):
        """Draw selection highlight for a span on one screen line (batched)."""
        if span is None:
            return
        sel_start, sel_end = span
        # Clamp to visible body area
        vis_start = max(sel_start - start_col, 0)
        vis_end = min(sel_end - start_col, body_w - 1)
        if vis_end <= vis_start:
            return
        abs_start = start_col + vis_start
        abs_end = start_col + vis_end
        text_slice = line_text[abs_start:abs_end]
        pad = vis_end - vis_start - len(text_slice)
        if pad > 0:
            text_slice += ' ' * pad
        safe_addstr(stdscr, screen_y, body_x + vis_start, text_slice, sel_attr)

    def execute_action(self, action):
        """Execute a window menu action. Returns signal or None."""
        if action == AppAction.NP_TOGGLE_WRAP:
            return self._toggle_wrap()
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

    # -- Key handler methods (dispatch targets) --

    def _toggle_wrap(self):
        """Toggle word wrap mode. Returns ActionResult for config update."""
        self.wrap_mode = not self.wrap_mode
        self.view_left = 0
        self._invalidate_wrap()
        self._ensure_cursor_visible()
        return ActionResult(ActionType.UPDATE_CONFIG, {'word_wrap_default': self.wrap_mode})

    def _key_escape(self):
        self.clear_selection()
        return None

    def _key_select_all(self):
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

    def _key_copy(self):
        if self.has_selection():
            selected = self._selected_text()
            if selected:
                copy_text(selected)
        else:
            if self.buffer and self.cursor_line < len(self.buffer):
                copy_text(self.buffer[self.cursor_line])
        return None

    def _key_cut(self):
        if self.has_selection():
            selected = self._selected_text()
            if selected:
                copy_text(selected)
            self._delete_selection()
        else:
            self._cut_current_line()
        return None

    def _key_nav_up(self):
        self.clear_selection()
        if self.cursor_line > 0:
            self.cursor_line -= 1
            self._clamp_cursor()
            self._ensure_cursor_visible()
        return None

    def _key_nav_down(self):
        self.clear_selection()
        if self.cursor_line < len(self.buffer) - 1:
            self.cursor_line += 1
            self._clamp_cursor()
            self._ensure_cursor_visible()
        return None

    def _key_nav_left(self):
        self.clear_selection()
        if self.cursor_col > 0:
            self.cursor_col -= 1
        elif self.cursor_line > 0:
            self.cursor_line -= 1
            self.cursor_col = len(self.buffer[self.cursor_line])
        self._ensure_cursor_visible()
        return None

    def _key_nav_right(self):
        self.clear_selection()
        line = self.buffer[self.cursor_line]
        if self.cursor_col < len(line):
            self.cursor_col += 1
        elif self.cursor_line < len(self.buffer) - 1:
            self.cursor_line += 1
            self.cursor_col = 0
        self._ensure_cursor_visible()
        return None

    def _key_nav_home(self):
        self.clear_selection()
        self.cursor_col = 0
        self._ensure_cursor_visible()
        return None

    def _key_nav_end(self):
        self.clear_selection()
        self.cursor_col = len(self.buffer[self.cursor_line])
        self._ensure_cursor_visible()
        return None

    def _key_nav_pgup(self):
        self.clear_selection()
        _, _, _, bh = self.body_rect()
        self.cursor_line = max(0, self.cursor_line - (bh - 2))
        self._clamp_cursor()
        self._ensure_cursor_visible()
        return None

    def _key_nav_pgdn(self):
        self.clear_selection()
        _, _, _, bh = self.body_rect()
        self.cursor_line = min(len(self.buffer) - 1, self.cursor_line + (bh - 2))
        self._clamp_cursor()
        self._ensure_cursor_visible()
        return None

    def _key_enter(self):
        self._push_undo()
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
        # Enter splits a line: the head and the new line are both
        # dirty, and the buffer length changed.
        self._invalidate_wrap()
        self._sync_wrap_cache_to_buffer()
        self._ensure_cursor_visible()
        return None

    def _key_backspace(self):
        self._push_undo()
        if self.has_selection():
            self._delete_selection()
        elif self.cursor_col > 0:
            line = self.buffer[self.cursor_line]
            self.buffer[self.cursor_line] = line[:self.cursor_col - 1] + line[self.cursor_col:]
            self.cursor_col -= 1
            self.modified = True
            # Single-line text edit: only the current line is dirty.
            self._invalidate_wrap(self.cursor_line)
        elif self.cursor_line > 0:
            # Merge with previous line
            prev_line = self.buffer[self.cursor_line - 1]
            self.cursor_col = len(prev_line)
            self.buffer[self.cursor_line - 1] = prev_line + self.buffer[self.cursor_line]
            self.buffer.pop(self.cursor_line)
            self.cursor_line -= 1
        self.modified = True
        # Either path: sync the cache list (merge changed the length;
        # backspace-within-line didn't but the call is cheap).
        self._sync_wrap_cache_to_buffer()
        self._ensure_cursor_visible()
        return None

    def _key_delete(self):
        self._push_undo()
        if self.has_selection():
            self._delete_selection()
        else:
            self.clear_selection()
            line = self.buffer[self.cursor_line]
            if self.cursor_col < len(line):
                self.buffer[self.cursor_line] = line[:self.cursor_col] + line[self.cursor_col + 1:]
                self.modified = True
                # Single-line text edit: only the current line is dirty.
                self._invalidate_wrap(self.cursor_line)
            elif self.cursor_line < len(self.buffer) - 1:
                # Merge with next line
                self.buffer[self.cursor_line] = line + self.buffer[self.cursor_line + 1]
                self.buffer.pop(self.cursor_line + 1)
                self.modified = True
        # Either path: sync the cache list (merge changed the length;
        # delete-within-line didn't but the call is cheap).
        self._sync_wrap_cache_to_buffer()
        return None

    def _key_open(self):
        return ActionResult(ActionType.REQUEST_OPEN_PATH)

    def _key_save(self):
        result = self._save_file()
        if result is not True:
            return result
        return None

    def _key_copy_line(self):
        text = self._selected_text()
        if text:
            copy_text(text)
        elif 0 <= self.cursor_line < len(self.buffer):
            copy_text(self.buffer[self.cursor_line])
        return None

    def _key_paste(self):
        if self.has_selection():
            self._delete_selection()
        self._insert_text(paste_text())
        return None

    def _key_toggle_wrap(self):
        self.clear_selection()
        return self._toggle_wrap()

    def _key_printable(self, ch):
        self._push_undo()
        if self.has_selection():
            self._delete_selection()
        else:
            self.clear_selection()
        line = self.buffer[self.cursor_line]
        self.buffer[self.cursor_line] = line[:self.cursor_col] + ch + line[self.cursor_col:]
        self.cursor_col += 1
        self.modified = True
        # Single-character insert: only the current line is dirty.
        self._invalidate_wrap(self.cursor_line)
        self._ensure_cursor_visible()
        return None

    def _key_search(self):
        self._search_mode = True
        self._search_query = ''
        return None

    def _execute_search(self):
        self._search_mode = False
        if not self._search_query: return
        q = self._search_query.lower()
        for i in range(self.cursor_line, len(self.buffer)):
            idx = self.buffer[i].lower().find(q, self.cursor_col + 1 if i == self.cursor_line else 0)
            if idx != -1:
                self.cursor_line = i
                self.cursor_col = idx
                self._ensure_cursor_visible()
                return
        for i in range(0, self.cursor_line + 1):
            idx = self.buffer[i].lower().find(q)
            if idx != -1:
                self.cursor_line = i
                self.cursor_col = idx
                self._ensure_cursor_visible()
                return

    # -- Dispatch table mapping key codes to handler method names --

    _KEY_DISPATCH = {
        27: '_key_escape',
        1: '_key_select_all',
        3: '_key_copy',
        24: '_key_cut',
        curses.KEY_UP: '_key_nav_up',
        curses.KEY_DOWN: '_key_nav_down',
        curses.KEY_LEFT: '_key_nav_left',
        curses.KEY_RIGHT: '_key_nav_right',
        curses.KEY_HOME: '_key_nav_home',
        curses.KEY_END: '_key_nav_end',
        curses.KEY_PPAGE: '_key_nav_pgup',
        curses.KEY_NPAGE: '_key_nav_pgdn',
        curses.KEY_ENTER: '_key_enter',
        10: '_key_enter',
        13: '_key_enter',
        curses.KEY_BACKSPACE: '_key_backspace',
        127: '_key_backspace',
        8: '_key_backspace',
        curses.KEY_DC: '_key_delete',
        15: '_key_open',
        19: '_key_save',
        25: 'redo',
        26: 'undo',
        6: '_key_search',
        KEY_F6: '_key_copy_line',
        KEY_INSERT: '_key_copy_line',
        22: '_key_paste',
        23: '_key_toggle_wrap',
    }

    def handle_key(self, key):
        """Handle keyboard input for the editor. Returns None or ActionResult."""
        key_code = normalize_key_code(key)
        if key_code is None:
            return None

        if getattr(self, '_search_mode', False):
            if key_code == 27:
                self._search_mode = False
            elif key_code in (10, 13, curses.KEY_ENTER):
                self._execute_search()
            elif key_code in (8, 127, curses.KEY_BACKSPACE):
                self._search_query = self._search_query[:-1]
            else:
                ch = key if isinstance(key, str) else chr(key) if isinstance(key, int) and 32 <= key <= 126 else None
                if ch and ch.isprintable():
                    self._search_query += ch
            return ActionResult(ActionType.REFRESH)

        # Window menu intercept
        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            return self.execute_action(action) if action else None

        # Dispatch table lookup
        handler_name = self._KEY_DISPATCH.get(key_code)
        if handler_name:
            return getattr(self, handler_name)()

        # Printable characters (unified)
        ch = key if isinstance(key, str) else chr(key) if isinstance(key, int) and 32 <= key <= 126 else None
        if ch and ch.isprintable() and ch not in ('\n', '\r', '\t'):
            return self._key_printable(ch)

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
            has_button1 = bool(
                bstate
                and (
                    bstate & curses.BUTTON1_PRESSED
                    or bstate & curses.BUTTON1_CLICKED
                    or bstate & curses.BUTTON1_DOUBLE_CLICKED
                )
            )
            if has_button1:
                self.clear_selection()
            else:
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

    def _context_menu_items(self):
        """Build context menu items for current cursor/selection state."""
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
             # Update Copy/Cut to work on selection if it exists.
             # Push undo *before* the cut so a single Undo restores the
             # selection (otherwise ``_delete_selection`` no longer
             # pushes and a single cut would be silently un-undoable).
             items[0] = {'label': 'Cut Selection', 'action': lambda: (copy_text(self._selected_text()), self._push_undo() or self._delete_selection())}
             items[1] = {'label': 'Copy Selection', 'action': lambda: copy_text(self._selected_text())}

        return items

    def handle_right_click(self, mx, my, bstate):
        """Handle right-click: show context menu."""
        bx, by, bw, bh = self.body_rect()
        if not (bx <= mx < bx + bw and by <= my < by + bh):
             return False

        self._set_cursor_from_screen(mx, my)
        self._ensure_cursor_visible()
        return self._context_menu_items()

    def get_context_menu_items(self, mx=None, my=None, bstate=None):
        """Return context menu items for compatibility callers."""
        if mx is not None and my is not None:
            return self.handle_right_click(mx, my, bstate)
        return self._context_menu_items()


    def scroll_up(self):
        """Scroll viewport up (for scroll wheel)."""
        if self.view_top > 0:
            self.view_top -= 1

    def scroll_down(self):
        """Scroll viewport down (for scroll wheel)."""
        _, _, bw, bh = self.body_rect()
        body_h = bh - 1
        if self.wrap_mode:
            max_top = max(0, len(self._compute_wrap(bw)) - body_h)
        else:
            max_top = max(0, len(self.buffer) - body_h)
        if self.view_top < max_top:
            self.view_top += 1

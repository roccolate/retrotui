"""Log Viewer application with tail mode, severity highlighting and search."""

import curses
import os
import time

from ..core.actions import ActionResult, ActionType, AppAction
from ..core.clipboard import copy_text
from ..ui.menu import WindowMenu
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr


class LogViewerWindow(Window):
    """Read-only log viewer with follow mode and vim-like search."""

    MAX_LINES = 5000
    READ_TAIL_BYTES = 512 * 1024
    POLL_INTERVAL_SECONDS = 0.4
    COLOR_ERROR_PAIR = 60
    COLOR_WARN_PAIR = 61
    COLOR_INFO_PAIR = 62
    _log_colors_ready = False

    def __init__(self, x, y, w, h, filepath=None):
        super().__init__("Log Viewer", x, y, w, h, content=[])
        self.filepath = None
        self.lines = []
        self.file_position = 0
        self._tail_remainder = ""
        self._error_message = None
        self._last_poll = 0.0

        self.follow_mode = True
        self.freeze_scroll = False

        self.search_query = ""
        self.search_matches = []
        self.search_index = -1
        self.search_input_mode = False
        self.search_input = ""
        self.selection_anchor = None  # (line_idx, col)
        self.selection_cursor = None  # (line_idx, col)
        self._mouse_selecting = False

        self.window_menu = WindowMenu(
            {
                "File": [
                    ("Open Path...   O", "lv_open"),
                    ("Reload         R", "lv_reload"),
                    ("-------------", None),
                    ("Close          Q", "lv_close"),
                ],
                "View": [
                    ("Follow Tail    F", "lv_follow"),
                    ("Freeze Scroll  Space", "lv_freeze"),
                    ("Copy Selection F6", "lv_copy"),
                    ("Search           /", "lv_search"),
                    ("Next Match       n", "lv_next"),
                    ("Prev Match       N", "lv_prev"),
                ],
            }
        )
        self.h = max(self.h, 10)

        if filepath:
            self.open_path(filepath)

    def clear_selection(self):
        """Clear line/column selection state."""
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
        """Return ordered ((line,col),(line,col)) bounds or None."""
        if not self.has_selection():
            return None
        a = self.selection_anchor
        b = self.selection_cursor
        return (a, b) if a <= b else (b, a)

    def _line_selection_span(self, line_idx, line_len):
        """Return [start,end) selection span for one line, or None."""
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
            if line_len <= start:
                return None
            return (start, line_len)
        if line_idx == end_line:
            end = max(0, min(line_len, end_col))
            if end <= 0:
                return None
            return (0, end)
        return (0, line_len)

    def _selected_text(self):
        """Return selected text as plain string."""
        bounds = self._selection_bounds()
        if not bounds or not self.lines:
            return ""
        (start_line, start_col), (end_line, end_col) = bounds
        start_line = max(0, min(start_line, len(self.lines) - 1))
        end_line = max(0, min(end_line, len(self.lines) - 1))
        if end_line < start_line:
            return ""

        if start_line == end_line:
            line = self.lines[start_line]
            return line[max(0, start_col):max(0, end_col)]

        chunks = []
        chunks.append(self.lines[start_line][max(0, start_col):])
        for idx in range(start_line + 1, end_line):
            chunks.append(self.lines[idx])
        chunks.append(self.lines[end_line][:max(0, end_col)])
        return "\n".join(chunks)

    def _cursor_from_screen(self, mx, my):
        """Map body coordinates into (line_idx, col) in log buffer."""
        bx, by, bw, bh = self.body_rect()
        if bw <= 0 or bh <= 0:
            return None
        view_rows = self._visible_line_rows()
        if not (bx <= mx < bx + bw and by + 1 <= my < by + 1 + view_rows):
            return None
        line_idx = self.scroll_offset + (my - (by + 1))
        if not (0 <= line_idx < len(self.lines)):
            return None
        line = self.lines[line_idx]
        col = max(0, min(len(line), mx - bx))
        return (line_idx, col)

    def _copy_selection(self):
        """Copy selected text (or current line fallback) into clipboard."""
        text = self._selected_text()
        if not text and self.lines:
            idx = max(0, min(self.scroll_offset, len(self.lines) - 1))
            text = self.lines[idx]
        if text:
            copy_text(text)

    @classmethod
    def _ensure_log_colors(cls):
        """Initialize dedicated severity colors once per process."""
        if cls._log_colors_ready:
            return
        init_pair = getattr(curses, "init_pair", None)
        if not callable(init_pair):
            cls._log_colors_ready = True
            return

        try:
            init_pair(cls.COLOR_ERROR_PAIR, getattr(curses, "COLOR_RED", 1), -1)
            init_pair(cls.COLOR_WARN_PAIR, getattr(curses, "COLOR_YELLOW", 3), -1)
            init_pair(cls.COLOR_INFO_PAIR, getattr(curses, "COLOR_GREEN", 2), -1)
        except Exception:
            pass
        cls._log_colors_ready = True

    @staticmethod
    def _normalize_text(value):
        return value.replace("\r\n", "\n").replace("\r", "\n")

    def _severity_attr(self, line, base_attr):
        """Return colorized attribute for one log line."""
        text = line.upper()
        pair_id = None
        if "ERROR" in text:
            pair_id = self.COLOR_ERROR_PAIR
        elif "WARN" in text:
            pair_id = self.COLOR_WARN_PAIR
        elif "INFO" in text:
            pair_id = self.COLOR_INFO_PAIR

        if pair_id is None:
            return base_attr

        self._ensure_log_colors()
        color_pair = getattr(curses, "color_pair", None)
        if callable(color_pair):
            try:
                return color_pair(pair_id) | curses.A_BOLD
            except Exception:
                return base_attr | curses.A_BOLD
        return base_attr | curses.A_BOLD

    def _visible_line_rows(self):
        _, _, _, bh = self.body_rect()
        return max(1, bh - 2)  # Header + status rows.

    def _max_scroll(self):
        return max(0, len(self.lines) - self._visible_line_rows())

    def _scroll_to_bottom(self):
        self.scroll_offset = self._max_scroll()

    def _scroll_to_line(self, line_index):
        line_index = max(0, min(int(line_index), max(0, len(self.lines) - 1)))
        max_scroll = self._max_scroll()
        view_rows = self._visible_line_rows()
        desired = min(max_scroll, max(0, line_index - max(0, view_rows // 2)))
        self.scroll_offset = desired

    def _trim_lines_if_needed(self):
        if len(self.lines) <= self.MAX_LINES:
            return
        trim = len(self.lines) - self.MAX_LINES
        self.lines = self.lines[trim:]
        self.scroll_offset = max(0, self.scroll_offset - trim)
        if self.search_query:
            self._rebuild_search_matches()

    def _append_lines(self, new_lines):
        if not new_lines:
            return
        self.lines.extend(new_lines)
        self._trim_lines_if_needed()
        if self.search_query:
            self._rebuild_search_matches()
        if self.follow_mode and not self.freeze_scroll:
            self._scroll_to_bottom()
        else:
            self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))

    def _reload_file(self):
        """Load a tail snapshot of current file."""
        if not self.filepath:
            return None

        try:
            with open(self.filepath, "rb") as stream:
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                start = max(0, size - self.READ_TAIL_BYTES)
                stream.seek(start, os.SEEK_SET)
                raw = stream.read()
            if start > 0:
                split_at = raw.find(b"\n")
                if split_at >= 0:
                    raw = raw[split_at + 1 :]
            text = self._normalize_text(raw.decode("utf-8", errors="replace"))
        except OSError as exc:
            self.lines = []
            self.file_position = 0
            self._tail_remainder = ""
            self._error_message = str(exc)
            self._rebuild_search_matches()
            return ActionResult(ActionType.ERROR, str(exc))

        rows = text.split("\n")
        if rows and rows[-1] == "":
            rows = rows[:-1]
        self.lines = rows[-self.MAX_LINES :]
        self.file_position = os.path.getsize(self.filepath)
        self._tail_remainder = ""
        self._error_message = None
        self._rebuild_search_matches()
        if self.follow_mode and not self.freeze_scroll:
            self._scroll_to_bottom()
        else:
            self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))
        return None

    def _poll_for_updates(self, force=False):
        """Read appended bytes while tail mode is enabled."""
        if not self.filepath:
            return
        now = time.monotonic()
        if not force and (now - self._last_poll) < self.POLL_INTERVAL_SECONDS:
            return
        self._last_poll = now

        try:
            current_size = os.path.getsize(self.filepath)
            if current_size < self.file_position:
                # Truncated/rotated file.
                self.file_position = 0
                self._tail_remainder = ""

            with open(self.filepath, "r", encoding="utf-8", errors="replace", newline="") as stream:
                stream.seek(self.file_position)
                chunk = stream.read()
                self.file_position = stream.tell()
        except OSError as exc:
            self._error_message = str(exc)
            return

        if not chunk:
            return

        text = self._tail_remainder + self._normalize_text(chunk)
        parts = text.split("\n")
        if text.endswith("\n"):
            self._tail_remainder = ""
        else:
            self._tail_remainder = parts.pop() if parts else text
        self._error_message = None
        self._append_lines(parts)

    def _rebuild_search_matches(self):
        query = self.search_query.strip().lower()
        if not query:
            self.search_matches = []
            self.search_index = -1
            return
        self.search_matches = [
            idx for idx, line in enumerate(self.lines) if query in line.lower()
        ]
        if not self.search_matches:
            self.search_index = -1
        elif self.search_index < 0:
            self.search_index = 0
        else:
            self.search_index = max(0, min(self.search_index, len(self.search_matches) - 1))

    def _jump_search_match(self, direction):
        if not self.search_matches:
            return
        if self.search_index < 0:
            self.search_index = 0
        else:
            size = len(self.search_matches)
            self.search_index = (self.search_index + direction) % size
        self._scroll_to_line(self.search_matches[self.search_index])

    def execute_action(self, action):
        if action == "lv_open":
            return ActionResult(ActionType.REQUEST_OPEN_PATH)
        if action == "lv_reload":
            return self._reload_file()
        if action == "lv_close":
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        if action == "lv_follow":
            self.follow_mode = not self.follow_mode
            if self.follow_mode and not self.freeze_scroll:
                self._scroll_to_bottom()
            return None
        if action == "lv_freeze":
            self.freeze_scroll = not self.freeze_scroll
            return None
        if action == "lv_copy":
            self._copy_selection()
            return None
        if action == "lv_search":
            self.search_input_mode = True
            self.search_input = self.search_query
            return None
        if action == "lv_next":
            self._jump_search_match(1)
            return None
        if action == "lv_prev":
            self._jump_search_match(-1)
            return None
        return None

    def open_path(self, filepath):
        """Load a file path in this viewer."""
        raw = (filepath or "").strip()
        if not raw:
            return None

        path = os.path.abspath(os.path.expanduser(raw))
        if not os.path.isfile(path):
            return ActionResult(ActionType.ERROR, f"Not a file: {path}")

        self.filepath = path
        self.title = f"Log Viewer - {os.path.basename(path)}"
        self.search_query = ""
        self.search_matches = []
        self.search_index = -1
        self.scroll_offset = 0
        self.clear_selection()
        self._tail_remainder = ""
        self.file_position = 0
        return self._reload_file()

    def draw(self, stdscr):
        """Draw log content area with severity highlighting."""
        if not self.visible:
            return

        self._poll_for_updates(force=False)
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        if bh <= 0 or bw <= 0:
            return

        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, " " * bw, body_attr)

        view_rows = self._visible_line_rows()
        self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))
        start = self.scroll_offset
        end = min(len(self.lines), start + view_rows)

        basename = os.path.basename(self.filepath) if self.filepath else "(no file)"
        mode = "TAIL" if self.follow_mode else "VIEW"
        freeze = "FROZEN" if self.freeze_scroll else "LIVE"
        query = f" /{self.search_query}" if self.search_query else ""
        header = f"{mode} {freeze} | {basename}{query}"
        safe_addstr(stdscr, by, bx, header[:bw].ljust(bw), theme_attr("menubar"))

        query_lc = self.search_query.lower()
        for row, line_index in enumerate(range(start, end), start=1):
            line = self.lines[line_index]
            line_attr = self._severity_attr(line, body_attr)
            if query_lc and query_lc in line.lower():
                line_attr |= curses.A_REVERSE
            rendered = line[:bw].ljust(bw)
            span = self._line_selection_span(line_index, len(line))
            if not span:
                safe_addstr(stdscr, by + row, bx, rendered, line_attr)
                continue

            start_col, end_col = span
            start_col = max(0, min(start_col, bw))
            end_col = max(start_col, min(end_col, bw))
            if start_col > 0:
                safe_addstr(stdscr, by + row, bx, rendered[:start_col], line_attr)
            if end_col > start_col:
                safe_addstr(
                    stdscr,
                    by + row,
                    bx + start_col,
                    rendered[start_col:end_col],
                    line_attr | curses.A_BOLD | curses.A_REVERSE,
                )
            if end_col < bw:
                safe_addstr(stdscr, by + row, bx + end_col, rendered[end_col:bw], line_attr)

        if self.search_input_mode:
            status = f"/{self.search_input}"
        else:
            match_info = ""
            if self.search_query:
                if self.search_matches:
                    match_info = (
                        f" | match {self.search_index + 1}/{len(self.search_matches)}"
                    )
                else:
                    match_info = " | no matches"
            error_info = f" | {self._error_message}" if self._error_message else ""
            status = (
                "Arrows/PgUp/PgDn scroll  F follow  Space freeze  / search  "
                f"n/N next{match_info}{error_info}"
            )
        safe_addstr(stdscr, by + bh - 1, bx, status[:bw].ljust(bw), theme_attr("status"))

        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def handle_click(self, mx, my, bstate=None):
        """Handle menu interactions and line-based scroll focus."""
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if action:
                    return self.execute_action(action)
                return None

        cursor_pos = self._cursor_from_screen(mx, my)
        if cursor_pos is None:
            if bstate is not None and (
                bstate
                & (
                    getattr(curses, "BUTTON1_CLICKED", 0)
                    | getattr(curses, "BUTTON1_PRESSED", 0)
                    | getattr(curses, "BUTTON1_DOUBLE_CLICKED", 0)
                )
            ):
                self.clear_selection()
            return None

        has_button1 = bool(
            bstate
            and (
                bstate & getattr(curses, "BUTTON1_CLICKED", 0)
                or bstate & getattr(curses, "BUTTON1_PRESSED", 0)
                or bstate & getattr(curses, "BUTTON1_DOUBLE_CLICKED", 0)
            )
        )
        if has_button1:
            self.selection_anchor = cursor_pos
            self.selection_cursor = cursor_pos
            self._mouse_selecting = bool(bstate & getattr(curses, "BUTTON1_PRESSED", 0))
        else:
            self._scroll_to_line(cursor_pos[0])
        return None

    def handle_mouse_drag(self, mx, my, bstate):
        """Extend selection while dragging with primary button."""
        if not (bstate & getattr(curses, "BUTTON1_PRESSED", 0)):
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

    def _handle_search_input_key(self, key, key_code):
        """Handle keypress while search input mode is active."""
        if key_code == 27:  # Esc
            self.search_input_mode = False
            self.search_input = ""
            return None
        if key_code in (curses.KEY_ENTER, 10, 13):
            self.search_input_mode = False
            self.search_query = self.search_input.strip()
            self.search_input = ""
            self._rebuild_search_matches()
            self._jump_search_match(1)
            return None
        if key_code in (curses.KEY_BACKSPACE, 127, 8):
            self.search_input = self.search_input[:-1]
            return None

        if isinstance(key, str) and key.isprintable() and key not in ("\n", "\r", "\t"):
            self.search_input += key
            return None
        if isinstance(key, int) and 32 <= key <= 126:
            self.search_input += chr(key)
            return None
        return None

    def handle_key(self, key):
        """Handle keyboard actions for viewer control."""
        key_code = normalize_key_code(key)

        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self.execute_action(action)
            return None

        if self.search_input_mode:
            return self._handle_search_input_key(key, key_code)

        if key_code == curses.KEY_UP:
            self.follow_mode = False
            self.scroll_offset = max(0, self.scroll_offset - 1)
        elif key_code == curses.KEY_DOWN:
            self.follow_mode = False
            self.scroll_offset = min(self._max_scroll(), self.scroll_offset + 1)
        elif key_code == curses.KEY_PPAGE:
            self.follow_mode = False
            self.scroll_offset = max(0, self.scroll_offset - self._visible_line_rows())
        elif key_code == curses.KEY_NPAGE:
            self.follow_mode = False
            self.scroll_offset = min(
                self._max_scroll(), self.scroll_offset + self._visible_line_rows()
            )
        elif key_code == curses.KEY_HOME:
            self.follow_mode = False
            self.scroll_offset = 0
        elif key_code == curses.KEY_END:
            self.follow_mode = True
            if not self.freeze_scroll:
                self._scroll_to_bottom()
        elif key_code in (ord("f"), ord("F")):
            self.follow_mode = not self.follow_mode
            if self.follow_mode and not self.freeze_scroll:
                self._scroll_to_bottom()
        elif key_code in (getattr(curses, "KEY_F6", -1), getattr(curses, "KEY_IC", -1)):
            self._copy_selection()
        elif key_code in (ord(" "), ord("p"), ord("P")):
            self.freeze_scroll = not self.freeze_scroll
        elif key_code in (ord("/"),):
            self.search_input_mode = True
            self.search_input = self.search_query
        elif key_code == ord("n"):
            self._jump_search_match(1)
        elif key_code == ord("N"):
            self._jump_search_match(-1)
        elif key_code in (ord("o"), ord("O")):
            return ActionResult(ActionType.REQUEST_OPEN_PATH)
        elif key_code in (ord("r"), ord("R")):
            return self._reload_file()
        elif key_code in (ord("q"), ord("Q")):
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        elif key_code == 27:
            if self.has_selection():
                self.clear_selection()
            else:
                self.search_query = ""
                self.search_matches = []
                self.search_index = -1

        return None

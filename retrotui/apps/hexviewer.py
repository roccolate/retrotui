"""Hex viewer window for binary files."""

import curses
import os
import string

from ..core.actions import ActionResult, ActionType, AppAction
from ..core.clipboard import copy_text
from ..ui.menu import WindowMenu
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr


_HEX_DIGITS = set(string.hexdigits)


def _ascii_column(data):
    """Return printable ASCII representation for one byte row."""
    return "".join(chr(value) if 32 <= value <= 126 else "." for value in data)


class HexViewerWindow(Window):
    """Read-only hex viewer with offset/hex/ascii columns."""

    BYTES_PER_ROW = 16

    def __init__(self, x, y, w, h, filepath=None):
        super().__init__("Hex Viewer", x, y, max(56, w), max(12, h), content=[])
        self.window_menu = WindowMenu(
            {
                "File": [
                    ("Open...        O", "hx_open"),
                    ("Reload         R", "hx_reload"),
                    ("-------------", None),
                    ("Close          Q", "hx_close"),
                ],
                "Search": [
                    ("Search         /", "hx_search"),
                    ("Find Next      N", "hx_next"),
                    ("Go to offset   G", "hx_goto"),
                    ("Copy Selection F6", "hx_copy"),
                ],
            }
        )
        self.filepath = None
        self.file_size = 0
        self.top_offset = 0
        self.cursor_offset = None
        self.status_message = ""
        self.prompt_mode = None
        self.prompt_value = ""
        self.last_query_bytes = None
        self.selection_anchor = None  # row index
        self.selection_cursor = None  # row index
        self._mouse_selecting = False

        if filepath:
            self.open_path(filepath)

    def _update_title(self):
        """Update title with current filename and size."""
        if not self.filepath:
            self.title = "Hex Viewer"
            return
        basename = os.path.basename(self.filepath) or self.filepath
        self.title = f"Hex Viewer - {basename} ({self.file_size} B)"

    def open_path(self, filepath):
        """Open a file path and reset view state."""
        path = os.path.realpath(os.path.expanduser(str(filepath)))
        if not os.path.isfile(path):
            return ActionResult(ActionType.ERROR, f"Not a file: {path}")
        try:
            st = os.stat(path)
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        self.filepath = path
        self.file_size = int(st.st_size)
        self.top_offset = 0
        self.cursor_offset = 0 if self.file_size > 0 else None
        self.last_query_bytes = None
        self.prompt_mode = None
        self.prompt_value = ""
        self.status_message = f"Opened {path}"
        self.clear_selection()
        self._update_title()
        return None

    def _rows_visible(self):
        """Return number of hex rows visible in current body."""
        _, _, _, bh = self.body_rect()
        return max(1, bh - 2)

    def _max_top_offset(self):
        """Return max aligned top offset for current file/viewport."""
        if self.file_size <= 0:
            return 0
        visible_bytes = self._rows_visible() * self.BYTES_PER_ROW
        max_start = max(0, self.file_size - visible_bytes)
        return (max_start // self.BYTES_PER_ROW) * self.BYTES_PER_ROW

    def _set_top_offset(self, offset):
        """Clamp and align view offset."""
        max_offset = self._max_top_offset()
        clamped = max(0, min(int(offset), max_offset))
        self.top_offset = (clamped // self.BYTES_PER_ROW) * self.BYTES_PER_ROW

    def _scroll_rows(self, delta_rows):
        """Scroll by row count."""
        self._set_top_offset(self.top_offset + delta_rows * self.BYTES_PER_ROW)

    def _read_slice(self, offset, length):
        """Read one chunk from current file."""
        if not self.filepath or length <= 0:
            return b""
        try:
            with open(self.filepath, "rb") as stream:
                stream.seek(max(0, int(offset)))
                return stream.read(max(0, int(length)))
        except OSError as exc:
            self.status_message = f"Read error: {exc}"
            return b""

    @staticmethod
    def _format_header():
        """Return header row for columns."""
        return "OFFSET(h) | 00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F | ASCII"

    def _format_row(self, offset, row_bytes):
        """Render one hex row."""
        cells = [f"{value:02X}" for value in row_bytes]
        if len(cells) < self.BYTES_PER_ROW:
            cells.extend(["  "] * (self.BYTES_PER_ROW - len(cells)))
        left = " ".join(cells[:8])
        right = " ".join(cells[8:])
        ascii_text = _ascii_column(row_bytes).ljust(self.BYTES_PER_ROW)
        return f"{offset:08X} | {left}  {right} | {ascii_text}"

    @staticmethod
    def _parse_goto_value(raw):
        """Parse decimal or hexadecimal offset value."""
        value = raw.strip().lower()
        if not value:
            return None
        try:
            if value.startswith("0x"):
                return int(value, 16)
            if value.endswith("h") and len(value) > 1:
                return int(value[:-1], 16)
            return int(value, 10)
        except ValueError:
            return None

    @staticmethod
    def _parse_search_query(raw):
        """Parse search query into byte sequence.

        Accepted inputs:
        - 0x48656c6c6f
        - 48 65 6c 6c 6f
        - plain text (utf-8)
        """
        text = raw.strip()
        if not text:
            return None

        lowered = text.lower()
        if lowered.startswith("0x"):
            hex_blob = lowered[2:].replace(" ", "")
            if not hex_blob or len(hex_blob) % 2 != 0:
                return None
            if any(ch not in _HEX_DIGITS for ch in hex_blob):
                return None
            return bytes.fromhex(hex_blob)

        if " " in text:
            chunks = [token for token in text.split(" ") if token]
            if chunks and all(1 <= len(token) <= 2 for token in chunks):
                if all(all(ch in _HEX_DIGITS for ch in token) for token in chunks):
                    return bytes(int(token, 16) for token in chunks)

        return text.encode("utf-8", errors="replace")

    def _find_bytes(self, needle, start_offset):
        """Find byte sequence from start offset; returns absolute offset or None."""
        if not self.filepath or not needle:
            return None
        overlap = max(0, len(needle) - 1)
        cursor = max(0, int(start_offset))
        tail = b""
        try:
            with open(self.filepath, "rb") as stream:
                stream.seek(cursor)
                while True:
                    chunk = stream.read(64 * 1024)
                    if not chunk:
                        return None
                    haystack = tail + chunk
                    idx = haystack.find(needle)
                    if idx != -1:
                        return cursor - len(tail) + idx
                    tail = haystack[-overlap:] if overlap else b""
                    cursor += len(chunk)
        except OSError as exc:
            self.status_message = f"Search error: {exc}"
            return None

    def _find_with_wrap(self, needle, start_offset):
        """Find bytes from start and wrap to file head if needed."""
        if self.file_size <= 0:
            return None
        start = max(0, min(int(start_offset), max(0, self.file_size - 1)))
        found = self._find_bytes(needle, start)
        if found is None and start > 0:
            found = self._find_bytes(needle, 0)
        return found

    def _goto_offset(self, offset):
        """Move cursor/view to absolute offset."""
        if self.file_size <= 0:
            self.cursor_offset = None
            self.top_offset = 0
            return
        target = max(0, min(int(offset), self.file_size - 1))
        self.cursor_offset = target
        self._set_top_offset(target)

    def _apply_prompt(self):
        """Execute current prompt mode action."""
        mode = self.prompt_mode
        value = self.prompt_value
        self.prompt_mode = None
        self.prompt_value = ""

        if mode == "goto":
            target = self._parse_goto_value(value)
            if target is None:
                self.status_message = "Invalid offset. Use decimal or 0xHEX."
                return
            self._goto_offset(target)
            self.status_message = f"Jumped to 0x{target:X}"
            return

        if mode == "search":
            needle = self._parse_search_query(value)
            if not needle:
                self.status_message = "Invalid search query."
                return
            self.last_query_bytes = needle
            start = (self.cursor_offset + 1) if self.cursor_offset is not None else self.top_offset
            found = self._find_with_wrap(needle, start)
            if found is None:
                self.status_message = "Pattern not found."
                return
            self._goto_offset(found)
            self.status_message = f"Found at 0x{found:X}"

    def clear_selection(self):
        """Clear row selection state."""
        self.selection_anchor = None
        self.selection_cursor = None
        self._mouse_selecting = False

    def has_selection(self):
        """Return True when at least one row span is selected."""
        return (
            self.selection_anchor is not None
            and self.selection_cursor is not None
            and self.selection_anchor != self.selection_cursor
        )

    def _selected_row_bounds(self):
        """Return (start_row, end_row_exclusive) or None."""
        if not self.has_selection():
            return None
        a = int(self.selection_anchor)
        b = int(self.selection_cursor)
        if a <= b:
            return (a, b)
        return (b, a)

    def _row_from_screen(self, mx, my):
        """Map screen coordinate to absolute row index in file."""
        bx, by, bw, bh = self.body_rect()
        data_rows = max(0, bh - 2)
        if data_rows <= 0 or bw <= 0:
            return None
        if not (bx <= mx < bx + bw and by + 1 <= my < by + 1 + data_rows):
            return None

        row = my - (by + 1)
        row_idx = (self.top_offset // self.BYTES_PER_ROW) + row
        if row_idx < 0:
            return None
        max_rows = (self.file_size + self.BYTES_PER_ROW - 1) // self.BYTES_PER_ROW
        if row_idx >= max_rows:
            return None
        return row_idx

    def _selected_text(self):
        """Return selected hex rows as text block."""
        bounds = self._selected_row_bounds()
        if not bounds or not self.filepath:
            return ""
        start_row, end_row = bounds
        if end_row <= start_row:
            return ""
        rows = []
        for row_idx in range(start_row, end_row):
            row_offset = row_idx * self.BYTES_PER_ROW
            row_bytes = self._read_slice(row_offset, self.BYTES_PER_ROW)
            if not row_bytes and row_offset >= self.file_size:
                break
            rows.append(self._format_row(row_offset, row_bytes))
        return "\n".join(rows)

    def _copy_selection(self):
        """Copy selected hex rows or focused row to clipboard."""
        text = self._selected_text()
        if not text and self.cursor_offset is not None and self.filepath:
            row_offset = (self.cursor_offset // self.BYTES_PER_ROW) * self.BYTES_PER_ROW
            row_bytes = self._read_slice(row_offset, self.BYTES_PER_ROW)
            text = self._format_row(row_offset, row_bytes)
        if text:
            copy_text(text)

    def find_next(self):
        """Find next match for the last query."""
        if not self.last_query_bytes:
            self.status_message = "No active search. Press / first."
            return
        start = (self.cursor_offset + 1) if self.cursor_offset is not None else self.top_offset
        found = self._find_with_wrap(self.last_query_bytes, start)
        if found is None:
            self.status_message = "Pattern not found."
            return
        self._goto_offset(found)
        self.status_message = f"Found at 0x{found:X}"

    def execute_action(self, action):
        if action == "hx_open":
            return ActionResult(ActionType.REQUEST_OPEN_PATH)
        if action == "hx_reload":
            if self.filepath:
                return self.open_path(self.filepath)
            self.status_message = "No file opened."
            return None
        if action == "hx_search":
            self.prompt_mode = "search"
            self.prompt_value = ""
            return None
        if action == "hx_next":
            self.find_next()
            return None
        if action == "hx_goto":
            self.prompt_mode = "goto"
            self.prompt_value = ""
            return None
        if action == "hx_copy":
            self._copy_selection()
            return None
        if action == "hx_close":
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

    def draw(self, stdscr):
        """Draw hex table body and status line."""
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        if bw <= 0 or bh <= 0:
            return

        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, " " * bw, body_attr)
            
        data_rows = max(0, bh - 3)
        if data_rows > 0:
            safe_addstr(stdscr, by + 1, bx, self._format_header()[:bw].ljust(bw), theme_attr("menubar"))

            if self.filepath:
                total = data_rows * self.BYTES_PER_ROW
                chunk = self._read_slice(self.top_offset, total)
                for row in range(data_rows):
                    row_offset = self.top_offset + row * self.BYTES_PER_ROW
                    if row_offset >= self.file_size:
                        break
                    start = row * self.BYTES_PER_ROW
                    row_bytes = chunk[start:start + self.BYTES_PER_ROW]
                    line = self._format_row(row_offset, row_bytes)
                    row_attr = body_attr
                    row_idx = row_offset // self.BYTES_PER_ROW
                    selected_rows = self._selected_row_bounds()
                    if selected_rows and selected_rows[0] <= row_idx < selected_rows[1]:
                        row_attr = theme_attr("file_selected") | curses.A_REVERSE | curses.A_BOLD
                    if self.cursor_offset is not None and row_offset <= self.cursor_offset < row_offset + len(row_bytes):
                        row_attr = theme_attr("file_selected") | curses.A_BOLD
                    safe_addstr(stdscr, by + 2 + row, bx, line[:bw].ljust(bw), row_attr)
            else:
                safe_addstr(stdscr, by + 2, bx, "No file opened. Press O to open."[:bw].ljust(bw), body_attr)

        if self.prompt_mode == "search":
            status = f"SEARCH> {self.prompt_value}"
        elif self.prompt_mode == "goto":
            status = f"GOTO> {self.prompt_value}"
        elif self.status_message:
            status = self.status_message
        else:
            status = "Arrows/PgUp/PgDn scroll | / search | N next | G goto | Q close"
        safe_addstr(stdscr, by + bh - 1, bx, status[:bw].ljust(bw), theme_attr("status"))

        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, win_x=self.x, win_y=self.y, win_w=self.w)

    def handle_click(self, mx, my, bstate=None):
        """Handle menu interactions."""
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, win_x=self.x, win_y=self.y, win_w=self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, win_x=self.x, win_y=self.y, win_w=self.w)
                if action:
                    return self.execute_action(action)
        row_idx = self._row_from_screen(mx, my)
        if row_idx is None:
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
            self.selection_anchor = row_idx
            self.selection_cursor = row_idx + 1
            self._mouse_selecting = bool(bstate & getattr(curses, "BUTTON1_PRESSED", 0))
            self._goto_offset(row_idx * self.BYTES_PER_ROW)
        return None

    def handle_mouse_drag(self, mx, my, bstate):
        """Extend row selection while button is held."""
        if not (bstate & getattr(curses, "BUTTON1_PRESSED", 0)):
            self._mouse_selecting = False
            return None
        row_idx = self._row_from_screen(mx, my)
        if row_idx is None:
            return None
        if self.selection_anchor is None:
            self.selection_anchor = row_idx
        self.selection_cursor = row_idx + 1
        self._mouse_selecting = True
        return None

    def _handle_prompt_key(self, key, key_code):
        """Capture inline prompt input for search/go-to."""
        if key_code in (27,):
            self.prompt_mode = None
            self.prompt_value = ""
            self.status_message = "Prompt cancelled."
            return None
        if key_code in (getattr(curses, "KEY_ENTER", -1), 10, 13):
            self._apply_prompt()
            return None
        if key_code in (getattr(curses, "KEY_BACKSPACE", -1), 8, 127):
            if self.prompt_value:
                self.prompt_value = self.prompt_value[:-1]
            return None

        if isinstance(key, str) and len(key) == 1 and key.isprintable():
            self.prompt_value += key
            return None
        if isinstance(key_code, int) and 32 <= key_code <= 126:
            self.prompt_value += chr(key_code)
        return None

    def handle_key(self, key):
        """Handle key bindings for scrolling, prompt and menu actions."""
        key_code = normalize_key_code(key)

        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self.execute_action(action)
            return None

        if self.prompt_mode:
            return self._handle_prompt_key(key, key_code)

        if key_code in (ord("q"), ord("Q")):
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        if key_code in (ord("o"), ord("O")):
            return ActionResult(ActionType.REQUEST_OPEN_PATH)
        if key_code in (ord("r"), ord("R")):
            if self.filepath:
                return self.open_path(self.filepath)
            self.status_message = "No file opened."
            return None
        if key_code == ord("/"):
            self.prompt_mode = "search"
            self.prompt_value = ""
            return None
        if key_code in (ord("n"), ord("N")):
            self.find_next()
            return None
        if key_code in (getattr(curses, "KEY_F6", -1), getattr(curses, "KEY_IC", -1)):
            self._copy_selection()
            return None
        if key_code in (ord("g"), ord("G")):
            self.prompt_mode = "goto"
            self.prompt_value = ""
            return None

        if key_code == getattr(curses, "KEY_UP", -1):
            self._scroll_rows(-1)
            return None
        if key_code == getattr(curses, "KEY_DOWN", -1):
            self._scroll_rows(1)
            return None
        if key_code == getattr(curses, "KEY_PPAGE", -1):
            self._scroll_rows(-self._rows_visible())
            return None
        if key_code == getattr(curses, "KEY_NPAGE", -1):
            self._scroll_rows(self._rows_visible())
            return None
        if key_code == getattr(curses, "KEY_HOME", -1):
            self._set_top_offset(0)
            return None
        if key_code == getattr(curses, "KEY_END", -1):
            self._set_top_offset(self._max_top_offset())
            return None
        return None

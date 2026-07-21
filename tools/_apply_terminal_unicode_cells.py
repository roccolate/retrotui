"""One-shot applicator for the terminal Unicode cell-engine slice."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, path: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement, found {count}")
    return text.replace(old, new, 1)


def replace_between(text: str, start_marker: str, end_marker: str, new: str, path: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"{path}: missing start marker {start_marker!r}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"{path}: missing end marker {end_marker!r}")
    return text[:start] + new + text[end:]


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


write("retrotui/core/terminal_cells.py", '"""Unicode display-cell helpers for the embedded terminal."""\n\nfrom __future__ import annotations\n\nfrom collections.abc import Sequence\n\nfrom wcwidth import wcwidth, wcswidth\n\n\nCONTINUATION_TEXT = ""\n\n\ndef display_width(text: str) -> int:\n    """Return terminal display width for one stored grapheme-like cell."""\n    if not text:\n        return 0\n    width = wcswidth(str(text))\n    if width < 0:\n        return -1\n    return min(width, 2)\n\n\ndef codepoint_width(ch: str) -> int:\n    """Return the printable width of one codepoint."""\n    if not ch:\n        return 0\n    return wcwidth(ch[0])\n\n\ndef is_continuation(cell) -> bool:\n    """Return whether ``cell`` is the reserved tail of a wide glyph."""\n    return bool(cell) and cell[0] == CONTINUATION_TEXT\n\n\ndef leading_cell_index(row: Sequence, col: int) -> int | None:\n    """Resolve a physical column to the glyph-leading column."""\n    if not 0 <= col < len(row):\n        return None\n    if not is_continuation(row[col]):\n        return col\n    index = col - 1\n    while index >= 0 and is_continuation(row[index]):\n        index -= 1\n    return index if index >= 0 else None\n\n\ndef row_text(cells: Sequence) -> str:\n    """Convert physical cells to plain text without continuation sentinels."""\n    return "".join(cell[0] for cell in cells if cell and not is_continuation(cell))\n\n\ndef sanitize_row(cells: Sequence, default_attr: int = 0) -> list[tuple[str, int]]:\n    """Remove orphan tails and half-wide glyphs from a physical row."""\n    row = [(str(cell[0]), cell[1]) for cell in cells]\n    blank = (" ", default_attr)\n    for col, (text, attr) in enumerate(list(row)):\n        if text == CONTINUATION_TEXT:\n            lead = leading_cell_index(row, col)\n            if lead is None or col != lead + 1 or display_width(row[lead][0]) != 2:\n                row[col] = blank\n            else:\n                row[col] = (CONTINUATION_TEXT, row[lead][1])\n            continue\n        if display_width(text) == 2:\n            if col + 1 >= len(row) or not is_continuation(row[col + 1]):\n                row[col] = blank\n            else:\n                row[col + 1] = (CONTINUATION_TEXT, attr)\n    return row\n')

session_path = ROOT / "retrotui/core/terminal_session.py"
session = session_path.read_text(encoding="utf-8")
session = replace_once(
    session,
    "import time\n",
    "import time\n\nfrom .terminal_cells import (\n"
    "    CONTINUATION_TEXT,\n"
    "    codepoint_width,\n"
    "    display_width,\n"
    "    is_continuation,\n"
    "    leading_cell_index,\n"
    "    sanitize_row,\n"
    ")\n",
    str(session_path),
)
session = replace_between(
    session,
    "class TerminalScreenBuffer:",
    "\n\nclass TerminalScreen:",
    'class TerminalScreenBuffer:\n    """2D grid of physical terminal cells with Unicode width semantics.\n\n    Cells retain the legacy ``(text, attr)`` tuple contract. A wide glyph is\n    stored in its leading cell and reserves the following physical column with\n    ``("", attr)``. Combining marks and zero-width joiners are appended to the\n    preceding leading cell without advancing the cursor.\n    """\n\n    __slots__ = (\n        "rows",\n        "cols",\n        "_grid",\n        "_cursor_row",\n        "_cursor_col",\n        "_default_attr",\n        "_scroll_sink",\n    )\n\n    def __init__(self, rows, cols, default_attr=0):\n        rows = max(1, int(rows))\n        cols = max(1, int(cols))\n        self.rows = rows\n        self.cols = cols\n        self._default_attr = int(default_attr)\n        self._grid = [self._blank_row() for _ in range(rows)]\n        self._cursor_row = 0\n        self._cursor_col = 0\n        self._scroll_sink = None\n\n    def _blank_cell(self):\n        return (" ", self._default_attr)\n\n    def _blank_row(self):\n        return [self._blank_cell() for _ in range(self.cols)]\n\n    @property\n    def cursor_row(self):\n        return self._cursor_row\n\n    @property\n    def cursor_col(self):\n        return self._cursor_col\n\n    def set_cursor(self, row, col):\n        """Move the cursor to a physical column clamped to the grid."""\n        self._cursor_row = max(0, min(self.rows - 1, int(row)))\n        self._cursor_col = max(0, min(self.cols - 1, int(col)))\n\n    def get_cell(self, row, col):\n        """Return the ``(text, attr)`` at ``(row, col)`` or a blank cell."""\n        if 0 <= row < self.rows and 0 <= col < self.cols:\n            return self._grid[row][col]\n        return self._blank_cell()\n\n    def get_row(self, row):\n        """Return a copy of one physical row."""\n        if 0 <= row < self.rows:\n            return list(self._grid[row])\n        return []\n\n    def normalize_row(self, row):\n        """Repair wide-cell invariants for one row after direct legacy edits."""\n        if 0 <= row < self.rows:\n            normalized = sanitize_row(self._grid[row], self._default_attr)\n            if len(normalized) < self.cols:\n                normalized.extend(self._blank_cell() for _ in range(self.cols - len(normalized)))\n            self._grid[row] = normalized[:self.cols]\n\n    def _glyph_bounds(self, row, col):\n        if not (0 <= row < self.rows and 0 <= col < self.cols):\n            return None\n        line = self._grid[row]\n        lead = leading_cell_index(line, col)\n        if lead is None:\n            return None\n        width = display_width(line[lead][0])\n        end = lead + (2 if width == 2 else 1)\n        return lead, min(self.cols, end)\n\n    def _clear_glyph_at(self, row, col):\n        bounds = self._glyph_bounds(row, col)\n        if bounds is None:\n            return\n        start, end = bounds\n        for index in range(start, end):\n            self._grid[row][index] = self._blank_cell()\n\n    def _previous_leading_cell(self):\n        if self._cursor_col > 0:\n            col = min(self.cols - 1, self._cursor_col - 1)\n            lead = leading_cell_index(self._grid[self._cursor_row], col)\n            if lead is not None:\n                return self._cursor_row, lead\n        return None\n\n    def _merge_with_previous(self, ch):\n        previous = self._previous_leading_cell()\n        if previous is None:\n            return False\n        row, lead = previous\n        text, attr = self._grid[row][lead]\n        if text == " ":\n            return False\n\n        old_width = display_width(text)\n        merged = text + ch\n        new_width = display_width(merged)\n        if new_width < 0:\n            return False\n        if old_width < 1:\n            old_width = 1\n        if new_width < 1:\n            new_width = old_width\n        if new_width > 2:\n            new_width = 2\n\n        if new_width == 2 and lead + 1 >= self.cols:\n            return False\n\n        if old_width == 2 and new_width == 1 and lead + 1 < self.cols:\n            self._grid[row][lead + 1] = self._blank_cell()\n            if self._cursor_col > lead + 1:\n                self._cursor_col -= 1\n        elif old_width == 1 and new_width == 2:\n            self._clear_glyph_at(row, lead + 1)\n            self._grid[row][lead + 1] = (CONTINUATION_TEXT, attr)\n            if self._cursor_col == lead + 1:\n                self._cursor_col += 1\n\n        self._grid[row][lead] = (merged, attr)\n        if new_width == 2:\n            self._grid[row][lead + 1] = (CONTINUATION_TEXT, attr)\n        return True\n\n    def put_char(self, ch, attr=None, *, autowrap=True):\n        """Write one Unicode codepoint and advance by its display width."""\n        if not ch:\n            return\n        attr = self._default_attr if attr is None else attr\n        width = codepoint_width(ch)\n        if width < 0:\n            return\n\n        previous = self._previous_leading_cell()\n        previous_text = ""\n        if previous is not None:\n            previous_text = self._grid[previous[0]][previous[1]][0]\n        if width == 0 or previous_text.endswith("\\u200d"):\n            if self._merge_with_previous(ch):\n                return\n            if width == 0:\n                return\n\n        width = 2 if width >= 2 else 1\n\n        if self._cursor_col >= self.cols:\n            if autowrap:\n                self.line_feed()\n                self._cursor_col = 0\n            else:\n                self._cursor_col = self.cols - 1\n\n        if width == 2 and self.cols < 2:\n            ch = "\\ufffd"\n            width = 1\n        elif width == 2 and self._cursor_col == self.cols - 1:\n            if autowrap:\n                self.line_feed()\n                self._cursor_col = 0\n            else:\n                ch = "\\ufffd"\n                width = 1\n\n        row = self._cursor_row\n        col = self._cursor_col\n        self._clear_glyph_at(row, col)\n        if width == 2:\n            self._clear_glyph_at(row, col + 1)\n\n        self._grid[row][col] = (ch, attr)\n        if width == 2:\n            self._grid[row][col + 1] = (CONTINUATION_TEXT, attr)\n\n        if autowrap:\n            self._cursor_col += width\n        else:\n            self._cursor_col = min(self.cols - 1, self._cursor_col + width)\n\n    def carriage_return(self):\n        self._cursor_col = 0\n\n    def line_feed(self):\n        if self._cursor_row >= self.rows - 1:\n            self.scroll_up()\n        else:\n            self._cursor_row += 1\n\n    def backspace(self):\n        if self._cursor_col <= 0:\n            return\n        target = min(self.cols - 1, self._cursor_col - 1)\n        lead = leading_cell_index(self._grid[self._cursor_row], target)\n        self._cursor_col = target if lead is None else lead\n\n    def clear_range(self, row, start, end):\n        """Clear a half-open physical-column range without splitting glyphs."""\n        if not 0 <= row < self.rows:\n            return\n        start = max(0, min(self.cols, int(start)))\n        end = max(start, min(self.cols, int(end)))\n        if start >= end:\n            return\n\n        line = self._grid[row]\n        if start < self.cols and is_continuation(line[start]):\n            lead = leading_cell_index(line, start)\n            if lead is not None:\n                start = lead\n        if end > 0:\n            bounds = self._glyph_bounds(row, end - 1)\n            if bounds is not None:\n                end = max(end, bounds[1])\n\n        for col in range(start, min(end, self.cols)):\n            self._grid[row][col] = self._blank_cell()\n\n    def clear_line(self, row=None):\n        if row is None:\n            row = self._cursor_row\n        if 0 <= row < self.rows:\n            self._grid[row] = self._blank_row()\n            if row == self._cursor_row:\n                self._cursor_col = 0\n\n    def clear_screen(self, mode="all"):\n        if mode == "all":\n            self._grid = [self._blank_row() for _ in range(self.rows)]\n            self._cursor_row = 0\n            self._cursor_col = 0\n            return\n        if mode == "below":\n            self.clear_range(self._cursor_row, self._cursor_col, self.cols)\n            for row in range(self._cursor_row + 1, self.rows):\n                self._grid[row] = self._blank_row()\n            return\n        if mode == "above":\n            for row in range(0, self._cursor_row):\n                self._grid[row] = self._blank_row()\n            self.clear_range(self._cursor_row, 0, self._cursor_col + 1)\n            return\n        raise ValueError(f"unknown clear_screen mode: {mode!r}")\n\n    def scroll_up(self, count=1):\n        if count <= 0 or self.rows <= 0:\n            return\n        for _ in range(min(count, self.rows)):\n            scrolled_off = self._grid.pop(0)\n            self._grid.append(self._blank_row())\n            sink = self._scroll_sink\n            if sink is not None:\n                try:\n                    sink(scrolled_off)\n                except Exception:\n                    pass\n\n    def set_scroll_sink(self, sink):\n        self._scroll_sink = sink\n\n    def scroll_down(self, count=1):\n        if count <= 0 or self.rows <= 0:\n            return\n        for _ in range(min(count, self.rows)):\n            self._grid.insert(0, self._blank_row())\n            self._grid.pop()\n\n    def insert_line(self, count=1):\n        if count <= 0:\n            return\n        for _ in range(min(count, self.rows)):\n            self._grid.insert(self._cursor_row, self._blank_row())\n            self._grid.pop()\n\n    def delete_line(self, count=1):\n        if count <= 0:\n            return\n        for _ in range(min(count, self.rows)):\n            self._grid.pop(self._cursor_row)\n            self._grid.append(self._blank_row())\n\n    def delete_chars(self, count=1):\n        """Delete physical columns at the cursor without orphaning wide tails."""\n        count = max(1, int(count))\n        row = self._cursor_row\n        line = self._grid[row]\n        if self._cursor_col >= self.cols:\n            return\n        start = self._cursor_col\n        if is_continuation(line[start]):\n            lead = leading_cell_index(line, start)\n            if lead is not None:\n                start = lead\n        end = min(self.cols, start + count)\n        if end < self.cols and is_continuation(line[end]):\n            end += 1\n        bounds = self._glyph_bounds(row, end - 1)\n        if bounds is not None:\n            end = max(end, bounds[1])\n        removed = max(0, end - start)\n        del line[start:end]\n        line.extend(self._blank_cell() for _ in range(removed))\n        self._grid[row] = sanitize_row(line[:self.cols], self._default_attr)\n\n    def resize(self, rows, cols):\n        rows = max(1, int(rows))\n        cols = max(1, int(cols))\n        old_cols = self.cols\n        new_grid = [\n            [(" ", self._default_attr) for _ in range(cols)] for _ in range(rows)\n        ]\n        common_rows = min(rows, self.rows)\n        common_cols = min(cols, old_cols)\n        for row in range(common_rows):\n            new_grid[row][:common_cols] = self._grid[row][:common_cols]\n            new_grid[row] = sanitize_row(new_grid[row], self._default_attr)\n        self._grid = new_grid\n        self.rows = rows\n        self.cols = cols\n        self._cursor_row = min(self._cursor_row, rows - 1)\n        self._cursor_col = min(self._cursor_col, cols - 1)'.rstrip(),
    str(session_path),
)
session = replace_once(
    session,
    "    def put_char(self, ch, attr=None):\n"
    "        self._active.put_char(ch, attr=attr)\n",
    "    def put_char(self, ch, attr=None, *, autowrap=True):\n"
    "        self._active.put_char(ch, attr=attr, autowrap=autowrap)\n",
    str(session_path),
)
session_path.write_text(session, encoding="utf-8", newline="\n")


terminal_path = ROOT / "retrotui/apps/terminal.py"
terminal = terminal_path.read_text(encoding="utf-8")
terminal = replace_once(
    terminal,
    "from ..core.terminal_session import TerminalScreen, TerminalScreenBuffer, TerminalSession\n",
    "from ..core.terminal_session import TerminalScreen, TerminalScreenBuffer, TerminalSession\n"
    "from ..core.terminal_cells import is_continuation, leading_cell_index, row_text\n",
    str(terminal_path),
)
terminal = replace_once(
    terminal,
    "        active._grid[row] = row_cells\n",
    "        active._grid[row] = row_cells\n"
    "        active.normalize_row(row)\n",
    str(terminal_path),
)
terminal = replace_once(
    terminal,
    "                alt._grid[r] = row[:alt.cols]\n",
    "                alt._grid[r] = row[:alt.cols]\n"
    "                alt.normalize_row(r)\n",
    str(terminal_path),
)
terminal = replace_once(
    terminal,
    "    def _get_line_text(self, line_cells):\n"
    "        \"\"\"Helper to convert cell list to plain string.\"\"\"\n"
    "        return ''.join(c[0] for c in line_cells)\n",
    "    def _get_line_text(self, line_cells):\n"
    "        \"\"\"Convert physical cells to plain text.\"\"\"\n"
    "        return row_text(line_cells)\n",
    str(terminal_path),
)
terminal = replace_between(
    terminal,
    "    def _selected_text(self):",
    "\n    def _cursor_from_screen",
    '    def _selected_text(self):\n        """Return selected text from physical cell coordinates."""\n        bounds = self._selection_bounds()\n        if not bounds:\n            return \'\'\n        (start_line, start_col), (end_line, end_col) = bounds\n        lines = self._all_lines()\n        if not lines:\n            return \'\'\n\n        start_line = max(0, min(start_line, len(lines) - 1))\n        end_line = max(0, min(end_line, len(lines) - 1))\n        if end_line < start_line:\n            return \'\'\n\n        if start_line == end_line:\n            cells = lines[start_line]\n            return self._get_line_text(cells[max(0, start_col):max(0, end_col)])\n\n        chunks = []\n        first_cells = lines[start_line]\n        chunks.append(self._get_line_text(first_cells[max(0, start_col):]))\n        for idx in range(start_line + 1, end_line):\n            chunks.append(self._get_line_text(lines[idx]))\n        last_cells = lines[end_line]\n        chunks.append(self._get_line_text(last_cells[:max(0, end_col)]))\n        return \'\\n\'.join(chunks)'.rstrip(),
    str(terminal_path),
)
terminal = replace_once(
    terminal,
    "        self._screen.put_char(ch, attr=attr)\n",
    "        self._screen.put_char(ch, attr=attr, autowrap=self.modes.autowrap)\n",
    str(terminal_path),
)
terminal = replace_between(
    terminal,
    "    def _erase_line(self, mode):",
    "\n    def _erase_display",
    '    def _erase_line(self, mode):\n        """Apply CSI K without splitting wide glyphs."""\n        active = self._screen._active\n        if mode == 2:\n            active.clear_line()\n            return\n        if mode == 1:\n            active.clear_range(active.cursor_row, 0, active.cursor_col + 1)\n            return\n        active.clear_range(active.cursor_row, active.cursor_col, active.cols)',
    str(terminal_path),
)
terminal = replace_between(
    terminal,
    "        if final == 'P':",
    "        if final == 'J':",
    "        if final == 'P':\n            active.delete_chars(max(1, _num(0, 1)))\n            return\n",
    str(terminal_path),
)
terminal = replace_between(
    terminal,
    "    def _draw_live_cursor",
    "\n    def _draw_selection",
    '    def _draw_live_cursor(self, stdscr, x, y, text_cols, text_rows, start_idx, total_lines, body_attr):\n        if not self.active or self.scrollback_offset != 0 or not self.modes.cursor_visible:\n            return\n        if total_lines <= 0:\n            return\n\n        active = self._screen._active\n        cursor_line_idx = active.cursor_row\n        col = min(active.cursor_col, text_cols - 1)\n\n        if self._alt_screen:\n            row = y + cursor_line_idx\n            if row >= y + text_rows:\n                return\n            line = active.get_row(cursor_line_idx) if cursor_line_idx < active.rows else []\n        else:\n            buffer_first_line_idx = total_lines - active.rows\n            line_idx = buffer_first_line_idx + cursor_line_idx\n            if not (start_idx <= line_idx < start_idx + text_rows):\n                return\n            row = y + (line_idx - start_idx)\n            line = active.get_row(cursor_line_idx)\n\n        if col < len(line) and is_continuation(line[col]):\n            lead = leading_cell_index(line, col)\n            if lead is not None:\n                col = lead\n\n        if col < len(line):\n            ch, attr = line[col]\n        else:\n            ch, attr = \' \', 0\n        if not ch:\n            ch = \' \'\n\n        effective_attr = attr if attr else body_attr\n        if ch == \' \':\n            safe_addstr(stdscr, row, x + col, \'_\', effective_attr | curses.A_BOLD)\n            return\n        safe_addstr(stdscr, row, x + col, ch, effective_attr | curses.A_REVERSE | curses.A_BOLD)'.rstrip(),
    str(terminal_path),
)
terminal = replace_once(
    terminal,
    "            start = max(0, start)\n"
    "            end = min(end, text_cols)\n"
    "            if end <= start:\n",
    "            start = max(0, start)\n"
    "            end = min(end, text_cols)\n"
    "            if start < len(line_cells) and is_continuation(line_cells[start]):\n"
    "                lead = leading_cell_index(line_cells, start)\n"
    "                if lead is not None:\n"
    "                    start = lead\n"
    "            if end <= start:\n",
    str(terminal_path),
)
terminal_path.write_text(terminal, encoding="utf-8", newline="\n")


project_path = ROOT / "pyproject.toml"
project = project_path.read_text(encoding="utf-8")
project = replace_once(
    project,
    "dependencies = [\n"
    "    \"tomli>=2.0; python_version < '3.11'\",\n",
    "dependencies = [\n"
    "    \"tomli>=2.0; python_version < '3.11'\",\n"
    "    \"wcwidth>=0.8.2,<1\",\n",
    str(project_path),
)
project_path.write_text(project, encoding="utf-8", newline="\n")


write("tests/test_terminal_unicode_cells.py", '"""Focused Unicode cell-engine regressions."""\n\nimport unittest\n\nfrom retrotui.core.terminal_cells import (\n    CONTINUATION_TEXT,\n    display_width,\n    leading_cell_index,\n    row_text,\n    sanitize_row,\n)\nfrom retrotui.core.terminal_session import TerminalScreenBuffer\n\n\nclass TerminalUnicodeCellTests(unittest.TestCase):\n    def test_width_helpers_cover_ascii_wide_combining_and_controls(self):\n        self.assertEqual(display_width("A"), 1)\n        self.assertEqual(display_width("\u4f60"), 2)\n        self.assertEqual(display_width("e\\u0301"), 1)\n        self.assertEqual(display_width(""), 0)\n        self.assertEqual(display_width("\\x07"), -1)\n\n    def test_wide_character_reserves_a_continuation_cell(self):\n        buf = TerminalScreenBuffer(2, 4)\n\n        buf.put_char("\u4f60", attr=7)\n\n        self.assertEqual(buf.get_row(0)[:2], [("\u4f60", 7), (CONTINUATION_TEXT, 7)])\n        self.assertEqual(buf.cursor_col, 2)\n        self.assertEqual(row_text(buf.get_row(0)[:2]), "\u4f60")\n\n    def test_combining_mark_merges_without_advancing(self):\n        buf = TerminalScreenBuffer(1, 4)\n\n        buf.put_char("e")\n        buf.put_char("\\u0301")\n\n        self.assertEqual(buf.get_cell(0, 0), ("e\\u0301", 0))\n        self.assertEqual(buf.cursor_col, 1)\n\n    def test_variation_selector_can_expand_previous_cell(self):\n        buf = TerminalScreenBuffer(1, 4)\n\n        buf.put_char("\\u2640")\n        before = buf.cursor_col\n        buf.put_char("\\ufe0f")\n\n        self.assertIn(buf.cursor_col, (before, before + 1))\n        self.assertTrue(buf.get_cell(0, 0)[0].startswith("\\u2640"))\n        self.assertEqual(display_width(buf.get_cell(0, 0)[0]), buf.cursor_col)\n\n    def test_wide_character_wraps_before_last_column(self):\n        buf = TerminalScreenBuffer(2, 3)\n        buf.put_char("a")\n        buf.put_char("b")\n\n        buf.put_char("\u4f60")\n\n        self.assertEqual(buf.cursor_row, 1)\n        self.assertEqual(buf.cursor_col, 2)\n        self.assertEqual(buf.get_row(1)[:2], [("\u4f60", 0), (CONTINUATION_TEXT, 0)])\n\n    def test_autowrap_disabled_clamps_and_overwrites_last_cell(self):\n        buf = TerminalScreenBuffer(1, 3)\n\n        for ch in "abcd":\n            buf.put_char(ch, autowrap=False)\n\n        self.assertEqual(row_text(buf.get_row(0)), "abd")\n        self.assertEqual(buf.cursor_col, 2)\n\n    def test_wide_character_without_room_uses_replacement_when_no_wrap(self):\n        buf = TerminalScreenBuffer(1, 3)\n        buf.put_char("a", autowrap=False)\n        buf.put_char("b", autowrap=False)\n\n        buf.put_char("\u4f60", autowrap=False)\n\n        self.assertEqual(buf.get_cell(0, 2), ("\\ufffd", 0))\n        self.assertEqual(buf.cursor_col, 2)\n\n    def test_backspace_lands_on_wide_leading_cell(self):\n        buf = TerminalScreenBuffer(1, 4)\n        buf.put_char("\u4f60")\n\n        buf.backspace()\n\n        self.assertEqual(buf.cursor_col, 0)\n\n    def test_clear_range_expands_over_wide_glyph(self):\n        buf = TerminalScreenBuffer(1, 4)\n        buf.put_char("\u4f60")\n        buf.put_char("x")\n\n        buf.clear_range(0, 1, 2)\n\n        self.assertEqual(buf.get_row(0)[:2], [(" ", 0), (" ", 0)])\n        self.assertEqual(buf.get_cell(0, 2), ("x", 0))\n\n    def test_delete_chars_never_leaves_an_orphan_tail(self):\n        buf = TerminalScreenBuffer(1, 5)\n        for ch in "\u4f60ab":\n            buf.put_char(ch)\n        buf.set_cursor(0, 0)\n\n        buf.delete_chars(1)\n\n        self.assertEqual(row_text(buf.get_row(0)), "ab   ")\n        self.assertNotEqual(buf.get_cell(0, 0)[0], CONTINUATION_TEXT)\n\n    def test_resize_drops_a_half_wide_glyph(self):\n        buf = TerminalScreenBuffer(1, 3)\n        buf.put_char("a")\n        buf.put_char("\u4f60")\n\n        buf.resize(1, 2)\n\n        self.assertEqual(buf.get_row(0), [("a", 0), (" ", 0)])\n\n    def test_sanitize_row_repairs_orphan_and_extra_continuations(self):\n        row = [("", 3), ("\u4f60", 4), ("", 9), ("", 9)]\n\n        cleaned = sanitize_row(row, default_attr=0)\n\n        self.assertEqual(cleaned[0], (" ", 0))\n        self.assertEqual(cleaned[1:3], [("\u4f60", 4), ("", 4)])\n        self.assertEqual(cleaned[3], (" ", 0))\n        self.assertEqual(leading_cell_index(cleaned, 2), 1)\n\n\nif __name__ == "__main__":\n    unittest.main()\n')

component_path = ROOT / "tests/test_terminal_component.py"
component = component_path.read_text(encoding="utf-8")
component = replace_once(
    component,
    "\n\nif __name__ == \"__main__\":\n",
    "\n\n" + '    def test_dec_autowrap_mode_controls_physical_columns(self):\n        win = self._make_window()\n        win.body_rect = mock.Mock(return_value=(4, 5, 5, 4))\n\n        win._consume_output("\\x1b[?7lABCDE")\n\n        self.assertFalse(win.modes.autowrap)\n        self.assertEqual("".join(ch for ch, _ in win._normal_buf.get_row(0)), "ABCE")\n        self.assertEqual((win._cursor_row, win._cursor_col), (0, 3))\n\n        win._consume_output("\\x1b[?7hFG")\n\n        self.assertTrue(win.modes.autowrap)\n        self.assertEqual("".join(ch for ch, _ in win._normal_buf.get_row(0)), "ABCF")\n        self.assertEqual(win._normal_buf.get_cell(1, 0), ("G", 0))\n\n    def test_selected_text_uses_physical_unicode_cells(self):\n        win = self._make_window()\n        win._scroll_lines = [(("\u4f60", 0), ("", 0), ("x", 0))]\n        win._line_cells = []\n        win.selection_anchor = (0, 0)\n        win.selection_cursor = (0, 2)\n\n        self.assertEqual(win._selected_text(), "\u4f60")\n\n    def test_cursor_on_wide_tail_draws_the_leading_glyph(self):\n        win = self._make_window()\n        win.active = True\n        win._line_cells = [("\u4f60", 0), ("", 0)]\n        win._cursor_col = 1\n        total = win._all_lines_count()\n        start = max(0, total - 7)\n\n        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:\n            win._draw_live_cursor(None, 4, 5, 29, 7, start, total, 0)\n\n        self.assertTrue(safe_addstr.called)\n        draw_call = safe_addstr.call_args\n        self.assertEqual(draw_call.args[2], 4)\n        self.assertEqual(draw_call.args[3], "\u4f60")' + "\n\nif __name__ == \"__main__\":\n",
    str(component_path),
)
component_path.write_text(component, encoding="utf-8", newline="\n")


write("docs/TERMINAL_UNICODE_CELLS.md", '# Terminal Unicode Cell Model\n\nRetroTUI stores terminal output as physical screen columns rather than Python\nstring indices. This document defines the Unicode rules used by the embedded\nterminal after the Unicode-cell hardening slice.\n\n## Cell representation\n\nThe public compatibility shape remains a two-item tuple:\n\n```python\n(text, curses_attribute)\n```\n\nOne narrow glyph occupies one tuple. A glyph whose terminal width is two stores\nits text in the leading tuple and reserves the next physical column with:\n\n```python\n("", same_attribute)\n```\n\nThe empty string is an internal continuation sentinel. It is never copied to the\nclipboard and it is not emitted as output text.\n\n## Width source\n\nRetroTUI uses the Python `wcwidth` package for terminal display width. The\ndependency is bounded below by the release used to implement this model and\nbelow the next major version.\n\nThe engine distinguishes:\n\n- width `1`: ordinary printable cell;\n- width `2`: CJK, wide emoji and other double-column glyphs;\n- width `0`: combining marks, variation selectors and joiners;\n- width `-1`: control or non-printable codepoints, which are ignored by the\n  printable-cell writer.\n\n## Combining and joined sequences\n\nZero-width codepoints append to the preceding leading cell and do not advance\nthe cursor. Variation selectors may expand a previously narrow glyph to two\ncolumns; when that happens, the adjacent column is reserved atomically.\n\nA codepoint following a zero-width joiner is merged into the previous stored\nsequence. This is intentionally a conservative grapheme-like model rather than\na complete terminal implementation of every Unicode segmentation rule.\n\n## Autowrap\n\nDEC private mode `?7h` enables autowrap and `?7l` disables it.\n\nWith autowrap enabled:\n\n- a cursor immediately beyond the right edge wraps before the next printable\n  codepoint;\n- a width-two glyph at the last column wraps before it is written;\n- bottom-edge wrapping scrolls through the normal buffer and its scrollback\n  sink.\n\nWith autowrap disabled:\n\n- the cursor is clamped to the last physical column;\n- later narrow glyphs overwrite that column;\n- a width-two glyph with only one column available is represented by the\n  replacement character instead of creating a half glyph.\n\n## Invariants\n\nThe buffer repairs these invariants after deletion, direct legacy assignment and\nresize operations:\n\n- every continuation has exactly one width-two leading cell immediately before\n  it;\n- a width-two leading cell always has its continuation;\n- clearing or deleting one half clears or removes the whole glyph;\n- shrinking a row never leaves a half-wide glyph;\n- backspace from a continuation lands on the leading column.\n\n## Rendering, cursor and selection\n\nRendering still batches adjacent cells with the same attribute. Concatenating a\nwidth-two leading string and its empty continuation preserves the correct\nphysical width, so later runs begin at the proper column.\n\nSelection coordinates remain physical screen columns. Copying slices the cell\nlist first and only then converts it to text, preventing a wide glyph from\nshifting the selected range. A cursor positioned on a continuation column is\ndrawn over the leading glyph.\n\n## Deliberate limits\n\nThis slice does not add:\n\n- 256-color or true-color SGR;\n- bidi reordering;\n- font fallback;\n- configurable ambiguous-width policy;\n- complete emoji grapheme conformance across every terminal vendor.\n\nThose remain independent capability decisions and must not be advertised by the\nterminfo profile until implemented and tested.\n')

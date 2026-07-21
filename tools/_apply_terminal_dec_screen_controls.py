"""One-shot applicator for DEC screen controls.

The GitHub workflow that invokes this script removes both the workflow and this
file before committing the functional changes.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path: str, start: str, end: str, replacement: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    start_index = text.find(start)
    if start_index < 0:
        raise RuntimeError(f"{path}: start marker not found: {start!r}")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"{path}: end marker not found: {end!r}")
    target.write_text(
        text[:start_index] + replacement + text[end_index:],
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Runtime DEC modes and capability declaration.
# ---------------------------------------------------------------------------
replace_once(
    "retrotui/core/terminal_modes.py",
    """    cursor_visibility: bool = True\n    sgr_mouse: bool = True\n""",
    """    cursor_visibility: bool = True\n    scroll_regions: bool = True\n    origin_mode: bool = True\n    cursor_save_restore: bool = True\n    insert_delete: bool = True\n    sgr_mouse: bool = True\n""",
)
replace_once(
    "retrotui/core/terminal_modes.py",
    """    bracketed_paste: bool = False\n    autowrap: bool = True\n""",
    """    bracketed_paste: bool = False\n    autowrap: bool = True\n    origin_mode: bool = False\n""",
)
replace_once(
    "retrotui/core/terminal_modes.py",
    """        self.bracketed_paste = False\n        self.autowrap = True\n""",
    """        self.bracketed_paste = False\n        self.autowrap = True\n        self.origin_mode = False\n""",
)
replace_once(
    "retrotui/core/terminal_modes.py",
    """        if mode == 7:\n            self.autowrap = enabled\n            return True\n        return False\n""",
    """        if mode == 7:\n            self.autowrap = enabled\n            return True\n        if mode == 6:\n            self.origin_mode = enabled\n            return True\n        return False\n""",
)


# ---------------------------------------------------------------------------
# Unicode-aware screen buffer regions and editing primitives.
# ---------------------------------------------------------------------------
replace_once(
    "retrotui/core/terminal_session.py",
    """        \"_default_attr\",\n        \"_scroll_sink\",\n    )\n""",
    """        \"_default_attr\",\n        \"_scroll_sink\",\n        \"_scroll_top\",\n        \"_scroll_bottom\",\n        \"_saved_cursor\",\n    )\n""",
)
replace_once(
    "retrotui/core/terminal_session.py",
    """        self._cursor_col = 0\n        self._scroll_sink = None\n""",
    """        self._cursor_col = 0\n        self._scroll_sink = None\n        self._scroll_top = 0\n        self._scroll_bottom = rows - 1\n        self._saved_cursor = (0, 0)\n""",
)
replace_once(
    "retrotui/core/terminal_session.py",
    """    @property\n    def cursor_col(self):\n        return self._cursor_col\n\n    def set_cursor(self, row, col):\n""",
    """    @property\n    def cursor_col(self):\n        return self._cursor_col\n\n    @property\n    def scroll_top(self):\n        return self._scroll_top\n\n    @property\n    def scroll_bottom(self):\n        return self._scroll_bottom\n\n    def set_scroll_region(self, top=0, bottom=None):\n        \"\"\"Set inclusive scrolling margins and report whether they are valid.\"\"\"\n        if bottom is None:\n            bottom = self.rows - 1\n        top = max(0, min(self.rows - 1, int(top)))\n        bottom = max(0, min(self.rows - 1, int(bottom)))\n        if top >= bottom:\n            return False\n        self._scroll_top = top\n        self._scroll_bottom = bottom\n        return True\n\n    def reset_scroll_region(self):\n        self._scroll_top = 0\n        self._scroll_bottom = self.rows - 1\n\n    def save_cursor(self):\n        self._saved_cursor = (self._cursor_row, self._cursor_col)\n\n    def restore_cursor(self):\n        row, col = self._saved_cursor\n        self.set_cursor(row, col)\n\n    def set_cursor(self, row, col):\n""",
)
replace_between(
    "retrotui/core/terminal_session.py",
    "    def line_feed(self):\n",
    "    def backspace(self):\n",
    """    def line_feed(self):\n        \"\"\"Advance one row, scrolling only the active DEC region.\"\"\"\n        if self._scroll_top <= self._cursor_row <= self._scroll_bottom:\n            if self._cursor_row == self._scroll_bottom:\n                self.scroll_up(1)\n            else:\n                self._cursor_row += 1\n            return\n        if self._cursor_row < self.rows - 1:\n            self._cursor_row += 1\n\n    def reverse_index(self):\n        \"\"\"Move upward, scrolling the active DEC region downward at its top.\"\"\"\n        if self._scroll_top <= self._cursor_row <= self._scroll_bottom:\n            if self._cursor_row == self._scroll_top:\n                self.scroll_down(1)\n            else:\n                self._cursor_row -= 1\n            return\n        if self._cursor_row > 0:\n            self._cursor_row -= 1\n\n""",
)
replace_between(
    "retrotui/core/terminal_session.py",
    "    def scroll_up(self, count=1):\n",
    "    def delete_chars(self, count=1):\n",
    """    def scroll_up(self, count=1):\n        \"\"\"Scroll the active DEC region upward by ``count`` rows.\"\"\"\n        if count <= 0 or self.rows <= 0:\n            return\n        top, bottom = self._scroll_top, self._scroll_bottom\n        height = bottom - top + 1\n        for _ in range(min(count, height)):\n            scrolled_off = self._grid.pop(top)\n            self._grid.insert(bottom, self._blank_row())\n            sink = self._scroll_sink\n            if top == 0 and bottom == self.rows - 1 and sink is not None:\n                try:\n                    sink(scrolled_off)\n                except Exception:\n                    pass\n\n    def set_scroll_sink(self, sink):\n        self._scroll_sink = sink\n\n    def scroll_down(self, count=1):\n        \"\"\"Scroll the active DEC region downward by ``count`` rows.\"\"\"\n        if count <= 0 or self.rows <= 0:\n            return\n        top, bottom = self._scroll_top, self._scroll_bottom\n        height = bottom - top + 1\n        for _ in range(min(count, height)):\n            self._grid.pop(bottom)\n            self._grid.insert(top, self._blank_row())\n\n    def insert_line(self, count=1):\n        \"\"\"Insert rows at the cursor inside the active scroll region.\"\"\"\n        if count <= 0 or not self._scroll_top <= self._cursor_row <= self._scroll_bottom:\n            return\n        available = self._scroll_bottom - self._cursor_row + 1\n        for _ in range(min(count, available)):\n            self._grid.insert(self._cursor_row, self._blank_row())\n            self._grid.pop(self._scroll_bottom + 1)\n\n    def delete_line(self, count=1):\n        \"\"\"Delete rows at the cursor inside the active scroll region.\"\"\"\n        if count <= 0 or not self._scroll_top <= self._cursor_row <= self._scroll_bottom:\n            return\n        available = self._scroll_bottom - self._cursor_row + 1\n        for _ in range(min(count, available)):\n            self._grid.pop(self._cursor_row)\n            self._grid.insert(self._scroll_bottom, self._blank_row())\n\n    def insert_chars(self, count=1):\n        \"\"\"Insert blank physical cells without splitting a wide glyph.\"\"\"\n        count = max(1, int(count))\n        row = self._cursor_row\n        start = min(self.cols - 1, self._cursor_col)\n        line = self._grid[row]\n        if is_continuation(line[start]):\n            lead = leading_cell_index(line, start)\n            if lead is not None:\n                start = lead\n        count = min(count, self.cols - start)\n        line[start:start] = [self._blank_cell() for _ in range(count)]\n        self._grid[row] = sanitize_row(line[:self.cols], self._default_attr)\n\n    def erase_chars(self, count=1):\n        \"\"\"Erase physical cells at the cursor without orphaning wide tails.\"\"\"\n        count = max(1, int(count))\n        self.clear_range(\n            self._cursor_row,\n            self._cursor_col,\n            min(self.cols, self._cursor_col + count),\n        )\n\n""",
)
replace_between(
    "retrotui/core/terminal_session.py",
    "    def resize(self, rows, cols):\n",
    "class TerminalScreen:\n",
    """    def resize(self, rows, cols):\n        \"\"\"Resize while preserving cursor, margins and Unicode cell invariants.\"\"\"\n        rows = max(1, int(rows))\n        cols = max(1, int(cols))\n        old_rows = self.rows\n        old_cols = self.cols\n        region_was_full = self._scroll_top == 0 and self._scroll_bottom == old_rows - 1\n        new_grid = [\n            [(\" \", self._default_attr) for _ in range(cols)] for _ in range(rows)\n        ]\n        common_rows = min(rows, self.rows)\n        common_cols = min(cols, old_cols)\n        for row in range(common_rows):\n            new_grid[row][:common_cols] = self._grid[row][:common_cols]\n            new_grid[row] = sanitize_row(new_grid[row], self._default_attr)\n        self._grid = new_grid\n        self.rows = rows\n        self.cols = cols\n        self._cursor_row = min(self._cursor_row, rows - 1)\n        self._cursor_col = min(self._cursor_col, cols - 1)\n\n        if region_was_full:\n            self.reset_scroll_region()\n        else:\n            self._scroll_top = min(self._scroll_top, rows - 1)\n            self._scroll_bottom = min(self._scroll_bottom, rows - 1)\n            if self._scroll_top >= self._scroll_bottom:\n                self.reset_scroll_region()\n\n        saved_row, saved_col = self._saved_cursor\n        self._saved_cursor = (\n            min(saved_row, rows - 1),\n            min(saved_col, cols - 1),\n        )\n\n\n""",
)


# ---------------------------------------------------------------------------
# Terminal-window CSI/DEC integration.
# ---------------------------------------------------------------------------
replace_once(
    "retrotui/apps/terminal.py",
    """        self.capabilities = DEFAULT_TERMINAL_CAPABILITIES\n        self.modes = TerminalModes()\n""",
    """        self.capabilities = DEFAULT_TERMINAL_CAPABILITIES\n        self.modes = TerminalModes()\n        self._normal_cursor_before_alt = None\n""",
)
replace_between(
    "retrotui/apps/terminal.py",
    "    def _append_newline(self):\n",
    "    def _erase_line(self, mode):\n",
    """    def _append_newline(self):\n        \"\"\"Advance using LF+CR and let the buffer own scrollback capture.\"\"\"\n        self._screen.line_feed()\n        self._screen.carriage_return()\n\n    def _set_alt_screen_mode(self, mode, enabled):\n        \"\"\"Apply alternate-screen modes, including ?1049 cursor restore.\"\"\"\n        self.scrollback_offset = 0\n        if mode == 1049:\n            if enabled:\n                if not self._screen.alt_screen:\n                    self._normal_cursor_before_alt = (\n                        self._normal_buf.cursor_row,\n                        self._normal_buf.cursor_col,\n                    )\n                self._alt_buf.clear_screen(\"all\")\n                self._alt_buf.reset_scroll_region()\n                self._screen.set_alt_screen(True)\n                self._screen.set_cursor(0, 0)\n            else:\n                self._screen.set_alt_screen(False)\n                if self._normal_cursor_before_alt is not None:\n                    self._normal_buf.set_cursor(*self._normal_cursor_before_alt)\n                    self._normal_cursor_before_alt = None\n            return\n        self._screen.set_alt_screen(bool(enabled))\n\n    def _cursor_vertical_bounds(self, active):\n        if self.modes.origin_mode:\n            return active.scroll_top, active.scroll_bottom\n        return 0, active.rows - 1\n\n    def _home_cursor(self, active):\n        row = active.scroll_top if self.modes.origin_mode else 0\n        active.set_cursor(row, 0)\n\n""",
)
replace_between(
    "retrotui/apps/terminal.py",
    "    def _apply_csi(self, params, final):\n",
    "    def _consume_output(self, text):\n",
    """    def _apply_csi(self, params, final):\n        \"\"\"Handle CSI screen controls and DEC private modes.\"\"\"\n        def _num(index, default):\n            if index >= len(params):\n                return default\n            return params[index]\n\n        private = getattr(params, \"private\", \"\")\n        if final in ('h', 'l'):\n            enabled = final == 'h'\n            if private not in ('', '?'):\n                return\n            mode_values = list(params) or [0]\n            for mode in mode_values:\n                if mode in (1049, 1047, 47):\n                    self._set_alt_screen_mode(mode, enabled)\n                elif mode in _MOUSE_REPORT_MODES:\n                    if enabled:\n                        self._mouse_modes.add(mode)\n                    else:\n                        self._mouse_modes.discard(mode)\n                elif mode == 6:\n                    self.modes.set_private_mode(mode, enabled)\n                    self._home_cursor(self._screen._active)\n                else:\n                    self.modes.set_private_mode(mode, enabled)\n            return\n\n        active = self._screen._active\n        rows, cols = active.rows, active.cols\n        top, bottom = self._cursor_vertical_bounds(active)\n\n        if final == 'A':\n            active.set_cursor(max(top, active.cursor_row - max(1, _num(0, 1))), active.cursor_col)\n            return\n        if final == 'B':\n            active.set_cursor(min(bottom, active.cursor_row + max(1, _num(0, 1))), active.cursor_col)\n            return\n        if final == 'D':\n            active.set_cursor(active.cursor_row, max(0, active.cursor_col - max(1, _num(0, 1))))\n            return\n        if final == 'C':\n            active.set_cursor(active.cursor_row, min(cols - 1, active.cursor_col + max(1, _num(0, 1))))\n            return\n        if final == 'G':\n            active.set_cursor(active.cursor_row, min(cols - 1, max(0, _num(0, 1) - 1)))\n            return\n        if final == 'd':\n            row = max(0, _num(0, 1) - 1)\n            if self.modes.origin_mode:\n                row += active.scroll_top\n            active.set_cursor(min(bottom, max(top, row)), active.cursor_col)\n            return\n        if final in ('H', 'f'):\n            row = max(0, _num(0, 1) - 1)\n            if self.modes.origin_mode:\n                row += active.scroll_top\n            row = min(bottom, max(top, row))\n            col = max(0, min(cols - 1, _num(1, 1) - 1))\n            active.set_cursor(row, col)\n            return\n        if final == 'r' and private == '':\n            region_top = max(0, _num(0, 1) - 1)\n            region_bottom = min(rows - 1, max(0, _num(1, rows) - 1))\n            if active.set_scroll_region(region_top, region_bottom):\n                self._home_cursor(active)\n            return\n        if final == 's' and private == '':\n            active.save_cursor()\n            return\n        if final == 'u' and private == '':\n            active.restore_cursor()\n            return\n        if final == 'K':\n            self._erase_line(_num(0, 0))\n            return\n        if final == '@':\n            active.insert_chars(max(1, _num(0, 1)))\n            return\n        if final == 'P':\n            active.delete_chars(max(1, _num(0, 1)))\n            return\n        if final == 'X':\n            active.erase_chars(max(1, _num(0, 1)))\n            return\n        if final == 'L':\n            active.insert_line(max(1, _num(0, 1)))\n            return\n        if final == 'M':\n            active.delete_line(max(1, _num(0, 1)))\n            return\n        if final == 'J':\n            self._erase_display(_num(0, 0))\n            return\n\n""",
)
replace_once(
    "retrotui/apps/terminal.py",
    """        self._normal_buf.clear_screen(\"all\")\n        self._alt_buf.clear_screen(\"all\")\n        self._screen.set_alt_screen(False)\n""",
    """        self._normal_buf.clear_screen(\"all\")\n        self._alt_buf.clear_screen(\"all\")\n        self._normal_buf.reset_scroll_region()\n        self._alt_buf.reset_scroll_region()\n        self._normal_cursor_before_alt = None\n        self._screen.set_alt_screen(False)\n""",
)


# ---------------------------------------------------------------------------
# Honest terminfo advertisement for newly implemented controls.
# ---------------------------------------------------------------------------
replace_once(
    "retrotui/terminfo/retrotui.src",
    """    dch1=\\E[P,\n    dch=\\E[%p1%dP,\n""",
    """    dch1=\\E[P,\n    dch=\\E[%p1%dP,\n    ich1=\\E[@,\n    ich=\\E[%p1%d@,\n    ech=\\E[%p1%dX,\n    il1=\\E[L,\n    il=\\E[%p1%dL,\n    dl1=\\E[M,\n    dl=\\E[%p1%dM,\n    csr=\\E[%i%p1%d;%p2%dr,\n    sc=\\E[s,\n    rc=\\E[u,\n""",
)


# ---------------------------------------------------------------------------
# Focused regressions.
# ---------------------------------------------------------------------------
(ROOT / "tests/test_terminal_dec_screen_controls.py").write_text(
    '''"""Focused tests for DEC screen regions and editing controls."""\n\nimport unittest\n\nfrom retrotui.core.terminal_modes import TerminalModes\nfrom retrotui.core.terminal_session import TerminalScreenBuffer\n\n\ndef _fill_rows(buf):\n    for row in range(buf.rows):\n        token = str(row)\n        buf._grid[row] = [(token, 0) for _ in range(buf.cols)]\n\n\nclass TerminalDecScreenBufferTests(unittest.TestCase):\n    def test_scroll_region_line_feed_preserves_rows_outside_margins(self):\n        buf = TerminalScreenBuffer(5, 4)\n        _fill_rows(buf)\n        captured = []\n        buf.set_scroll_sink(captured.append)\n        self.assertTrue(buf.set_scroll_region(1, 3))\n        buf.set_cursor(3, 0)\n\n        buf.line_feed()\n\n        self.assertEqual(buf.get_row(0), [("0", 0)] * 4)\n        self.assertEqual(buf.get_row(1), [("2", 0)] * 4)\n        self.assertEqual(buf.get_row(2), [("3", 0)] * 4)\n        self.assertEqual(buf.get_row(3), [(" ", 0)] * 4)\n        self.assertEqual(buf.get_row(4), [("4", 0)] * 4)\n        self.assertEqual(captured, [])\n\n    def test_full_screen_scroll_still_emits_scrollback(self):\n        buf = TerminalScreenBuffer(3, 3)\n        _fill_rows(buf)\n        captured = []\n        buf.set_scroll_sink(captured.append)\n        buf.set_cursor(2, 0)\n\n        buf.line_feed()\n\n        self.assertEqual(captured, [[("0", 0)] * 3])\n        self.assertEqual(buf.get_row(2), [(" ", 0)] * 3)\n\n    def test_reverse_index_scrolls_region_down(self):\n        buf = TerminalScreenBuffer(5, 3)\n        _fill_rows(buf)\n        buf.set_scroll_region(1, 3)\n        buf.set_cursor(1, 0)\n\n        buf.reverse_index()\n\n        self.assertEqual(buf.get_row(0), [("0", 0)] * 3)\n        self.assertEqual(buf.get_row(1), [(" ", 0)] * 3)\n        self.assertEqual(buf.get_row(2), [("1", 0)] * 3)\n        self.assertEqual(buf.get_row(3), [("2", 0)] * 3)\n        self.assertEqual(buf.get_row(4), [("4", 0)] * 3)\n\n    def test_insert_and_delete_lines_are_region_scoped(self):\n        buf = TerminalScreenBuffer(5, 3)\n        _fill_rows(buf)\n        buf.set_scroll_region(1, 3)\n        buf.set_cursor(2, 0)\n\n        buf.insert_line()\n        self.assertEqual(buf.get_row(2), [(" ", 0)] * 3)\n        self.assertEqual(buf.get_row(3), [("2", 0)] * 3)\n        self.assertEqual(buf.get_row(4), [("4", 0)] * 3)\n\n        buf.delete_line()\n        self.assertEqual(buf.get_row(2), [("2", 0)] * 3)\n        self.assertEqual(buf.get_row(3), [(" ", 0)] * 3)\n        self.assertEqual(buf.get_row(4), [("4", 0)] * 3)\n\n    def test_insert_and_erase_chars_preserve_wide_cell_invariants(self):\n        buf = TerminalScreenBuffer(1, 7)\n        for ch in "A界B":\n            buf.put_char(ch)\n        buf.set_cursor(0, 1)\n\n        buf.insert_chars(1)\n\n        self.assertEqual(buf.get_cell(0, 1), (" ", 0))\n        self.assertEqual(buf.get_cell(0, 2), ("界", 0))\n        self.assertEqual(buf.get_cell(0, 3), ("", 0))\n        buf.set_cursor(0, 3)\n        buf.erase_chars(1)\n        self.assertEqual(buf.get_cell(0, 2), (" ", 0))\n        self.assertEqual(buf.get_cell(0, 3), (" ", 0))\n\n    def test_saved_cursor_and_region_survive_resize_safely(self):\n        buf = TerminalScreenBuffer(6, 8)\n        buf.set_scroll_region(1, 4)\n        buf.set_cursor(4, 7)\n        buf.save_cursor()\n        buf.resize(4, 5)\n\n        self.assertEqual((buf.scroll_top, buf.scroll_bottom), (1, 3))\n        buf.set_cursor(0, 0)\n        buf.restore_cursor()\n        self.assertEqual((buf.cursor_row, buf.cursor_col), (3, 4))\n\n    def test_origin_mode_resets_with_other_dec_modes(self):\n        modes = TerminalModes()\n        self.assertTrue(modes.set_private_mode(6, True))\n        self.assertTrue(modes.origin_mode)\n        modes.reset()\n        self.assertFalse(modes.origin_mode)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''',
    encoding="utf-8",
)

component_path = ROOT / "tests/test_terminal_component.py"
component_text = component_path.read_text(encoding="utf-8")
marker = '\n\nif __name__ == "__main__":\n    unittest.main()\n'
if component_text.count(marker) != 1:
    raise RuntimeError("terminal component test footer marker changed")
component_tests = '''\n    def test_dec_scroll_region_origin_and_cursor_save_restore(self):\n        win = self._make_window()\n        win.body_rect = mock.Mock(return_value=(4, 5, 8, 6))\n        win._sync_screen_size()\n\n        win._consume_output("\\x1b[2;4r\\x1b[?6h\\x1b[2;3H")\n        active = win._screen._active\n        self.assertEqual((active.scroll_top, active.scroll_bottom), (1, 3))\n        self.assertEqual((active.cursor_row, active.cursor_col), (2, 2))\n\n        win._consume_output("\\x1b[s\\x1b[1;1H\\x1b[u")\n        self.assertEqual((active.cursor_row, active.cursor_col), (2, 2))\n\n        win._consume_output("\\x1b[?6l")\n        self.assertFalse(win.modes.origin_mode)\n        self.assertEqual((active.cursor_row, active.cursor_col), (0, 0))\n\n    def test_csi_insert_erase_and_region_line_operations(self):\n        win = self._make_window()\n        win.body_rect = mock.Mock(return_value=(4, 5, 7, 6))\n        win._sync_screen_size()\n        active = win._screen._active\n        for row in range(active.rows):\n            active._grid[row] = [(str(row), 0) for _ in range(active.cols)]\n\n        active.set_scroll_region(1, 3)\n        active.set_cursor(2, 0)\n        win._apply_csi([1], "L")\n        self.assertEqual(active.get_row(2), [(" ", 0)] * active.cols)\n        self.assertEqual(active.get_row(3), [("2", 0)] * active.cols)\n\n        win._apply_csi([1], "M")\n        self.assertEqual(active.get_row(2), [("2", 0)] * active.cols)\n\n        active._grid[0] = [(ch, 0) for ch in "ABCDE "]\n        active.set_cursor(0, 1)\n        win._apply_csi([1], "@")\n        self.assertEqual("".join(ch for ch, _ in active.get_row(0)), "A ABCD")\n        win._apply_csi([2], "X")\n        self.assertEqual("".join(ch for ch, _ in active.get_row(0)), "A  BCD")\n\n    def test_dec_1049_restores_normal_cursor_and_isolates_alt_screen(self):\n        win = self._make_window()\n        win._normal_buf.set_cursor(2, 3)\n\n        win._consume_output("\\x1b[?1049h")\n        self.assertTrue(win._alt_screen)\n        self.assertEqual((win._screen.cursor_row, win._screen.cursor_col), (0, 0))\n        win._consume_output("X")\n        self.assertEqual(win._alt_buf.get_cell(0, 0)[0], "X")\n\n        win._consume_output("\\x1b[?1049l")\n        self.assertFalse(win._alt_screen)\n        self.assertEqual((win._normal_buf.cursor_row, win._normal_buf.cursor_col), (2, 3))\n        self.assertNotEqual(win._normal_buf.get_cell(0, 0)[0], "X")\n'''
component_path.write_text(
    component_text.replace(marker, component_tests + marker, 1),
    encoding="utf-8",
)


# ---------------------------------------------------------------------------
# Operational documentation.
# ---------------------------------------------------------------------------
(ROOT / "docs/TERMINAL_DEC_SCREEN_CONTROLS.md").write_text(
    '''# Terminal DEC screen controls\n\nThis cut adds the first region-aware VT screen operations on top of the Unicode\nphysical-cell model.\n\n## Implemented\n\n- `DECSTBM` (`CSI top;bottom r`) with independent margins per normal and\n  alternate screen buffer.\n- `DECOM` origin mode (`CSI ? 6 h` / `CSI ? 6 l`). Cursor addressing becomes\n  relative to the top margin while origin mode is enabled.\n- CSI cursor save and restore (`CSI s` / `CSI u`).\n- Insert character (`ICH`, `CSI Ps @`).\n- Delete character (`DCH`, `CSI Ps P`).\n- Erase character (`ECH`, `CSI Ps X`).\n- Insert line (`IL`, `CSI Ps L`).\n- Delete line (`DL`, `CSI Ps M`).\n- `?1049` saves the normal-screen cursor, clears and homes the alternate\n  screen, then restores the normal cursor on exit.\n- Resize preserves valid margins and clamps saved cursor coordinates.\n\n## Unicode safety\n\nCharacter editing uses physical columns. Operations that intersect the tail of\na double-width glyph expand to the leading cell so no orphan continuation is\nleft in the row. Resizing sanitizes rows after clipping.\n\n## Scrollback ownership\n\nOnly a full-screen upward scroll emits a row into normal-screen scrollback. A\npartial DEC scrolling region moves rows inside the visible grid and never\ncreates history entries.\n\n## Deliberate follow-ups\n\nThe following remain separate work:\n\n- `IND`, `RI` and `NEL` ESC dispatch;\n- configurable tab stops;\n- device-status and cursor-position reports;\n- selective erase/protected cells;\n- 256-color and true-color SGR.\n''',
    encoding="utf-8",
)


# Remove one-shot machinery before the workflow commits the functional diff.
(ROOT / "tools/_apply_terminal_dec_screen_controls.py").unlink(missing_ok=True)
(ROOT / ".github/workflows/apply-terminal-dec-screen-controls.yml").unlink(missing_ok=True)

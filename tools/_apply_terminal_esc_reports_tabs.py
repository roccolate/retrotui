"""One-shot applicator for ESC dispatch, terminal reports and tab stops."""

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


# Parser: preserve single-byte ESC commands as explicit events.
replace_once(
    "retrotui/core/ansi.py",
    """          ('CSI', final_char, params_list)\n          ('OSC', ...) # Not fully implemented, just consumed\n          ('CONTROL', char) # For \\n, \\r, \\b, \\t\n""",
    """          ('CSI', final_char, params_list)\n          ('ESC', final_char, 0) # Single-byte ESC dispatch\n          ('OSC', ...) # Not fully implemented, just consumed\n          ('CONTROL', char) # For \\n, \\r, \\b, \\t\n""",
)
replace_once(
    "retrotui/core/ansi.py",
    """                elif ch == '(':\n                    self.state = 'CHARSET'\n                else:\n                    # Fallback for unhandled ESC sequence or immediate char\n                    self.state = 'TEXT' # Reset and treat as text or ignore?\n                    # Properly we should handle ESC c etc.\n""",
    """                elif ch == '(':\n                    self.state = 'CHARSET'\n                elif ch in ('D', 'E', 'M', 'H', '7', '8'):\n                    self.state = 'TEXT'\n                    yield ('ESC', ch, 0)\n                else:\n                    # Unknown single-byte ESC commands are consumed safely.\n                    self.state = 'TEXT'\n""",
)

# Honest capability declarations.
replace_once(
    "retrotui/core/terminal_modes.py",
    """    insert_delete: bool = True\n    sgr_mouse: bool = True\n""",
    """    insert_delete: bool = True\n    esc_indexing: bool = True\n    tab_stops: bool = True\n    device_status_reports: bool = True\n    sgr_mouse: bool = True\n""",
)

# Terminal-wide tab state is initialized from the active viewport width.
replace_once(
    "retrotui/apps/terminal.py",
    """        text_cols, text_rows = self._text_area_size()\n        self._scrollback: deque = deque(maxlen=self.max_scrollback)\n""",
    """        text_cols, text_rows = self._text_area_size()\n        self._tab_stops = set(range(8, text_cols, 8))\n        self._tab_stop_extent = text_cols\n        self._tab_stops_cleared_all = False\n        self._scrollback: deque = deque(maxlen=self.max_scrollback)\n""",
)
replace_once(
    "retrotui/apps/terminal.py",
    """    def _sync_screen_size(self):\n        \"\"\"Resize both buffers to match the current text area dimensions.\"\"\"\n        text_cols, text_rows = self._text_area_size()\n        if (\n            self._normal_buf.rows == text_rows\n            and self._normal_buf.cols == text_cols\n        ):\n            return\n        self._normal_buf.resize(text_rows, text_cols)\n        self._alt_buf.resize(text_rows, text_cols)\n""",
    """    def _sync_screen_size(self):\n        \"\"\"Resize both buffers and keep tab stops valid for the viewport.\"\"\"\n        text_cols, text_rows = self._text_area_size()\n        self._sync_tab_stops(text_cols)\n        if (\n            self._normal_buf.rows == text_rows\n            and self._normal_buf.cols == text_cols\n        ):\n            return\n        self._normal_buf.resize(text_rows, text_cols)\n        self._alt_buf.resize(text_rows, text_cols)\n""",
)

# Add terminal-wide tab handling, ESC dispatch and report responses.
replace_once(
    "retrotui/apps/terminal.py",
    """    def _home_cursor(self, active):\n        row = active.scroll_top if self.modes.origin_mode else 0\n        active.set_cursor(row, 0)\n\n    def _erase_line(self, mode):\n""",
    """    def _home_cursor(self, active):\n        row = active.scroll_top if self.modes.origin_mode else 0\n        active.set_cursor(row, 0)\n\n    def _reset_tab_stops(self, cols=None):\n        \"\"\"Restore default horizontal stops every eight physical columns.\"\"\"\n        if cols is None:\n            cols = self._screen.cols\n        cols = max(1, int(cols))\n        self._tab_stops = set(range(8, cols, 8))\n        self._tab_stop_extent = cols\n        self._tab_stops_cleared_all = False\n\n    def _sync_tab_stops(self, cols):\n        \"\"\"Clip stops on shrink and seed new default columns on expansion.\"\"\"\n        cols = max(1, int(cols))\n        previous = max(1, int(self._tab_stop_extent))\n        self._tab_stops = {stop for stop in self._tab_stops if 0 <= stop < cols}\n        if cols > previous and not self._tab_stops_cleared_all:\n            first = max(8, ((previous + 7) // 8) * 8)\n            self._tab_stops.update(range(first, cols, 8))\n        self._tab_stop_extent = cols\n\n    def _set_tab_stop(self):\n        active = self._screen._active\n        if 0 <= active.cursor_col < active.cols:\n            self._tab_stops.add(active.cursor_col)\n\n    def _clear_tab_stop(self, mode=0):\n        active = self._screen._active\n        if mode in (0, None):\n            self._tab_stops.discard(active.cursor_col)\n        elif mode == 3:\n            self._tab_stops.clear()\n            self._tab_stops_cleared_all = True\n\n    def _tab_forward(self, count=1):\n        active = self._screen._active\n        col = active.cursor_col\n        for _ in range(max(1, int(count))):\n            candidates = [stop for stop in self._tab_stops if col < stop < active.cols]\n            col = min(candidates) if candidates else active.cols - 1\n        active.set_cursor(active.cursor_row, col)\n\n    def _tab_backward(self, count=1):\n        active = self._screen._active\n        col = active.cursor_col\n        for _ in range(max(1, int(count))):\n            candidates = [stop for stop in self._tab_stops if 0 <= stop < col]\n            col = max(candidates) if candidates else 0\n        active.set_cursor(active.cursor_row, col)\n\n    def _send_terminal_response(self, payload):\n        \"\"\"Write a protocol response to the existing child without UI side effects.\"\"\"\n        session = self._session\n        if session is None or not getattr(session, 'running', False):\n            return False\n        try:\n            session.write(payload)\n        except (OSError, RuntimeError) as exc:\n            self._set_session_error(exc)\n            return False\n        return True\n\n    def _apply_esc(self, final):\n        \"\"\"Apply supported single-byte ESC format effectors.\"\"\"\n        active = self._screen._active\n        if final == 'D':\n            active.line_feed()\n        elif final == 'E':\n            active.line_feed()\n            active.carriage_return()\n        elif final == 'M':\n            active.reverse_index()\n        elif final == 'H':\n            self._set_tab_stop()\n        elif final == '7':\n            active.save_cursor()\n        elif final == '8':\n            active.restore_cursor()\n\n    def _apply_dsr(self, params, private=''):\n        \"\"\"Answer ANSI/DEC status and cursor-position requests.\"\"\"\n        if private not in ('', '?'):\n            return\n        request = params[0] if params else 0\n        prefix = '?' if private == '?' else ''\n        if request == 5:\n            self._send_terminal_response(f'\\x1b[{prefix}0n')\n            return\n        if request != 6:\n            return\n        active = self._screen._active\n        if self.modes.origin_mode:\n            row = active.cursor_row - active.scroll_top + 1\n        else:\n            row = active.cursor_row + 1\n        col = active.cursor_col + 1\n        self._send_terminal_response(f'\\x1b[{prefix}{row};{col}R')\n\n    def _erase_line(self, mode):\n""",
)

# CSI tab and report controls.
replace_once(
    "retrotui/apps/terminal.py",
    """        if final == 'G':\n            active.set_cursor(active.cursor_row, min(cols - 1, max(0, _num(0, 1) - 1)))\n            return\n        if final == 'd':\n""",
    """        if final == 'G':\n            active.set_cursor(active.cursor_row, min(cols - 1, max(0, _num(0, 1) - 1)))\n            return\n        if final == 'I':\n            self._tab_forward(max(1, _num(0, 1)))\n            return\n        if final == 'Z':\n            self._tab_backward(max(1, _num(0, 1)))\n            return\n        if final == 'g' and private == '':\n            self._clear_tab_stop(_num(0, 0))\n            return\n        if final == 'n':\n            self._apply_dsr(params, private)\n            return\n        if final == 'd':\n""",
)

# HT now moves to a stop without mutating cells; parser ESC events are dispatched.
replace_once(
    "retrotui/apps/terminal.py",
    """                elif data == '\\t':\n                    spaces = 8 - (self._screen.cursor_col % 8)\n                    for _ in range(spaces):\n                        self._write_char(' ', self.ansi.attr)\n            elif kind == 'CSI':\n                # data is final char, attr is params list\n                self._apply_csi(attr, data)\n""",
    """                elif data == '\\t':\n                    self._tab_forward()\n            elif kind == 'ESC':\n                self._apply_esc(data)\n            elif kind == 'CSI':\n                # data is final char, attr is params list\n                self._apply_csi(attr, data)\n""",
)
replace_once(
    "retrotui/apps/terminal.py",
    """        self._normal_cursor_before_alt = None\n        self._screen.set_alt_screen(False)\n        self._screen.set_cursor(0, 0)\n""",
    """        self._normal_cursor_before_alt = None\n        self._screen.set_alt_screen(False)\n        self._screen.set_cursor(0, 0)\n        self._reset_tab_stops(self._screen.cols)\n""",
)

# Terminfo: advertise only sequences implemented by this cut.
replace_once(
    "retrotui/terminfo/retrotui.src",
    """    ind=^J,\n    nel=^M^J,\n    ht=^I,\n""",
    """    ind=\\ED,\n    ri=\\EM,\n    nel=\\EE,\n    ht=^I,\n    hts=\\EH,\n    tbc=\\E[3g,\n    cbt=\\E[Z,\n""",
)

# Parser regressions.
ansi_path = ROOT / "tests/test_ansi_basic.py"
ansi_text = ansi_path.read_text(encoding="utf-8")
ansi_marker = "\n\nif __name__ == '__main__':\n    unittest.main()\n"
if ansi_text.count(ansi_marker) != 1:
    raise RuntimeError("tests/test_ansi_basic.py footer marker changed")
ansi_tests = '''
    def test_single_byte_esc_dispatch_and_multichunk_state(self):
        state = AnsiStateMachine()
        events = list(state.parse_chunk("\\x1bD\\x1bE\\x1bM\\x1bH\\x1b7\\x1b8"))
        self.assertEqual(
            [(kind, data) for kind, data, _ in events],
            [("ESC", value) for value in "DEMH78"],
        )

        split = AnsiStateMachine()
        self.assertEqual(list(split.parse_chunk("\\x1b")), [])
        self.assertEqual(list(split.parse_chunk("M")), [("ESC", "M", 0)])
'''
ansi_path.write_text(
    ansi_text.replace(ansi_marker, ansi_tests + ansi_marker, 1),
    encoding="utf-8",
)

# Terminal integration regressions.
component_path = ROOT / "tests/test_terminal_component.py"
component_text = component_path.read_text(encoding="utf-8")
component_marker = "\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
if component_text.count(component_marker) != 1:
    raise RuntimeError("tests/test_terminal_component.py footer marker changed")
component_tests = '''
    def test_esc_index_next_line_reverse_index_and_cursor_restore(self):
        win = self._make_window()
        win._sync_screen_size()
        active = win._screen._active
        for row in range(active.rows):
            active._grid[row] = [(str(row), 0) for _ in range(active.cols)]
        active.set_scroll_region(1, 3)

        active.set_cursor(3, 2)
        win._consume_output("\\x1bD")
        self.assertEqual(active.cursor_col, 2)
        self.assertEqual(active.get_cell(1, 0), ("2", 0))
        self.assertEqual(active.get_cell(3, 0), (" ", 0))

        active.set_cursor(1, 4)
        win._consume_output("\\x1bM")
        self.assertEqual(active.get_cell(1, 0), (" ", 0))
        self.assertEqual(active.get_cell(2, 0), ("2", 0))

        active.set_cursor(1, 5)
        win._consume_output("\\x1bE")
        self.assertEqual((active.cursor_row, active.cursor_col), (2, 0))

        active.set_cursor(2, 6)
        win._consume_output("\\x1b7\\x1b[1;1H\\x1b8")
        self.assertEqual((active.cursor_row, active.cursor_col), (2, 6))

    def test_horizontal_tab_controls_move_cursor_without_overwriting_cells(self):
        win = self._make_window()
        win._sync_screen_size()
        active = win._screen._active
        active._grid[0][4] = ("X", 0)
        active.set_cursor(0, 0)

        win._consume_output("\\t")
        self.assertEqual(active.cursor_col, 8)
        self.assertEqual(active.get_cell(0, 4), ("X", 0))

        active.set_cursor(0, 3)
        win._consume_output("\\x1bH")
        active.set_cursor(0, 0)
        win._consume_output("\\t")
        self.assertEqual(active.cursor_col, 3)

        win._consume_output("\\x1b[g")
        active.set_cursor(0, 0)
        win._consume_output("\\t")
        self.assertEqual(active.cursor_col, 8)

        win._consume_output("\\x1b[3g")
        active.set_cursor(0, 0)
        win._consume_output("\\t")
        self.assertEqual(active.cursor_col, active.cols - 1)

        win._reset_tab_stops(active.cols)
        active.set_cursor(0, 0)
        win._consume_output("\\x1b[2I")
        self.assertEqual(active.cursor_col, 16)
        win._consume_output("\\x1b[Z")
        self.assertEqual(active.cursor_col, 8)

    def test_dsr_and_cpr_responses_respect_origin_mode(self):
        win = self._make_window()
        win._sync_screen_size()
        fake_session = _FakeSession()
        win._session = fake_session
        active = win._screen._active
        active.set_cursor(2, 4)

        win._consume_output("\\x1b[5n\\x1b[6n")
        self.assertEqual(fake_session.writes[:2], ["\\x1b[0n", "\\x1b[3;5R"])

        active.set_scroll_region(1, 5)
        win._consume_output("\\x1b[?6h\\x1b[3;5H\\x1b[?5n\\x1b[?6n")
        self.assertEqual(fake_session.writes[-2:], ["\\x1b[?0n", "\\x1b[?3;5R"])
'''
component_path.write_text(
    component_text.replace(component_marker, component_tests + component_marker, 1),
    encoding="utf-8",
)

# Operational documentation.
(ROOT / "docs/TERMINAL_ESC_REPORTS_TABS.md").write_text(
    '''# Terminal ESC dispatch, reports and tab stops

This cut completes the basic VT format-effectors that sit above the Unicode
physical-cell and DEC scrolling-region layers.

## Single-byte ESC dispatch

The ANSI parser now emits explicit `ESC` events for:

- `IND` (`ESC D`): index one row without changing the column;
- `NEL` (`ESC E`): index one row and return to column zero;
- `RI` (`ESC M`): reverse index, scrolling the active region downward at its top;
- `HTS` (`ESC H`): set a horizontal tab stop at the current physical column;
- `DECSC` / `DECRC` (`ESC 7` / `ESC 8`): save and restore cursor position.

Unknown single-byte ESC commands remain safely consumed.

## Horizontal tabulation

Default stops are installed every eight physical columns. `HT` moves the
cursor to the next stop without writing spaces or changing cells. The terminal
also implements:

- `CHT` (`CSI Ps I`);
- `CBT` (`CSI Ps Z`);
- `TBC` current stop (`CSI g` / `CSI 0 g`);
- `TBC` all stops (`CSI 3 g`).

Tab stops are terminal-wide rather than tied to normal or alternate screen.
They are clipped when the viewport shrinks. New default stops are seeded when
it expands unless the child explicitly cleared all stops.

## Device status reports

- `CSI 5 n` replies with `CSI 0 n`.
- `CSI 6 n` replies with cursor position (`CPR`).
- DEC-private `CSI ? 5 n` and `CSI ? 6 n` receive private-form replies.
- CPR row numbering follows `DECOM`: screen-relative when reset and relative to
  the scrolling region origin when set.

Responses are written directly to the existing PTY child and do not alter
scrollback position or create a new session.

## Deliberate follow-ups

This cut does not implement primary/secondary device attributes, terminal
parameter reports, selective erase, full DECSC rendition restoration, or
256-color/true-color SGR.
''',
    encoding="utf-8",
)

# Remove one-shot machinery before the workflow commits the functional diff.
(ROOT / "tools/_apply_terminal_esc_reports_tabs.py").unlink()
(ROOT / ".github/workflows/apply-terminal-esc-reports-tabs.yml").unlink()

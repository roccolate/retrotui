"""Tests for v0.9.5 Terminal 2D buffer wiring.

These cover the contract between ``TerminalWindow`` and
``TerminalScreenBuffer`` / ``TerminalScreen`` introduced for v0.9.5:

* The ANSI state machine writes through the buffer (not the legacy
  ``_line_cells`` / ``_scroll_lines`` lists).
* The normal-screen buffer captures only rows that leave the visible grid.
* Newlines inside the visible grid do not duplicate rows in scrollback.
* The alt-screen buffer is isolated and swapped via ``TerminalScreen``.
* The cursor position read by the renderer comes from the buffer.
"""

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.A_DIM = 4
    fake.A_UNDERLINE = 8
    fake.color_pair = lambda value: int(value) * 10
    fake.has_colors = lambda: False
    fake.init_pair = lambda *_args, **_kwargs: None
    fake.error = Exception
    fake.BUTTON1_PRESSED = 0x2
    fake.BUTTON1_CLICKED = 0x8
    fake.BUTTON1_DOUBLE_CLICKED = 0x10
    return fake


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "tests"))
sys.path.insert(0, str(_REPO_ROOT))

for mod_name in (
    "retrotui.constants",
    "retrotui.utils",
    "retrotui.ui.menu",
    "retrotui.ui.window",
    "retrotui.core.actions",
    "retrotui.core.clipboard",
    "retrotui.core.terminal_session",
    "retrotui.apps.terminal",
):
    sys.modules.pop(mod_name, None)

sys.modules["curses"] = _install_fake_curses()

terminal_mod = importlib.import_module("retrotui.apps.terminal")
actions_mod = importlib.import_module("retrotui.core.actions")
session_mod = importlib.import_module("retrotui.core.terminal_session")


class _FakeSession:
    instances = []
    supported = True
    start_error = None

    def __init__(self, *args, **kwargs):
        self.started = False
        self.running = True
        self.cols = kwargs.get("cols", 80)
        self.rows = kwargs.get("rows", 24)
        self.master_fd = 1
        self.child_pid = 100
        self.closed = False
        self.writes = []
        _FakeSession.instances.append(self)

    @staticmethod
    def is_supported():
        return _FakeSession.supported

    def start(self):
        if _FakeSession.start_error:
            raise _FakeSession.start_error
        self.started = True

    def read(self, *_):
        return ""

    def poll_exit(self):
        return False

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def interrupt(self):
        return True

    def terminate(self):
        return True

    def close(self):
        self.closed = True
        self.running = False


class TerminalBufferWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.actions",
            "retrotui.core.clipboard",
            "retrotui.core.terminal_session",
            "retrotui.apps.terminal",
        ):
            sys.modules.pop(mod_name, None)
        cls.terminal_mod = importlib.import_module("retrotui.apps.terminal")
        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.curses = sys.modules["curses"]

    def setUp(self):
        _FakeSession.instances = []
        _FakeSession.supported = True
        _FakeSession.start_error = None
        with mock.patch.object(self.terminal_mod, "theme_attr", return_value=0):
            with mock.patch.object(self.terminal_mod, "TerminalSession", _FakeSession):
                self.win = self.terminal_mod.TerminalWindow(2, 3, 80, 24)
                self.win.body_rect = mock.Mock(return_value=(4, 5, 70, 18))
                self.win._sync_screen_size()

    @staticmethod
    def _texts(lines):
        return ["".join(ch for ch, _ in line).rstrip() for line in lines]

    def _resize_buffers(self, rows, cols=20):
        self.win._normal_buf.resize(rows, cols)
        self.win._alt_buf.resize(rows, cols)

    def test_terminalwindow_owns_terminal_screen(self):
        win = self.win
        # Both buffers must be TerminalScreenBuffer instances owned by a
        # TerminalScreen; the normal one is wrapped to capture into scrollback.
        self.assertIsInstance(win._screen, self.terminal_mod.TerminalScreen)
        self.assertIsInstance(win._normal_buf, self.terminal_mod.TerminalScreenBuffer)
        self.assertIsInstance(win._alt_buf, self.terminal_mod.TerminalScreenBuffer)
        # Active starts on the normal buffer.
        self.assertFalse(win._screen.alt_screen)
        self.assertIs(win._screen._active, win._normal_buf)

    def test_ansi_state_machine_writes_via_buffer_put_char(self):
        """``_consume_output`` must route characters through ``put_char``."""
        win = self.win
        win._consume_output("ABC")
        self.assertEqual(win._cursor_col, 3)
        # Cells must live in the buffer (cursor row), not in a side list.
        cursor_row = win._normal_buf.get_row(win._cursor_row)
        self.assertEqual([ch for ch, _ in cursor_row[:3]], ["A", "B", "C"])

    def test_newline_does_not_duplicate_rows_before_or_after_overflow(self):
        win = self.win
        self._resize_buffers(3)

        win._consume_output("one\ntwo\n")
        self.assertEqual(list(win._scrollback), [])
        self.assertEqual(
            [text for text in self._texts(win._all_lines()) if text],
            ["one", "two"],
        )

        win._consume_output("three\nfour\n")
        self.assertEqual(self._texts(win._scrollback), ["one", "two"])
        self.assertEqual(
            [text for text in self._texts(win._all_lines()) if text],
            ["one", "two", "three", "four"],
        )

    def test_scrollback_respects_maxlen(self):
        win = self.win
        win.max_scrollback = 3
        win._scroll_lines = []
        self._resize_buffers(2)

        for ch in "abcdefghij":
            win._consume_output(ch + "\n")

        self.assertEqual(self._texts(win._scrollback), ["g", "h", "i"])
        self.assertEqual(
            [text for text in self._texts(win._all_lines()) if text],
            ["g", "h", "i", "j"],
        )

    def test_consecutive_identical_lines_are_preserved_once_each(self):
        win = self.win
        self._resize_buffers(2)

        win._consume_output("same\nsame\nsame\n")

        self.assertEqual(
            [text for text in self._texts(win._all_lines()) if text],
            ["same", "same", "same"],
        )
        self.assertEqual(self._texts(win._scrollback), ["same", "same"])

    def test_replacing_scrollback_rebinds_buffer_sink(self):
        win = self.win
        old_scrollback = win._scrollback
        win._scroll_lines = []
        new_scrollback = win._scrollback
        self._resize_buffers(2)

        win._consume_output("a\nb\nc\n")

        self.assertIsNot(old_scrollback, new_scrollback)
        self.assertEqual(list(old_scrollback), [])
        self.assertEqual(self._texts(new_scrollback), ["a", "b"])

    def test_carriage_return_resets_column_to_zero(self):
        win = self.win
        win._consume_output("abc\rXY")
        self.assertEqual(win._cursor_col, 2)
        cursor_row = win._normal_buf.get_row(win._cursor_row)
        self.assertEqual(cursor_row[0], ("X", 0))
        self.assertEqual(cursor_row[1], ("Y", 0))

    def test_alt_screen_toggle_uses_alt_buffer(self):
        win = self.win
        win._consume_output("\x1b[?1049h")
        self.assertTrue(win._screen.alt_screen)
        self.assertIs(win._screen._active, win._alt_buf)
        win._consume_output("\x1b[?1049l")
        self.assertFalse(win._screen.alt_screen)
        self.assertIs(win._screen._active, win._normal_buf)

    def test_alt_screen_writes_do_not_pollute_scrollback(self):
        win = self.win
        before = len(win._scrollback)
        win._consume_output("\x1b[?1049hXYZ\n\x1b[?1049l")
        after = len(win._scrollback)
        # Alt-screen newlines should not leak into the normal scrollback.
        self.assertEqual(after, before)

    def test_csi_cursor_position_clamps_to_buffer(self):
        win = self.win
        rows, cols = win._normal_buf.rows, win._normal_buf.cols
        # Move cursor way past the bottom-right corner.
        win._consume_output(f"\x1b[{rows * 10};{cols * 10}H")
        self.assertEqual(win._cursor_row, rows - 1)
        self.assertEqual(win._cursor_col, cols - 1)

    def test_csi_erase_display_clears_buffer(self):
        win = self.win
        win._consume_output("hello\x1b[2J")
        # After mode-2 ED, the whole buffer is spaces.
        for r in range(win._normal_buf.rows):
            row = win._normal_buf.get_row(r)
            for ch, _ in row:
                self.assertEqual(ch, " ")

    def test_backward_compat_line_cells_reflects_cursor_row(self):
        win = self.win
        win._consume_output("XY")
        # Legacy readers expect _line_cells to be the cells at the cursor row.
        row = win._line_cells
        self.assertEqual([ch for ch, _ in row[:2]], ["X", "Y"])
        self.assertEqual(win._cursor_col, 2)

    def test_backward_compat_scroll_lines_exposes_committed_rows(self):
        win = self.win
        win._consume_output("first\nsecond\n")
        scrollback_texts = self._texts(win._scroll_lines)
        self.assertIn("first", scrollback_texts)
        self.assertIn("second", scrollback_texts)
        # The compatibility view must not create a second stored copy.
        self.assertEqual(list(win._scrollback), [])

    def test_resize_preserves_overlapping_cells(self):
        win = self.win
        win._consume_output("ABCDE")
        win._normal_buf.resize(win._normal_buf.rows, win._normal_buf.cols)
        cursor_row = win._normal_buf.get_row(win._cursor_row)
        # The first five cells of the cursor row must survive a no-op resize.
        self.assertEqual([ch for ch, _ in cursor_row[:5]], ["A", "B", "C", "D", "E"])

    def test_buffer_module_exposes_screen_class(self):
        # The terminal_session module must export the public API surface that
        # the wiring depends on; importing it is enough to prove the
        # contract.
        self.assertTrue(hasattr(self.terminal_mod, "TerminalScreen"))
        self.assertTrue(hasattr(self.terminal_mod, "TerminalScreenBuffer"))


if __name__ == "__main__":
    unittest.main()

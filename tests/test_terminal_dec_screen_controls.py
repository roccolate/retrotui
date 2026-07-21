"""Focused tests for DEC screen regions and editing controls."""

import unittest

from retrotui.core.terminal_modes import TerminalModes
from retrotui.core.terminal_session import TerminalScreenBuffer


def _fill_rows(buf):
    for row in range(buf.rows):
        token = str(row)
        buf._grid[row] = [(token, 0) for _ in range(buf.cols)]


class TerminalDecScreenBufferTests(unittest.TestCase):
    def test_scroll_region_line_feed_preserves_rows_outside_margins(self):
        buf = TerminalScreenBuffer(5, 4)
        _fill_rows(buf)
        captured = []
        buf.set_scroll_sink(captured.append)
        self.assertTrue(buf.set_scroll_region(1, 3))
        buf.set_cursor(3, 0)

        buf.line_feed()

        self.assertEqual(buf.get_row(0), [("0", 0)] * 4)
        self.assertEqual(buf.get_row(1), [("2", 0)] * 4)
        self.assertEqual(buf.get_row(2), [("3", 0)] * 4)
        self.assertEqual(buf.get_row(3), [(" ", 0)] * 4)
        self.assertEqual(buf.get_row(4), [("4", 0)] * 4)
        self.assertEqual(captured, [])

    def test_full_screen_scroll_still_emits_scrollback(self):
        buf = TerminalScreenBuffer(3, 3)
        _fill_rows(buf)
        captured = []
        buf.set_scroll_sink(captured.append)
        buf.set_cursor(2, 0)

        buf.line_feed()

        self.assertEqual(captured, [[("0", 0)] * 3])
        self.assertEqual(buf.get_row(2), [(" ", 0)] * 3)

    def test_reverse_index_scrolls_region_down(self):
        buf = TerminalScreenBuffer(5, 3)
        _fill_rows(buf)
        buf.set_scroll_region(1, 3)
        buf.set_cursor(1, 0)

        buf.reverse_index()

        self.assertEqual(buf.get_row(0), [("0", 0)] * 3)
        self.assertEqual(buf.get_row(1), [(" ", 0)] * 3)
        self.assertEqual(buf.get_row(2), [("1", 0)] * 3)
        self.assertEqual(buf.get_row(3), [("2", 0)] * 3)
        self.assertEqual(buf.get_row(4), [("4", 0)] * 3)

    def test_insert_and_delete_lines_are_region_scoped(self):
        buf = TerminalScreenBuffer(5, 3)
        _fill_rows(buf)
        buf.set_scroll_region(1, 3)
        buf.set_cursor(2, 0)

        buf.insert_line()
        self.assertEqual(buf.get_row(2), [(" ", 0)] * 3)
        self.assertEqual(buf.get_row(3), [("2", 0)] * 3)
        self.assertEqual(buf.get_row(4), [("4", 0)] * 3)

        buf.delete_line()
        self.assertEqual(buf.get_row(2), [("2", 0)] * 3)
        self.assertEqual(buf.get_row(3), [(" ", 0)] * 3)
        self.assertEqual(buf.get_row(4), [("4", 0)] * 3)

    def test_insert_and_erase_chars_preserve_wide_cell_invariants(self):
        buf = TerminalScreenBuffer(1, 7)
        for ch in "A界B":
            buf.put_char(ch)
        buf.set_cursor(0, 1)

        buf.insert_chars(1)

        self.assertEqual(buf.get_cell(0, 1), (" ", 0))
        self.assertEqual(buf.get_cell(0, 2), ("界", 0))
        self.assertEqual(buf.get_cell(0, 3), ("", 0))
        buf.set_cursor(0, 3)
        buf.erase_chars(1)
        self.assertEqual(buf.get_cell(0, 2), (" ", 0))
        self.assertEqual(buf.get_cell(0, 3), (" ", 0))

    def test_saved_cursor_and_region_survive_resize_safely(self):
        buf = TerminalScreenBuffer(6, 8)
        buf.set_scroll_region(1, 4)
        buf.set_cursor(4, 7)
        buf.save_cursor()
        buf.resize(4, 5)

        self.assertEqual((buf.scroll_top, buf.scroll_bottom), (1, 3))
        buf.set_cursor(0, 0)
        buf.restore_cursor()
        self.assertEqual((buf.cursor_row, buf.cursor_col), (3, 4))

    def test_origin_mode_resets_with_other_dec_modes(self):
        modes = TerminalModes()
        self.assertTrue(modes.set_private_mode(6, True))
        self.assertTrue(modes.origin_mode)
        modes.reset()
        self.assertFalse(modes.origin_mode)


if __name__ == "__main__":
    unittest.main()

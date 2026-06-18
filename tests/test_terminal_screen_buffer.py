"""Unit tests for the TerminalScreenBuffer class."""

import unittest

from retrotui.core.terminal_session import TerminalScreenBuffer


class TerminalScreenBufferTests(unittest.TestCase):
    def setUp(self):
        self.buf = TerminalScreenBuffer(3, 5)

    def test_initial_state_is_blank_with_cursor_home(self):
        for row in range(3):
            for col in range(5):
                self.assertEqual(self.buf.get_cell(row, col), (" ", 0))
        self.assertEqual((self.buf.cursor_row, self.buf.cursor_col), (0, 0))

    def test_put_char_writes_and_advances(self):
        self.buf.put_char("H")
        self.buf.put_char("i")
        self.assertEqual(self.buf.get_row(0)[0], ("H", 0))
        self.assertEqual(self.buf.get_row(0)[1], ("i", 0))
        self.assertEqual(self.buf.cursor_col, 2)

    def test_put_char_with_attr_uses_provided_attr(self):
        self.buf.put_char("X", attr=0x42)
        self.assertEqual(self.buf.get_row(0)[0], ("X", 0x42))

    def test_put_char_wraps_to_next_line_at_end(self):
        for _ in range(5):
            self.buf.put_char("a")
        self.assertEqual(self.buf.cursor_row, 0)
        self.assertEqual(self.buf.cursor_col, 5)
        self.buf.put_char("b")
        # Wrapped to row 1.
        self.assertEqual(self.buf.cursor_row, 1)
        self.assertEqual(self.buf.cursor_col, 1)
        self.assertEqual(self.buf.get_row(1)[0], ("b", 0))

    def test_line_feed_scrolls_at_bottom(self):
        # Fill the buffer: each row holds "aaa..". After each row we
        # call carriage_return to mirror the typical CR/LF pair.
        for r in range(3):
            for _ in range(3):
                self.buf.put_char("a")
            self.buf.carriage_return()
            self.buf.line_feed()
        # Cursor is at row 2 (last row) after the third line_feed. Another
        # line_feed from the last row scrolls the buffer up by one.
        self.buf.line_feed()
        # The old row 0 ("aaa..") is gone; the old row 1 is now row 0.
        self.assertEqual(self.buf.get_row(0)[0], ("a", 0))
        # The new last row is blank.
        self.assertEqual(self.buf.get_row(2), [(" ", 0)] * 5)
        # Cursor stays on the last (newly blank) row.
        self.assertEqual(self.buf.cursor_row, 2)

    def test_clear_line_resets_only_one_row(self):
        self.buf.put_char("x")
        # Cursor at (0, 1). Call clear_line() without arg to clear the
        # cursor row.
        self.buf.clear_line()
        self.assertEqual(self.buf.get_row(0), [(" ", 0)] * 5)
        # Cursor reset to column 0 on the cleared row.
        self.assertEqual(self.buf.cursor_col, 0)
        # Move to row 1 and write "y", then clear row 0 explicitly.
        self.buf.set_cursor(1, 0)
        self.buf.put_char("y")
        self.buf.clear_line(0)
        self.assertEqual(self.buf.get_row(0), [(" ", 0)] * 5)
        # Row 1 untouched.
        self.assertEqual(self.buf.get_row(1)[0], ("y", 0))

    def test_clear_screen_below_preserves_columns_before_cursor(self):
        for ch in "abcde":
            self.buf.put_char(ch)
        self.buf.carriage_return()
        self.buf.line_feed()
        for ch in "fghij":
            self.buf.put_char(ch)
        # Move to (1, 2) so columns 0-1 of row 1 stay intact.
        self.buf.set_cursor(1, 2)
        self.buf.clear_screen("below")
        # Row 0 is untouched.
        self.assertEqual(self.buf.get_row(0)[0], ("a", 0))
        # Row 1: cols 0-1 preserved ("fg"), cols 2+ blanked.
        self.assertEqual(self.buf.get_row(1)[0], ("f", 0))
        self.assertEqual(self.buf.get_row(1)[1], ("g", 0))
        self.assertEqual(self.buf.get_row(1)[2], (" ", 0))
        # Row 2 (below the cursor) blanked entirely.
        for col in range(5):
            self.assertEqual(self.buf.get_row(2)[col], (" ", 0))

    def test_clear_screen_above_preserves_columns_after_cursor(self):
        for ch in "abcde":
            self.buf.put_char(ch)
        self.buf.carriage_return()
        self.buf.line_feed()
        for ch in "fghij":
            self.buf.put_char(ch)
        # Cursor at (1, 2). "above" clears rows 0 and columns 0-2 of
        # row 1; columns 3-4 of row 1 stay.
        self.buf.set_cursor(1, 2)
        self.buf.clear_screen("above")
        for col in range(5):
            self.assertEqual(self.buf.get_row(0)[col], (" ", 0))
        self.assertEqual(self.buf.get_row(1)[:2], [(" ", 0), (" ", 0)])
        self.assertEqual(self.buf.get_row(1)[2], (" ", 0))
        self.assertEqual(self.buf.get_row(1)[3], ("i", 0))
        self.assertEqual(self.buf.get_row(1)[4], ("j", 0))

    def test_clear_screen_all_homes_cursor(self):
        self.buf.put_char("a")
        self.buf.line_feed()
        self.buf.put_char("b")
        self.buf.set_cursor(1, 4)
        self.buf.clear_screen("all")
        self.assertEqual((self.buf.cursor_row, self.buf.cursor_col), (0, 0))
        for row in range(3):
            for col in range(5):
                self.assertEqual(self.buf.get_cell(row, col), (" ", 0))

    def test_scroll_up(self):
        for ch in "abcde":
            self.buf.put_char(ch)
        self.buf.carriage_return()
        self.buf.line_feed()
        for ch in "fghij":
            self.buf.put_char(ch)
        # After writing two rows, row 0 = "abcde" and row 1 = "fghij".
        self.buf.scroll_up(1)
        # Row 0 now holds what was row 1.
        self.assertEqual(self.buf.get_row(0)[0], ("f", 0))
        # Last row is blank.
        self.assertEqual(self.buf.get_row(2), [(" ", 0)] * 5)

    def test_scroll_down(self):
        for ch in "abcde":
            self.buf.put_char(ch)
        self.buf.scroll_down(1)
        # Row 0 is blank.
        self.assertEqual(self.buf.get_row(0), [(" ", 0)] * 5)
        # Old row 0 ("abcde") is now at row 1.
        self.assertEqual(self.buf.get_row(1)[0], ("a", 0))

    def test_insert_and_delete_line(self):
        for ch in "abcde":
            self.buf.put_char(ch)
        self.buf.carriage_return()
        self.buf.line_feed()
        for ch in "fghij":
            self.buf.put_char(ch)
        # After two rows, row 0 = "abcde" and row 1 = "fghij".
        self.buf.set_cursor(0, 0)
        self.buf.insert_line(1)
        # Row 0 now blank, old row 0 moved to row 1.
        self.assertEqual(self.buf.get_row(0), [(" ", 0)] * 5)
        self.assertEqual(self.buf.get_row(1)[0], ("a", 0))
        # The old row 1 is now at row 2 (row 3 is gone because we only
        # have a 3-row buffer).
        self.assertEqual(self.buf.get_row(2)[0], ("f", 0))

        # Delete the blank row we just inserted.
        self.buf.set_cursor(0, 0)
        self.buf.delete_line(1)
        self.assertEqual(self.buf.get_row(0)[0], ("a", 0))
        self.assertEqual(self.buf.get_row(1)[0], ("f", 0))

    def test_backspace(self):
        for ch in "abc":
            self.buf.put_char(ch)
        # Cursor is at column 3 after writing 3 chars.
        self.buf.backspace()
        self.assertEqual(self.buf.cursor_col, 2)
        # Backspace does not erase; the cell at col 2 still holds "c".
        self.assertEqual(self.buf.get_row(0)[2], ("c", 0))
        # Backspace at column 0 stays put.
        self.buf.set_cursor(0, 0)
        prev_col = self.buf.cursor_col
        self.buf.backspace()
        self.assertEqual(self.buf.cursor_col, prev_col)

    def test_carriage_return(self):
        for ch in "abc":
            self.buf.put_char(ch)
        self.buf.carriage_return()
        self.assertEqual(self.buf.cursor_col, 0)
        # Row 0 still has "abc" - CR doesn't erase.
        self.assertEqual(self.buf.get_row(0)[:3], [("a", 0), ("b", 0), ("c", 0)])

    def test_resize_preserves_overlap(self):
        for ch in "abcde":
            self.buf.put_char(ch)
        self.buf.carriage_return()
        self.buf.line_feed()
        for ch in "fghij":
            self.buf.put_char(ch)
        # Rows 0 and 1 hold content; row 2 is blank.
        # Resize larger: new rows are blank, old content stays.
        self.buf.resize(5, 7)
        self.assertEqual(self.buf.rows, 5)
        self.assertEqual(self.buf.cols, 7)
        self.assertEqual(
            self.buf.get_row(0)[:5],
            [("a", 0), ("b", 0), ("c", 0), ("d", 0), ("e", 0)],
        )
        self.assertEqual(self.buf.get_row(3), [(" ", 0)] * 7)
        # Resize smaller: trailing rows dropped, trailing cols dropped.
        self.buf.resize(2, 3)
        self.assertEqual(self.buf.rows, 2)
        self.assertEqual(self.buf.cols, 3)
        self.assertEqual(
            self.buf.get_row(0),
            [("a", 0), ("b", 0), ("c", 0)],
        )
        self.assertEqual(self.buf.get_row(1)[0], ("f", 0))

    def test_resize_clamps_cursor(self):
        for ch in "abcde":
            self.buf.put_char(ch)
        self.buf.resize(1, 2)
        # Cursor was at (0, 5) - clamp to (0, 1).
        self.assertEqual(self.buf.cursor_col, 1)

    def test_unknown_clear_mode_raises(self):
        with self.assertRaises(ValueError):
            self.buf.clear_screen("bogus")

    def test_default_attr_used_when_clearing(self):
        buf = TerminalScreenBuffer(2, 3, default_attr=0x55)
        buf.put_char("A", attr=0xAA)
        buf.clear_line()
        self.assertEqual(buf.get_row(0), [(" ", 0x55)] * 3)
        buf.clear_screen("all")
        self.assertEqual(buf.get_row(0), [(" ", 0x55)] * 3)


if __name__ == "__main__":
    unittest.main()

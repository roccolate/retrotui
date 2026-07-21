"""Focused Unicode cell-engine regressions."""

import unittest

from retrotui.core.terminal_cells import (
    CONTINUATION_TEXT,
    display_width,
    leading_cell_index,
    row_text,
    sanitize_row,
)
from retrotui.core.terminal_session import TerminalScreenBuffer


class TerminalUnicodeCellTests(unittest.TestCase):
    def test_width_helpers_cover_ascii_wide_combining_and_controls(self):
        self.assertEqual(display_width("A"), 1)
        self.assertEqual(display_width("你"), 2)
        self.assertEqual(display_width("e\u0301"), 1)
        self.assertEqual(display_width(""), 0)
        self.assertEqual(display_width("\x07"), -1)

    def test_wide_character_reserves_a_continuation_cell(self):
        buf = TerminalScreenBuffer(2, 4)

        buf.put_char("你", attr=7)

        self.assertEqual(buf.get_row(0)[:2], [("你", 7), (CONTINUATION_TEXT, 7)])
        self.assertEqual(buf.cursor_col, 2)
        self.assertEqual(row_text(buf.get_row(0)[:2]), "你")

    def test_combining_mark_merges_without_advancing(self):
        buf = TerminalScreenBuffer(1, 4)

        buf.put_char("e")
        buf.put_char("\u0301")

        self.assertEqual(buf.get_cell(0, 0), ("e\u0301", 0))
        self.assertEqual(buf.cursor_col, 1)

    def test_variation_selector_can_expand_previous_cell(self):
        buf = TerminalScreenBuffer(1, 4)

        buf.put_char("\u2640")
        before = buf.cursor_col
        buf.put_char("\ufe0f")

        self.assertIn(buf.cursor_col, (before, before + 1))
        self.assertTrue(buf.get_cell(0, 0)[0].startswith("\u2640"))
        self.assertEqual(display_width(buf.get_cell(0, 0)[0]), buf.cursor_col)

    def test_wide_character_wraps_before_last_column(self):
        buf = TerminalScreenBuffer(2, 3)
        buf.put_char("a")
        buf.put_char("b")

        buf.put_char("你")

        self.assertEqual(buf.cursor_row, 1)
        self.assertEqual(buf.cursor_col, 2)
        self.assertEqual(buf.get_row(1)[:2], [("你", 0), (CONTINUATION_TEXT, 0)])

    def test_autowrap_disabled_clamps_and_overwrites_last_cell(self):
        buf = TerminalScreenBuffer(1, 3)

        for ch in "abcd":
            buf.put_char(ch, autowrap=False)

        self.assertEqual(row_text(buf.get_row(0)), "abd")
        self.assertEqual(buf.cursor_col, 2)

    def test_wide_character_without_room_uses_replacement_when_no_wrap(self):
        buf = TerminalScreenBuffer(1, 3)
        buf.put_char("a", autowrap=False)
        buf.put_char("b", autowrap=False)

        buf.put_char("你", autowrap=False)

        self.assertEqual(buf.get_cell(0, 2), ("\ufffd", 0))
        self.assertEqual(buf.cursor_col, 2)

    def test_backspace_lands_on_wide_leading_cell(self):
        buf = TerminalScreenBuffer(1, 4)
        buf.put_char("你")

        buf.backspace()

        self.assertEqual(buf.cursor_col, 0)

    def test_clear_range_expands_over_wide_glyph(self):
        buf = TerminalScreenBuffer(1, 4)
        buf.put_char("你")
        buf.put_char("x")

        buf.clear_range(0, 1, 2)

        self.assertEqual(buf.get_row(0)[:2], [(" ", 0), (" ", 0)])
        self.assertEqual(buf.get_cell(0, 2), ("x", 0))

    def test_delete_chars_never_leaves_an_orphan_tail(self):
        buf = TerminalScreenBuffer(1, 5)
        for ch in "你ab":
            buf.put_char(ch)
        buf.set_cursor(0, 0)

        buf.delete_chars(1)

        self.assertEqual(row_text(buf.get_row(0)), "ab   ")
        self.assertNotEqual(buf.get_cell(0, 0)[0], CONTINUATION_TEXT)

    def test_resize_drops_a_half_wide_glyph(self):
        buf = TerminalScreenBuffer(1, 3)
        buf.put_char("a")
        buf.put_char("你")

        buf.resize(1, 2)

        self.assertEqual(buf.get_row(0), [("a", 0), (" ", 0)])

    def test_sanitize_row_repairs_orphan_and_extra_continuations(self):
        row = [("", 3), ("你", 4), ("", 9), ("", 9)]

        cleaned = sanitize_row(row, default_attr=0)

        self.assertEqual(cleaned[0], (" ", 0))
        self.assertEqual(cleaned[1:3], [("你", 4), ("", 4)])
        self.assertEqual(cleaned[3], (" ", 0))
        self.assertEqual(leading_cell_index(cleaned, 2), 1)


if __name__ == "__main__":
    unittest.main()

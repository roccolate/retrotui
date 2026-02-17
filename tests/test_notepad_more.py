"""Additional Notepad tests covering wrap/cache and editing helpers."""

from __future__ import annotations

import importlib
import sys
import unittest
from unittest import mock

from _support import make_fake_curses


class NotepadMoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = make_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.theme",
            "retrotui.utils",
            "retrotui.ui.dialog",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.actions",
            "retrotui.core.clipboard",
            "retrotui.apps.notepad",
        ):
            sys.modules.pop(mod_name, None)

        cls.notepad_mod = importlib.import_module("retrotui.apps.notepad")
        cls.NotepadWindow = cls.notepad_mod.NotepadWindow

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.notepad",
            "retrotui.core.clipboard",
            "retrotui.core.actions",
            "retrotui.ui.window",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
            "retrotui.utils",
            "retrotui.theme",
            "retrotui.constants",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def setUp(self):
        self.win = self.NotepadWindow(0, 0, 40, 10)

    def test_open_path_empty_and_non_empty(self):
        with mock.patch.object(self.win, "_load_file") as load_file, mock.patch.object(
            self.win, "clear_selection"
        ) as clear_selection:
            self.assertIsNone(self.win.open_path(""))
            load_file.assert_not_called()

            self.assertIsNone(self.win.open_path("note.txt"))
            self.assertTrue(load_file.called)
            clear_selection.assert_called()

    def test_line_selection_span_variants(self):
        win = self.win

        win.selection_anchor = (1, 0)
        win.selection_cursor = (1, 1)
        self.assertIsNone(win._line_selection_span(0, 10))

        win.selection_anchor = (0, 1)
        win.selection_cursor = (0, 2)
        self.assertIsNone(win._line_selection_span(0, 0))

        win.selection_anchor = (0, 2)
        win.selection_cursor = (0, 5)
        self.assertEqual(win._line_selection_span(0, 10), (2, 5))

        win.selection_anchor = (0, 1)
        win.selection_cursor = (2, 0)
        self.assertIsNone(win._line_selection_span(0, 0))
        self.assertEqual(win._line_selection_span(0, 10), (1, 10))

        win.selection_anchor = (0, 1)
        win.selection_cursor = (2, 0)
        self.assertIsNone(win._line_selection_span(2, 0))

        win.selection_anchor = (0, 1)
        win.selection_cursor = (2, 3)
        self.assertEqual(win._line_selection_span(2, 10), (0, 3))
        self.assertEqual(win._line_selection_span(1, 10), (0, 10))

    def test_selected_text_and_delete_selection_guard(self):
        win = self.win
        win.buffer = ["first", "second", "third"]
        win.selection_anchor = (0, 2)
        win.selection_cursor = (2, 3)
        self.assertIn("\nsecond\n", win._selected_text())

        win.clear_selection()
        self.assertFalse(win._delete_selection())

    def test_compute_wrap_and_cursor_wrap_row(self):
        self.win.buffer = ["".join(str(i % 10) for i in range(100))]
        self.win.wrap_mode = True
        self.win._invalidate_wrap()

        self.win._compute_wrap(body_w=10)
        self.assertGreater(len(self.win._wrap_cache), 1)

        self.win.cursor_line = 0
        self.win.cursor_col = 25
        idx = self.win._cursor_to_wrap_row(body_w=10)
        self.assertGreaterEqual(idx, 0)

    def test_insert_text_multiline_and_clamp(self):
        self.win.buffer = ["hello world"]
        self.win.cursor_line = 0
        self.win.cursor_col = 6

        self.win._insert_text("X\nY\nZ")
        self.assertEqual(self.win.buffer[0], "hello X")
        self.assertIn("Y", self.win.buffer)
        self.assertTrue(self.win.modified)

    def test_delete_selection_multiline(self):
        self.win.buffer = ["first", "second", "third"]
        self.win.selection_anchor = (0, 2)
        self.win.selection_cursor = (2, 3)

        res = self.win._delete_selection()
        self.assertTrue(res)
        self.assertEqual(self.win.cursor_line, 0)
        self.assertTrue(self.win.modified)

    def test_cut_current_line_and_copy(self):
        self.win.buffer = ["line1", "line2"]
        self.win.cursor_line = 0

        with mock.patch.object(self.notepad_mod, "copy_text") as fake_copy:
            self.win._cut_current_line()
            fake_copy.assert_called_once_with("line1")

        self.assertEqual(self.win.buffer[0], "line2")

    def test_cut_current_line_guard_and_single_line_and_pop_last(self):
        win = self.win
        win.buffer = ["only"]
        win.cursor_line = 99
        with mock.patch.object(self.notepad_mod, "copy_text") as copy_text:
            win._cut_current_line()
        copy_text.assert_not_called()

        win.buffer = ["hello"]
        win.cursor_line = 0
        win.cursor_col = 3
        with mock.patch.object(self.notepad_mod, "copy_text") as copy_text:
            win._cut_current_line()
        copy_text.assert_called_once_with("hello")
        self.assertEqual(win.buffer, [""])
        self.assertEqual((win.cursor_line, win.cursor_col), (0, 0))

        win.buffer = ["a", "b"]
        win.cursor_line = 1
        win.cursor_col = 0
        with mock.patch.object(self.notepad_mod, "copy_text"):
            win._cut_current_line()
        self.assertEqual(win.cursor_line, 0)

    def test_set_cursor_from_screen_unwrap(self):
        self.win.buffer = ["a", "bb", "ccc", "dddd"]
        self.win.wrap_mode = False

        with mock.patch.object(self.win, "body_rect", return_value=(2, 1, 10, 6)):
            self.win.view_top = 1
            self.win.view_left = 0
            self.win._set_cursor_from_screen(3, 2)

        self.assertEqual(self.win.cursor_line, 2)

    def test_draw_selection_highlight_wrap_and_unwrap_paths(self):
        win = self.win
        win.body_rect = mock.Mock(return_value=(0, 0, 10, 6))
        win.draw_frame = mock.Mock(return_value=0)

        win.wrap_mode = True
        win.buffer = ["abcdefghij"]
        win.view_top = 0
        win.selection_anchor = (0, 2)
        win.selection_cursor = (0, 7)
        with (
            mock.patch.object(self.notepad_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(self.notepad_mod, "theme_attr", return_value=0),
        ):
            win.draw(None)
        self.assertTrue(safe_addstr.called)

        win.wrap_mode = False
        win.buffer = ["abcdef"]
        win.view_top = 0
        win.view_left = 0
        win.cursor_line = 0
        win.cursor_col = 0
        win.selection_anchor = (0, 1)
        win.selection_cursor = (0, 3)
        with (
            mock.patch.object(self.notepad_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(self.notepad_mod, "theme_attr", return_value=0),
        ):
            win.draw(None)
        self.assertTrue(safe_addstr.called)

    def test_ctrl_a_creates_buffer_when_empty(self):
        win = self.win
        win.window_menu = None
        win.buffer = []
        win.handle_key(1)
        self.assertEqual(win.buffer, [""])

    def test_handle_key_enter_paste_and_printable_with_selection(self):
        win = self.win
        win.window_menu = None
        win.buffer = ["abc"]
        win.cursor_line = 0
        win.cursor_col = 1
        win.selection_anchor = (0, 0)
        win.selection_cursor = (0, 1)

        with mock.patch.object(win, "_delete_selection", return_value=True) as delete_sel:
            win.handle_key(10)
        delete_sel.assert_called()

        win.selection_anchor = (0, 0)
        win.selection_cursor = (0, 1)
        with (
            mock.patch.object(win, "_delete_selection", return_value=True) as delete_sel,
            mock.patch.object(self.notepad_mod, "paste_text", return_value="X"),
            mock.patch.object(win, "_insert_text") as insert_text,
        ):
            win.handle_key(22)
        delete_sel.assert_called()
        insert_text.assert_called_once_with("X")

        win.selection_anchor = (0, 0)
        win.selection_cursor = (0, 1)
        with mock.patch.object(win, "_delete_selection", return_value=True) as delete_sel:
            win.handle_key("y")
        delete_sel.assert_called()

        win.selection_anchor = (0, 0)
        win.selection_cursor = (0, 1)
        with mock.patch.object(win, "_delete_selection", return_value=True) as delete_sel:
            win.handle_key(ord("z"))
        delete_sel.assert_called()

    def test_mouse_drag_not_pressed_outside_and_anchor_set(self):
        win = self.win
        win.body_rect = mock.Mock(return_value=(0, 0, 10, 6))

        win._mouse_selecting = True
        self.assertIsNone(win.handle_mouse_drag(1, 1, bstate=0))
        self.assertFalse(win._mouse_selecting)

        self.assertIsNone(win.handle_mouse_drag(999, 999, bstate=self.notepad_mod.curses.BUTTON1_PRESSED))

        win.selection_anchor = None
        with mock.patch.object(win, "_set_cursor_from_screen") as set_cursor:
            win.cursor_line = 0
            win.cursor_col = 0
            self.assertIsNone(win.handle_mouse_drag(1, 1, bstate=self.notepad_mod.curses.BUTTON1_PRESSED))
        set_cursor.assert_called()
        self.assertIsNotNone(win.selection_anchor)

    def test_handle_key_navigation_and_editing(self):
        self.win.buffer = ["a", "b"]
        self.win.cursor_line = 0
        self.win.cursor_col = 0

        self.win.handle_key(self.notepad_mod.curses.KEY_RIGHT)
        self.assertIn(self.win.cursor_line, (0, 1))

        self.win.cursor_line = 0
        self.win.cursor_col = 0
        self.win.handle_key(10)  # Enter
        self.assertTrue(self.win.modified)


if __name__ == "__main__":
    unittest.main()

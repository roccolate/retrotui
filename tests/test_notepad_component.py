import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_LEFT = 260
    fake.KEY_RIGHT = 261
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_ENTER = 343
    fake.KEY_HOME = 262
    fake.KEY_END = 360
    fake.KEY_PPAGE = 339
    fake.KEY_NPAGE = 338
    fake.KEY_BACKSPACE = 263
    fake.KEY_DC = 330
    fake.KEY_IC = 331
    fake.KEY_F6 = 270
    fake.BUTTON1_CLICKED = 0x0004
    fake.BUTTON1_PRESSED = 0x0002
    fake.BUTTON1_DOUBLE_CLICKED = 0x0008
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.error = Exception
    fake.color_pair = lambda value: value * 10
    return fake


class NotepadComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.clipboard",
            "retrotui.apps.notepad",
            "retrotui.core.actions",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.notepad_mod = importlib.import_module("retrotui.apps.notepad")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.clipboard",
            "retrotui.apps.notepad",
            "retrotui.core.actions",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_window(self, w=32, h=12):
        return self.notepad_mod.NotepadWindow(0, 0, w, h)

    def test_compute_wrap_builds_and_reuses_cache(self):
        win = self._make_window()
        win.buffer = ["abcdef", ""]
        win.wrap_mode = True

        win._compute_wrap(5)  # wrap width = 4
        self.assertEqual(
            win._wrap_cache,
            [
                (0, 0, "abcd"),
                (0, 4, "ef"),
                (1, 0, ""),
            ],
        )
        self.assertFalse(win._wrap_stale)
        cached = list(win._wrap_cache)

        win._compute_wrap(5)
        self.assertEqual(win._wrap_cache, cached)

        win._compute_wrap(6)
        self.assertEqual(win._wrap_cache_w, 6)

    def test_cursor_to_wrap_row_returns_last_segment_for_end_column(self):
        win = self._make_window()
        win.buffer = ["abcdef"]
        win.wrap_mode = True
        win.cursor_line = 0
        win.cursor_col = 6

        wrap_row = win._cursor_to_wrap_row(5)
        self.assertEqual(wrap_row, 1)

    def test_ensure_cursor_visible_non_wrap_adjusts_vertical_and_horizontal(self):
        win = self._make_window()
        win.wrap_mode = False
        win.buffer = ["x" * 80 for _ in range(40)]
        win.cursor_line = 20
        win.cursor_col = 50
        win.view_top = 0
        win.view_left = 0

        win._ensure_cursor_visible()

        self.assertGreater(win.view_top, 0)
        self.assertGreater(win.view_left, 0)

    def test_ensure_cursor_visible_wrap_adjusts_view_top(self):
        win = self._make_window()
        win.wrap_mode = True
        win.buffer = ["x" * 80 for _ in range(3)]
        win.cursor_line = 2
        win.cursor_col = 60
        win.view_top = 0

        win._ensure_cursor_visible()
        self.assertGreater(win.view_top, 0)

    def test_clamp_cursor_bounds(self):
        win = self._make_window()
        win.buffer = ["abc"]
        win.cursor_line = 10
        win.cursor_col = 99
        win._clamp_cursor()
        self.assertEqual((win.cursor_line, win.cursor_col), (0, 3))

        win.cursor_line = -4
        win.cursor_col = -2
        win._clamp_cursor()
        self.assertEqual((win.cursor_line, win.cursor_col), (0, 0))

    def test_draw_updates_title_and_renders_scrollbar_and_status(self):
        win = self._make_window()
        win.filepath = "/tmp/demo.txt"
        win.modified = True
        win.buffer = [f"line {i}" for i in range(40)]
        win.cursor_line = 10
        win.cursor_col = 2
        win.view_top = 5
        win.draw_frame = mock.Mock(return_value=0)
        win.window_menu.active = False

        with mock.patch.object(self.notepad_mod, "safe_addstr") as safe_addstr:
            win.draw(None)

        self.assertIn("* demo.txt", win.title)
        scrollbar_attr = self.notepad_mod.curses.color_pair(self.notepad_mod.C_SCROLLBAR)
        status_attr = self.notepad_mod.curses.color_pair(self.notepad_mod.C_STATUS)
        attrs = [call.args[4] for call in safe_addstr.call_args_list if len(call.args) >= 5]
        self.assertIn(scrollbar_attr, attrs)
        self.assertIn(status_attr, attrs)
        rendered_text = [call.args[3] for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("Ln " in str(text) for text in rendered_text))

    def test_execute_menu_action_branches(self):
        win = self._make_window()
        win.wrap_mode = False
        win.view_left = 4
        win._save_file = mock.Mock(
            return_value=self.actions_mod.ActionResult(self.actions_mod.ActionType.SAVE_ERROR, "err")
        )

        toggle = win._execute_menu_action(self.actions_mod.AppAction.NP_TOGGLE_WRAP)
        open_result = win._execute_menu_action(self.actions_mod.AppAction.NP_OPEN)
        save = win._execute_menu_action(self.actions_mod.AppAction.NP_SAVE)
        save_as = win._execute_menu_action(self.actions_mod.AppAction.NP_SAVE_AS)
        new_win = win._execute_menu_action(self.actions_mod.AppAction.NP_NEW)
        close = win._execute_menu_action(self.actions_mod.AppAction.NP_CLOSE)

        self.assertIsNone(toggle)
        self.assertTrue(win.wrap_mode)
        self.assertEqual(win.view_left, 0)
        self.assertEqual(open_result.type, self.actions_mod.ActionType.REQUEST_OPEN_PATH)
        self.assertEqual(save.type, self.actions_mod.ActionType.SAVE_ERROR)
        self.assertEqual(save_as.type, self.actions_mod.ActionType.REQUEST_SAVE_AS)
        self.assertEqual(new_win.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(new_win.payload, self.actions_mod.AppAction.NOTEPAD)
        self.assertEqual(close.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(close.payload, self.actions_mod.AppAction.CLOSE_WINDOW)

    def test_handle_key_when_menu_active_dispatches_menu_action(self):
        win = self._make_window()
        win.window_menu.active = True
        win.window_menu.handle_key = mock.Mock(return_value=self.actions_mod.AppAction.NP_NEW)

        result = win.handle_key(10)

        self.assertEqual(result.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(result.payload, self.actions_mod.AppAction.NOTEPAD)

    def test_handle_key_navigation_and_page_moves(self):
        win = self._make_window()
        win.buffer = [f"line-{i}" for i in range(40)]
        win.buffer[0] = "ab"
        win.buffer[1] = "cd"
        win.cursor_line = 0
        win.cursor_col = 2

        win.handle_key(self.curses.KEY_RIGHT)  # move to next line start
        self.assertEqual((win.cursor_line, win.cursor_col), (1, 0))

        win.handle_key(self.curses.KEY_LEFT)  # back to previous line end
        self.assertEqual((win.cursor_line, win.cursor_col), (0, 2))

        win.handle_key(self.curses.KEY_HOME)
        self.assertEqual(win.cursor_col, 0)

        win.handle_key(self.curses.KEY_END)
        self.assertEqual(win.cursor_col, len(win.buffer[0]))

        win.cursor_line = 20
        win.handle_key(self.curses.KEY_PPAGE)
        self.assertLess(win.cursor_line, 20)
        before = win.cursor_line
        win.handle_key(self.curses.KEY_NPAGE)
        self.assertGreaterEqual(win.cursor_line, before)

    def test_handle_click_wrap_mode_out_of_range_selects_last_line(self):
        win = self._make_window()
        win.wrap_mode = True
        win.buffer = ["abc", "def"]
        win.view_top = 99
        bx, by, _, _ = win.body_rect()

        win.handle_click(bx, by)

        self.assertEqual(win.cursor_line, len(win.buffer) - 1)
        self.assertEqual(win.cursor_col, len(win.buffer[-1]))

    def test_handle_click_non_wrap_out_of_range_selects_last_line(self):
        win = self._make_window()
        win.wrap_mode = False
        win.buffer = ["abc", "def"]
        win.view_top = 99
        bx, by, _, _ = win.body_rect()

        win.handle_click(bx, by)

        self.assertEqual(win.cursor_line, len(win.buffer) - 1)
        self.assertEqual(win.cursor_col, len(win.buffer[-1]))

    def test_handle_click_menu_intercept_returns_action(self):
        win = self._make_window()
        win.window_menu = types.SimpleNamespace(
            on_menu_bar=mock.Mock(return_value=True),
            active=False,
            handle_click=mock.Mock(return_value=self.actions_mod.AppAction.NP_CLOSE),
        )

        result = win.handle_click(1, 1)

        self.assertEqual(result.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(result.payload, self.actions_mod.AppAction.CLOSE_WINDOW)

    def test_scroll_down_wrap_mode_respects_maximum(self):
        win = self._make_window()
        win.wrap_mode = True
        win.buffer = ["x" * 80 for _ in range(5)]
        _, _, bw, bh = win.body_rect()
        win._compute_wrap(bw)
        body_h = bh - 1

        for _ in range(200):
            win.scroll_down()

        max_top = max(0, len(win._wrap_cache) - body_h)
        self.assertEqual(win.view_top, max_top)

    def test_load_file_keeps_trailing_empty_line(self):
        win = self._make_window()
        with mock.patch("builtins.open", mock.mock_open(read_data="hello\n")):
            win._load_file("demo.txt")

        self.assertEqual(win.buffer, ["hello", ""])

    def test_cursor_to_wrap_row_non_wrap_and_fallback_paths(self):
        win = self._make_window()
        win.buffer = ["abcdef"]
        win.wrap_mode = True
        win.cursor_line = 0
        win.cursor_col = 99
        self.assertEqual(win._cursor_to_wrap_row(5), 1)

        win.wrap_mode = False
        win.cursor_col = 1
        self.assertEqual(win._cursor_to_wrap_row(5), 0)

        win.cursor_line = 99
        self.assertEqual(win._cursor_to_wrap_row(5), 0)

    def test_ensure_cursor_visible_moves_view_when_cursor_before_viewport(self):
        win = self._make_window()
        win.wrap_mode = True
        win.buffer = ["x" * 60 for _ in range(4)]
        win.cursor_line = 0
        win.cursor_col = 0
        win.view_top = 3
        win._ensure_cursor_visible()
        self.assertLess(win.view_top, 3)

        win.wrap_mode = False
        win.view_top = 5
        win.view_left = 10
        win.cursor_line = 1
        win.cursor_col = 2
        win._ensure_cursor_visible()
        self.assertEqual(win.view_top, 1)
        self.assertEqual(win.view_left, 2)

    def test_draw_returns_early_when_invisible(self):
        win = self._make_window()
        win.visible = False
        win.draw_frame = mock.Mock()
        win.draw(None)
        win.draw_frame.assert_not_called()

    def test_draw_sets_title_for_unsaved_states(self):
        win = self._make_window()
        win.filepath = None
        win.modified = True
        win.draw_frame = mock.Mock(return_value=0)
        with mock.patch.object(self.notepad_mod, "safe_addstr"):
            win.draw(None)
        self.assertEqual(win.title, "Notepad *")

        win.modified = False
        with mock.patch.object(self.notepad_mod, "safe_addstr"):
            win.draw(None)
        self.assertEqual(win.title, "Notepad")

    def test_draw_wrap_mode_renders_visible_wrapped_rows_and_cursor(self):
        win = self._make_window(w=20, h=10)
        win.wrap_mode = True
        win.buffer = ["abcdefghij", "klmnopqrst"]
        win.cursor_line = 0
        win.cursor_col = 2
        win.draw_frame = mock.Mock(return_value=0)

        with mock.patch.object(self.notepad_mod, "safe_addstr") as safe_addstr:
            win.draw(None)

        attrs = [call.args[4] for call in safe_addstr.call_args_list if len(call.args) >= 5]
        self.assertTrue(any(attr & self.curses.A_REVERSE for attr in attrs))

    def test_draw_non_wrap_breaks_when_buffer_ends(self):
        win = self._make_window(w=20, h=10)
        win.wrap_mode = False
        win.buffer = ["only one line"]
        win.draw_frame = mock.Mock(return_value=0)
        with mock.patch.object(self.notepad_mod, "safe_addstr") as safe_addstr:
            win.draw(None)

        rendered = [call.args[3] for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("only one line" in str(text) for text in rendered))

    def test_handle_key_menu_active_with_no_action_returns_none(self):
        win = self._make_window()
        win.window_menu.active = True
        win.window_menu.handle_key = mock.Mock(return_value=None)
        self.assertIsNone(win.handle_key(10))

    def test_handle_key_up_and_down_move_cursor(self):
        win = self._make_window()
        win.buffer = ["a", "b", "c"]
        win.cursor_line = 1
        win.cursor_col = 0

        win.handle_key(self.curses.KEY_UP)
        self.assertEqual(win.cursor_line, 0)

        win.handle_key(self.curses.KEY_DOWN)
        self.assertEqual(win.cursor_line, 1)

    def test_handle_key_left_and_right_inside_line(self):
        win = self._make_window()
        win.buffer = ["abcd"]
        win.cursor_line = 0
        win.cursor_col = 2

        win.handle_key(self.curses.KEY_LEFT)
        self.assertEqual(win.cursor_col, 1)

        win.handle_key(self.curses.KEY_RIGHT)
        self.assertEqual(win.cursor_col, 2)

    def test_handle_key_backspace_deletes_character(self):
        win = self._make_window()
        win.buffer = ["abcd"]
        win.cursor_line = 0
        win.cursor_col = 2

        win.handle_key(self.curses.KEY_BACKSPACE)

        self.assertEqual(win.buffer[0], "acd")
        self.assertEqual(win.cursor_col, 1)
        self.assertTrue(win.modified)

    def test_handle_key_delete_deletes_character(self):
        win = self._make_window()
        win.buffer = ["abcd"]
        win.cursor_line = 0
        win.cursor_col = 1

        win.handle_key(self.curses.KEY_DC)

        self.assertEqual(win.buffer[0], "acd")
        self.assertTrue(win.modified)

    def test_handle_key_backspace_deletes_selection_when_present(self):
        win = self._make_window()
        win.buffer = ["abcdef"]
        win.selection_anchor = (0, 1)
        win.selection_cursor = (0, 4)

        win.handle_key(self.curses.KEY_BACKSPACE)

        self.assertEqual(win.buffer, ["aef"])
        self.assertEqual((win.cursor_line, win.cursor_col), (0, 1))
        self.assertTrue(win.modified)

    def test_handle_key_delete_deletes_selection_when_present(self):
        win = self._make_window()
        win.buffer = ["abcdef"]
        win.selection_anchor = (0, 2)
        win.selection_cursor = (0, 5)

        win.handle_key(self.curses.KEY_DC)

        self.assertEqual(win.buffer, ["abf"])
        self.assertEqual((win.cursor_line, win.cursor_col), (0, 2))
        self.assertTrue(win.modified)

    def test_handle_key_ctrl_s_returns_save_error_action_result(self):
        win = self._make_window()
        err = self.actions_mod.ActionResult(self.actions_mod.ActionType.SAVE_ERROR, "x")
        win._save_file = mock.Mock(return_value=err)

        result = win.handle_key(19)

        self.assertEqual(result.type, self.actions_mod.ActionType.SAVE_ERROR)

    def test_handle_key_ctrl_o_requests_open_dialog(self):
        win = self._make_window()
        result = win.handle_key(15)
        self.assertEqual(result.type, self.actions_mod.ActionType.REQUEST_OPEN_PATH)

    def test_handle_key_ctrl_a_selects_all(self):
        win = self._make_window()
        win.buffer = ["abc", "defg"]
        win.cursor_line = 0
        win.cursor_col = 1

        win.handle_key(1)

        self.assertEqual(win.selection_anchor, (0, 0))
        self.assertEqual(win.selection_cursor, (1, 4))
        self.assertEqual((win.cursor_line, win.cursor_col), (1, 4))

    def test_handle_key_escape_clears_selection(self):
        win = self._make_window()
        win.selection_anchor = (0, 0)
        win.selection_cursor = (0, 2)

        win.handle_key(27)

        self.assertIsNone(win.selection_anchor)
        self.assertIsNone(win.selection_cursor)

    def test_handle_key_ctrl_x_cuts_selected_text(self):
        win = self._make_window()
        win.buffer = ["abcdef"]
        win.selection_anchor = (0, 1)
        win.selection_cursor = (0, 4)
        with mock.patch.object(self.notepad_mod, "copy_text") as copy_text:
            win.handle_key(24)
        copy_text.assert_called_once_with("bcd")
        self.assertEqual(win.buffer, ["aef"])
        self.assertEqual((win.cursor_line, win.cursor_col), (0, 1))
        self.assertTrue(win.modified)

    def test_handle_key_ctrl_x_without_selection_cuts_current_line(self):
        win = self._make_window()
        win.buffer = ["first", "second"]
        win.cursor_line = 0
        win.cursor_col = 2
        with mock.patch.object(self.notepad_mod, "copy_text") as copy_text:
            win.handle_key(24)
        copy_text.assert_called_once_with("first")
        self.assertEqual(win.buffer, ["second"])
        self.assertEqual((win.cursor_line, win.cursor_col), (0, 2))
        self.assertTrue(win.modified)

    def test_handle_key_copy_shortcut_copies_current_line(self):
        win = self._make_window()
        win.buffer = ["first", "second"]
        win.cursor_line = 1
        with mock.patch.object(self.notepad_mod, "copy_text") as copy_text:
            win.handle_key(self.curses.KEY_F6)
        copy_text.assert_called_once_with("second")

    def test_handle_key_copy_shortcut_prefers_selected_text(self):
        win = self._make_window()
        win.buffer = ["alpha beta"]
        win.selection_anchor = (0, 0)
        win.selection_cursor = (0, 5)
        with mock.patch.object(self.notepad_mod, "copy_text") as copy_text:
            win.handle_key(self.curses.KEY_F6)
        copy_text.assert_called_once_with("alpha")

    def test_handle_key_ctrl_c_no_longer_triggers_copy(self):
        win = self._make_window()
        win.buffer = ["first"]
        win.cursor_line = 0
        with mock.patch.object(self.notepad_mod, "copy_text") as copy_text:
            win.handle_key(3)
        copy_text.assert_not_called()

    def test_handle_key_ctrl_v_pastes_multiline_text(self):
        win = self._make_window()
        win.buffer = ["ab"]
        win.cursor_line = 0
        win.cursor_col = 1
        with mock.patch.object(self.notepad_mod, "paste_text", return_value="X\nY\nZ"):
            win.handle_key(22)
        self.assertEqual(win.buffer, ["aX", "Y", "Zb"])
        self.assertEqual((win.cursor_line, win.cursor_col), (2, 1))
        self.assertTrue(win.modified)

    def test_handle_key_ctrl_v_pastes_single_line_text(self):
        win = self._make_window()
        win.buffer = ["ab"]
        win.cursor_line = 0
        win.cursor_col = 1
        with mock.patch.object(self.notepad_mod, "paste_text", return_value="Q"):
            win.handle_key(22)
        self.assertEqual(win.buffer, ["aQb"])
        self.assertEqual((win.cursor_line, win.cursor_col), (0, 2))
        self.assertTrue(win.modified)

    def test_handle_key_ctrl_v_ignores_empty_clipboard(self):
        win = self._make_window()
        win.buffer = ["ab"]
        win.cursor_line = 0
        win.cursor_col = 1
        with mock.patch.object(self.notepad_mod, "paste_text", return_value=""):
            win.handle_key(22)
        self.assertEqual(win.buffer, ["ab"])
        self.assertEqual((win.cursor_line, win.cursor_col), (0, 1))
        self.assertFalse(win.modified)

    def test_handle_key_int_printable_inserts_character(self):
        win = self._make_window()
        win.buffer = [""]
        win.cursor_col = 0

        result = win.handle_key(65)

        self.assertIsNone(result)
        self.assertEqual(win.buffer[0], "A")
        self.assertEqual(win.cursor_col, 1)
        self.assertTrue(win.modified)

    def test_handle_click_menu_intercept_without_action_returns_none(self):
        win = self._make_window()
        win.window_menu = types.SimpleNamespace(
            on_menu_bar=mock.Mock(return_value=True),
            active=True,
            handle_click=mock.Mock(return_value=None),
        )
        self.assertIsNone(win.handle_click(1, 1))

    def test_handle_click_outside_body_returns_none(self):
        win = self._make_window()
        bx, by, bw, bh = win.body_rect()
        self.assertIsNone(win.handle_click(bx + bw + 5, by + bh + 5))

    def test_handle_click_wrap_mode_in_range_positions_cursor(self):
        win = self._make_window()
        win.wrap_mode = True
        win.buffer = ["abcdefghij"]
        win.view_top = 0
        bx, by, _, _ = win.body_rect()

        win.handle_click(bx + 2, by)

        self.assertEqual(win.cursor_line, 0)
        self.assertEqual(win.cursor_col, 2)

    def test_handle_click_with_button_sets_selection_anchor(self):
        win = self._make_window()
        win.buffer = ["abcdef"]
        bx, by, _, _ = win.body_rect()

        win.handle_click(bx + 1, by, self.curses.BUTTON1_PRESSED)

        self.assertEqual(win.selection_anchor, (0, 1))
        self.assertEqual(win.selection_cursor, (0, 1))

    def test_handle_mouse_drag_extends_selection(self):
        win = self._make_window()
        win.buffer = ["abcdefghij"]
        bx, by, _, _ = win.body_rect()
        win.handle_click(bx + 1, by, self.curses.BUTTON1_PRESSED)

        win.handle_mouse_drag(bx + 4, by, self.curses.BUTTON1_PRESSED | 0x200000)

        self.assertEqual(win.selection_anchor, (0, 1))
        self.assertEqual(win.selection_cursor, (0, 4))

    def test_scroll_up_decrements_view_top(self):
        win = self._make_window()
        win.view_top = 3
        win.scroll_up()
        self.assertEqual(win.view_top, 2)


if __name__ == "__main__":
    unittest.main()

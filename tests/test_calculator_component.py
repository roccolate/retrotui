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
    fake.KEY_BACKSPACE = 263
    fake.KEY_DC = 330
    fake.KEY_F6 = 270
    fake.KEY_F9 = 273
    fake.KEY_IC = 331
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.error = Exception
    fake.color_pair = lambda value: value * 10
    return fake


class CalculatorComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.window",
            "retrotui.core.actions",
            "retrotui.core.clipboard",
            "retrotui.apps.calculator",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.calc_mod = importlib.import_module("retrotui.apps.calculator")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.window",
            "retrotui.core.actions",
            "retrotui.core.clipboard",
            "retrotui.apps.calculator",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_window(self):
        return self.calc_mod.CalculatorWindow(0, 0, 44, 14)

    def test_evaluate_expression_supports_safe_arithmetic(self):
        evaluate = self.calc_mod.evaluate_expression
        self.assertEqual(evaluate("1 + 2 * 3"), "7")
        self.assertEqual(evaluate("(2 + 3) * 4"), "20")
        self.assertEqual(evaluate("-5 + +2"), "-3")
        self.assertEqual(evaluate("7 // 2"), "3")

    def test_evaluate_expression_rejects_unsupported_input(self):
        evaluate = self.calc_mod.evaluate_expression
        with self.assertRaises(ValueError):
            evaluate("")
        with self.assertRaises(ValueError):
            evaluate("name + 1")
        with self.assertRaises(ValueError):
            evaluate("1 << 2")
        with self.assertRaises(ValueError):
            evaluate("~1")

    def test_evaluate_expression_formats_floats_and_normalizes_negative_zero(self):
        evaluate = self.calc_mod.evaluate_expression
        self.assertEqual(evaluate("1/2"), "0.5")
        self.assertEqual(evaluate("-0.0"), "0")

    def test_set_expression_and_insert_delete_helpers(self):
        win = self._make_window()
        win._set_expression("12345")
        self.assertEqual(win.cursor_pos, 5)

        win.cursor_pos = 2
        win._insert_text("+")
        self.assertEqual(win.expression, "12+345")
        self.assertEqual(win.cursor_pos, 3)

        win._delete_backward()
        self.assertEqual(win.expression, "12345")
        self.assertEqual(win.cursor_pos, 2)

        win._delete_forward()
        self.assertEqual(win.expression, "1245")
        self.assertEqual(win.cursor_pos, 2)

    def test_insert_and_delete_guards_and_history_trim(self):
        win = self._make_window()
        win._set_expression("abc")
        win.cursor_pos = 0

        win._insert_text("")
        self.assertEqual(win.expression, "abc")
        self.assertEqual(win.cursor_pos, 0)

        win._delete_backward()
        self.assertEqual(win.expression, "abc")

        win.cursor_pos = len(win.expression)
        win._delete_forward()
        self.assertEqual(win.expression, "abc")

        win.history = [str(i) for i in range(win.MAX_HISTORY)]
        win._append_history("overflow")
        self.assertEqual(len(win.history), win.MAX_HISTORY)
        self.assertEqual(win.history[-1], "overflow")

    def test_ensure_cursor_visible_scrolls_left_and_right(self):
        win = self._make_window()
        win._set_expression("0123456789")

        win.view_left = 5
        win.cursor_pos = 2
        win._ensure_cursor_visible(input_width=3)
        self.assertEqual(win.view_left, 2)

        win.view_left = 0
        win.cursor_pos = 9
        win._ensure_cursor_visible(input_width=3)
        self.assertEqual(win.view_left, 7)

    def test_evaluate_current_success_and_error_history(self):
        win = self._make_window()
        win.expression = "2+3"
        win.cursor_pos = 3
        win._evaluate_current()
        self.assertEqual(win.last_result, "5")
        self.assertEqual(win.expression, "5")
        self.assertIn("2+3 = 5", win.history[-1])

        win.expression = "1/0"
        win.cursor_pos = 3
        win._evaluate_current()
        self.assertTrue(any("1/0 ! " in line for line in win.history))

    def test_evaluate_current_is_noop_when_expression_is_blank(self):
        win = self._make_window()
        win.expression = "   "
        win.cursor_pos = 3
        win._evaluate_current()
        self.assertEqual(win.history, [])

    def test_history_navigation_moves_expression(self):
        win = self._make_window()
        win.history = ["1+1 = 2", "2+2 = 4", "9/0 ! division by zero"]

        win._history_move(-1)
        self.assertEqual(win.expression, "9/0")
        win._history_move(-1)
        self.assertEqual(win.expression, "2+2")
        win._history_move(1)
        self.assertEqual(win.expression, "9/0")
        win._history_move(1)
        self.assertEqual(win.expression, "")

    def test_history_move_guard_and_clamps_index(self):
        win = self._make_window()
        win._history_move(-1)
        self.assertIsNone(win.history_index)

        win.history = ["1+1 = 2"]
        win.history_index = 0
        win._history_move(-1)
        self.assertEqual(win.history_index, 0)

        entries = win._history_expr_only()
        win.history_index = len(entries)
        win._history_move(1)
        self.assertEqual(win.history_index, len(entries))

    def test_handle_key_basic_editing_and_navigation(self):
        win = self._make_window()
        win.handle_key("1")
        win.handle_key(ord("+"))
        win.handle_key("2")
        self.assertEqual(win.expression, "1+2")

        win.handle_key(self.curses.KEY_LEFT)
        win.handle_key(self.curses.KEY_BACKSPACE)
        self.assertEqual(win.expression, "12")

        win.handle_key(self.curses.KEY_HOME)
        self.assertEqual(win.cursor_pos, 0)
        win.handle_key(self.curses.KEY_END)
        self.assertEqual(win.cursor_pos, len(win.expression))

    def test_handle_key_right_delete_and_history_keys(self):
        win = self._make_window()
        win._set_expression("ab")
        win.cursor_pos = 0

        win.handle_key(self.curses.KEY_RIGHT)
        self.assertEqual(win.cursor_pos, 1)

        win.cursor_pos = 1
        win.handle_key(self.curses.KEY_DC)
        self.assertEqual(win.expression, "a")

        win.history = ["2+2 = 4", "3+3 = 6"]
        win._set_expression("")
        win.handle_key(self.curses.KEY_UP)
        self.assertTrue(win.expression)
        win.handle_key(self.curses.KEY_DOWN)
        self.assertIn(win.expression, ("", "3+3"))

    def test_handle_key_evaluate_clear_and_close_paths(self):
        win = self._make_window()
        win.handle_key("3")
        win.handle_key("*")
        win.handle_key("4")
        win.handle_key(10)
        self.assertEqual(win.last_result, "12")

        with mock.patch.object(self.calc_mod, "copy_text") as copy_text:
            win.handle_key(self.curses.KEY_F6)
            win.handle_key(self.curses.KEY_IC)
        self.assertEqual(copy_text.call_count, 2)

        win.handle_key(12)  # Ctrl+L
        self.assertEqual(win.history, [])
        win.handle_key(27)  # Esc
        self.assertEqual(win.expression, "")

        win.handle_key("9")
        win.handle_key(24)  # Ctrl+X
        self.assertEqual(win.expression, "")

        close_result = win.handle_key(17)  # Ctrl+Q
        self.assertEqual(close_result.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(close_result.payload, self.actions_mod.AppAction.CLOSE_WINDOW)

    def test_draw_returns_early_when_hidden_or_body_zero(self):
        win = self._make_window()
        win.visible = False
        with mock.patch.object(self.calc_mod, "safe_addstr") as safe_addstr:
            win.draw(None)
        safe_addstr.assert_not_called()

        win.visible = True
        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(win, "body_rect", return_value=(0, 0, 10, 0)),
            mock.patch.object(self.calc_mod, "safe_addstr") as safe_addstr,
        ):
            win.draw(None)
        safe_addstr.assert_not_called()

    def test_draw_renders_cursor_character_when_in_bounds(self):
        win = self._make_window()
        win.expression = "abc"
        win.cursor_pos = 1
        win.view_left = 0

        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.calc_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(self.calc_mod, "theme_attr", return_value=0),
        ):
            win.draw(None)

        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertIn("b", "".join(rendered))

    def test_calculator_starts_topmost_and_f9_toggles(self):
        win = self._make_window()
        self.assertTrue(win.always_on_top)
        win.handle_key(self.curses.KEY_F9)
        self.assertFalse(win.always_on_top)
        win.handle_key(self.curses.KEY_F9)
        self.assertTrue(win.always_on_top)

    def test_handle_key_paste_and_ctrl_c_copy(self):
        win = self._make_window()
        with mock.patch.object(self.calc_mod, "paste_text", return_value="7*6") as paste_text:
            win.handle_key(22)  # Ctrl+V
        paste_text.assert_called_once_with()
        self.assertEqual(win.expression, "7*6")

        win.handle_key(10)
        with mock.patch.object(self.calc_mod, "copy_text") as copy_text:
            win.handle_key(3)  # Ctrl+C
        copy_text.assert_called_once_with("42")

    def test_handle_click_positions_cursor_on_input_row(self):
        win = self._make_window()
        win._set_expression("123456")
        bx, by, _, _ = win.body_rect()
        win.handle_click(bx + 8, by)
        self.assertEqual(win.cursor_pos, 2)
        self.assertIsNone(win.handle_click(999, 999))

    def test_draw_renders_input_history_and_status(self):
        win = self._make_window()
        win.history = ["1+1 = 2", "2+2 = 4"]
        win._set_expression("12+30")

        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.calc_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(self.calc_mod, "theme_attr", return_value=0),
        ):
            win.draw(None)

        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("Expr>" in text for text in rendered))
        self.assertTrue(any("1+1 = 2" in text for text in rendered))
        self.assertTrue(any("Ctrl+L=Clear" in text for text in rendered))


if __name__ == "__main__":
    unittest.main()

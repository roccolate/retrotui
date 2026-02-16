import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_LEFT = 260
    fake.KEY_RIGHT = 261
    fake.KEY_ENTER = 343
    fake.KEY_BACKSPACE = 263
    fake.KEY_DC = 330
    fake.A_BOLD = 1
    fake.A_DIM = 2
    fake.A_REVERSE = 4
    fake.color_pair = lambda value: value * 10
    fake.error = Exception
    return fake


class DialogComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.dialog",
        ):
            sys.modules.pop(mod_name, None)

        cls.dialog_mod = importlib.import_module("retrotui.ui.dialog")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.dialog",
        ):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_dialog_wraps_message_and_computes_height(self):
        message = "line one has words\n\nline three"
        dialog = self.dialog_mod.Dialog("Title", message, ["Yes", "No"], width=20)

        self.assertGreaterEqual(len(dialog.lines), 3)
        self.assertEqual(dialog.height, len(dialog.lines) + 7)
        self.assertEqual(dialog.buttons, ["Yes", "No"])

    def test_dialog_draw_and_click_resolves_button_index(self):
        dialog = self.dialog_mod.Dialog("Confirm", "Proceed?", ["Yes", "No"], width=30)
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(24, 80)))

        with (
            mock.patch.object(self.dialog_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(self.dialog_mod, "draw_box") as draw_box,
        ):
            dialog.draw(stdscr)

        draw_box.assert_called_once()
        self.assertGreater(safe_addstr.call_count, 0)
        self.assertGreater(dialog._btn_x_start, 0)
        self.assertGreater(dialog._btn_y, 0)
        self.assertEqual(dialog.handle_click(dialog._btn_x_start, dialog._btn_y), 0)
        second_btn_x = dialog._btn_x_start + (len("Yes") + 4) + 2
        self.assertEqual(dialog.handle_click(second_btn_x, dialog._btn_y), 1)
        self.assertEqual(dialog.handle_click(dialog._btn_x_start, dialog._btn_y + 1), -1)

    def test_dialog_key_navigation_and_submit(self):
        dialog = self.dialog_mod.Dialog("Confirm", "Proceed?", ["Yes", "No", "Cancel"])

        self.assertEqual(dialog.handle_key(self.curses.KEY_RIGHT), -1)
        self.assertEqual(dialog.selected, 1)
        self.assertEqual(dialog.handle_key(self.curses.KEY_LEFT), -1)
        self.assertEqual(dialog.selected, 0)
        self.assertEqual(dialog.handle_key(10), 0)
        self.assertEqual(dialog.handle_key(27), 2)  # Esc -> last button

    def test_input_dialog_handle_key_editing_and_actions(self):
        dialog = self.dialog_mod.InputDialog("Save As", "Name:", initial_value="ab", width=24)

        dialog.handle_key(self.curses.KEY_LEFT)
        self.assertEqual(dialog.cursor_pos, 1)
        dialog.handle_key(self.curses.KEY_RIGHT)
        self.assertEqual(dialog.cursor_pos, 2)
        dialog.handle_key("x")
        self.assertEqual(dialog.value, "abx")
        self.assertEqual(dialog.cursor_pos, 3)
        dialog.handle_key(121)  # 'y'
        self.assertEqual(dialog.value, "abxy")
        dialog.handle_key(self.curses.KEY_BACKSPACE)
        self.assertEqual(dialog.value, "abx")
        dialog.handle_key(self.curses.KEY_LEFT)
        dialog.handle_key(self.curses.KEY_DC)
        self.assertEqual(dialog.value, "ab")

        self.assertEqual(dialog.handle_key(10), 0)   # OK
        self.assertEqual(dialog.handle_key(27), 1)   # Cancel

    def test_input_dialog_draw_truncates_long_value_and_draws_cursor(self):
        dialog = self.dialog_mod.InputDialog("Save As", "Name:", initial_value="abcdefghijklmnopqrstuvwxyz", width=20)
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(24, 80)))

        with mock.patch.object(self.dialog_mod, "safe_addstr") as safe_addstr:
            dialog.draw(stdscr)

        # One of the draw calls should include a truncated tail of the value.
        self.assertTrue(
            any("uvwxyz" in str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4)
        )
        # Cursor draw uses reverse attribute; last call is usually the cursor.
        self.assertGreater(safe_addstr.call_count, 0)

    def test_input_dialog_draw_short_value_uses_cursor_pos_branch(self):
        dialog = self.dialog_mod.InputDialog("Save As", "Name:", initial_value="abc", width=24)
        dialog.cursor_pos = 1
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(24, 80)))

        with mock.patch.object(self.dialog_mod, "safe_addstr") as safe_addstr:
            dialog.draw(stdscr)

        cursor_calls = [
            call for call in safe_addstr.call_args_list
            if len(call.args) >= 5 and (call.args[4] & self.curses.A_REVERSE)
        ]
        self.assertTrue(cursor_calls)
        self.assertEqual(cursor_calls[-1].args[2], 33)

    def test_input_dialog_handle_click_delegates_to_base_dialog(self):
        dialog = self.dialog_mod.InputDialog("Save As", "Name:", initial_value="", width=24)
        with mock.patch.object(self.dialog_mod.Dialog, "handle_click", return_value=1) as handle_click:
            result = dialog.handle_click(10, 10)

        self.assertEqual(result, 1)
        handle_click.assert_called_once_with(10, 10)

    def test_progress_dialog_draw_updates_spinner_and_is_non_interactive(self):
        dialog = self.dialog_mod.ProgressDialog("Copying", "Please wait...", width=28)
        dialog.set_elapsed(1.25)
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(24, 80)))

        with (
            mock.patch.object(self.dialog_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(self.dialog_mod, "draw_box") as draw_box,
        ):
            dialog.draw(stdscr)

        draw_box.assert_called_once()
        self.assertGreater(safe_addstr.call_count, 0)
        self.assertEqual(dialog.handle_click(10, 10), -1)
        self.assertEqual(dialog.handle_key(10), -1)

    def test_progress_dialog_wraps_empty_paragraphs(self):
        dialog = self.dialog_mod.ProgressDialog("Move", "line1\n\nline3", width=30)
        self.assertIn("", dialog.lines)


if __name__ == "__main__":
    unittest.main()

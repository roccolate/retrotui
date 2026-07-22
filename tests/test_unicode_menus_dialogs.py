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
    fake.A_BOLD = 1
    fake.A_DIM = 2
    fake.A_REVERSE = 4
    fake.error = Exception
    fake.color_pair = lambda _: 0
    return fake


class UnicodeMenusDialogsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()
        for name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
        ):
            sys.modules.pop(name, None)
        cls.utils = importlib.import_module("retrotui.utils")
        cls.menu_mod = importlib.import_module("retrotui.ui.menu")
        cls.dialog_mod = importlib.import_module("retrotui.ui.dialog")

    @classmethod
    def tearDownClass(cls):
        for name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
        ):
            sys.modules.pop(name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_pad_text_columns_preserves_combining_and_exact_width(self):
        padded = self.utils.pad_text_columns("e\u0301你", 5)
        self.assertTrue(padded.startswith("e\u0301你"))
        self.assertEqual(self.utils.text_display_width(padded), 5)

        clipped = self.utils.pad_text_columns("你你你", 4, suffix="…")
        self.assertEqual(self.utils.text_display_width(clipped), 4)
        self.assertIn("…", clipped)

    def test_menu_positions_use_physical_columns(self):
        menu = self.menu_mod.MenuBar({
            "文件": [("打开", "open")],
            "编辑": [("复制", "copy")],
        })
        self.assertEqual(menu.get_menu_x_positions(), [2, 9])
        self.assertEqual(menu.menu_items_right_x(), 15)

    def test_menu_click_hitbox_matches_rendered_columns(self):
        menu = self.menu_mod.MenuBar({
            "文件": [("打开", "open")],
            "编辑": [("复制", "copy")],
        })
        second_x = menu.get_menu_x_positions()[1]
        self.assertFalse(menu.hit_test_menu_item(second_x - 1, 0))
        menu.handle_click(second_x, 0)
        self.assertTrue(menu.active)
        self.assertEqual(menu.selected_menu, 1)

    def test_dropdown_rows_clip_and_pad_to_physical_width(self):
        menu = self.menu_mod.MenuBar({"文件": [("你" * 12, "open")]})
        menu.active = True
        menu._set_viewport(width=10, height=10)
        layout = menu._dropdown_layout()
        self.assertIsNotNone(layout)
        x, y, dropdown_w, _items = layout
        safe_addstr = mock.Mock()
        draw_globals = self.menu_mod.MenuBar.draw_dropdown.__globals__
        with mock.patch.dict(
            draw_globals,
            {
                "draw_box": mock.Mock(),
                "safe_addstr": safe_addstr,
                "theme_attr": mock.Mock(return_value=0),
            },
        ):
            menu.draw_dropdown(types.SimpleNamespace())
        row = next(
            call.args[3]
            for call in safe_addstr.call_args_list
            if call.args[1] == y + 1 and call.args[2] == x
        )
        self.assertEqual(self.utils.text_display_width(row), dropdown_w)
        self.assertIn("…", row)

    def test_dialog_message_wraps_by_physical_columns(self):
        lines = self.dialog_mod._wrap_dialog_message("你你你 AB", 4)
        self.assertTrue(lines)
        self.assertTrue(
            all(self.utils.text_display_width(line) <= 4 for line in lines)
        )
        self.assertEqual(lines[:2], ["你你", "你"])

    def test_dialog_button_layout_and_hitboxes_use_physical_columns(self):
        dialog = self.dialog_mod.Dialog(
            "标题",
            "message",
            buttons=["确认", "Cancel"],
            width=20,
        )
        self.assertEqual(dialog.width, 24)
        draw_globals = self.dialog_mod.Dialog.draw.__globals__
        with mock.patch.dict(
            draw_globals,
            {
                "draw_box": mock.Mock(),
                "safe_addstr": mock.Mock(),
                "theme_attr": mock.Mock(return_value=0),
            },
        ):
            dialog.draw(types.SimpleNamespace(), frame_size=(24, 80))
        first_width = self.utils.text_display_width("确认") + 4
        second_x = dialog._btn_x_start + first_width + 2
        self.assertEqual(dialog.handle_click(dialog._btn_x_start, dialog._btn_y), 0)
        self.assertEqual(dialog.handle_click(second_x, dialog._btn_y), 1)
        self.assertEqual(dialog.handle_click(second_x - 1, dialog._btn_y), -1)

    def test_dialog_title_row_fills_exact_physical_width(self):
        dialog = self.dialog_mod.Dialog("标题🙂", "message", width=24)
        safe_addstr = mock.Mock()
        draw_globals = self.dialog_mod.Dialog.draw.__globals__
        with mock.patch.dict(
            draw_globals,
            {
                "draw_box": mock.Mock(),
                "safe_addstr": safe_addstr,
                "theme_attr": mock.Mock(return_value=0),
            },
        ):
            dialog.draw(types.SimpleNamespace(), frame_size=(24, 80))
        title_call = next(
            call
            for call in safe_addstr.call_args_list
            if call.args[1] == dialog._dialog_y
            and call.args[2] == dialog._dialog_x + 1
        )
        self.assertEqual(
            self.utils.text_display_width(title_call.args[3]),
            dialog.width - 2,
        )

    def test_multiselect_rows_fit_physical_list_width(self):
        dialog = self.dialog_mod.MultiSelectDialog(
            "选择",
            "message",
            [("你" * 30, "value", True)],
            width=24,
        )
        safe_addstr = mock.Mock()
        draw_globals = self.dialog_mod.MultiSelectDialog.draw.__globals__
        with mock.patch.dict(
            draw_globals,
            {
                "draw_box": mock.Mock(),
                "safe_addstr": safe_addstr,
                "theme_attr": mock.Mock(return_value=0),
            },
        ):
            dialog.draw(types.SimpleNamespace(), frame_size=(40, 100))
        list_w = dialog.width - 6
        row = next(
            call.args[3]
            for call in safe_addstr.call_args_list
            if isinstance(call.args[3], str) and "[x]" in call.args[3]
        )
        self.assertEqual(self.utils.text_display_width(row), list_w)
        self.assertIn("…", row)

    def test_progress_dialog_title_uses_physical_columns(self):
        dialog = self.dialog_mod.ProgressDialog("进度🙂", "message", width=20)
        self.assertEqual(dialog.width, 20)
        safe_addstr = mock.Mock()
        draw_globals = self.dialog_mod.ProgressDialog.draw.__globals__
        with mock.patch.dict(
            draw_globals,
            {
                "draw_box": mock.Mock(),
                "safe_addstr": safe_addstr,
                "theme_attr": mock.Mock(return_value=0),
            },
        ):
            dialog.draw(types.SimpleNamespace(), frame_size=(30, 80))
        title_call = next(
            call
            for call in safe_addstr.call_args_list
            if call.args[1] == (30 - dialog.height) // 2
            and call.args[2] == (80 - dialog.width) // 2 + 1
        )
        self.assertEqual(
            self.utils.text_display_width(title_call.args[3]),
            dialog.width - 2,
        )


if __name__ == "__main__":
    unittest.main()

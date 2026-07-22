import types
import unittest
from unittest import mock

from retrotui.apps import app_manager, process_manager
from retrotui.apps.filemanager.core import FileEntry, _fit_text_to_cells
from retrotui.core import rendering
from retrotui.core.icon_manager import IconPositionManager, icon_render_metrics
from retrotui.ui.window import Window
from retrotui.utils import center_text_columns, text_display_width


class UnicodeIconAndListTests(unittest.TestCase):
    def test_center_text_columns_preserves_exact_width(self):
        centered = center_text_columns("界é", 8)

        self.assertEqual(text_display_width(centered), 8)
        self.assertEqual(centered.strip(), "界é")
        self.assertLessEqual(
            abs(len(centered) - len(centered.lstrip()) - (len(centered) - len(centered.rstrip()))),
            1,
        )

    def test_file_entry_name_field_uses_physical_columns(self):
        name = "報告書é🙂" * 8
        with mock.patch("retrotui.apps.filemanager.core.os.access", return_value=False):
            entry = FileEntry(name, False, "/tmp/report", 123, use_unicode=True)

        self.assertEqual(text_display_width(entry.display_text), 44)
        self.assertTrue(entry.display_text.endswith("    123B"))
        self.assertIn("…", entry.display_text)
        self.assertEqual(text_display_width(_fit_text_to_cells("A界éZ", 8)), 8)

    def test_icon_hitbox_matches_unicode_render_width(self):
        icon = {"symbol": "界", "label": "設定🙂設定🙂設定"}
        app = types.SimpleNamespace(
            icons=[icon],
            stdscr=types.SimpleNamespace(getmaxyx=lambda: (24, 80)),
            persist_config=lambda: None,
        )
        manager = IconPositionManager(app)
        manager.positions["設定🙂設定🙂設定"] = (3, 4)
        _lines, render_height, render_width = icon_render_metrics(icon)

        self.assertEqual(manager.get_icon_at(3 + render_width - 1, 4), 0)
        self.assertEqual(manager.get_icon_at(3 + render_width, 4), -1)
        self.assertEqual(manager.get_icon_at(3, 4 + render_height), 0)
        self.assertEqual(manager.get_icon_at(3, 4 + render_height + 1), -1)

    def test_desktop_icon_rows_have_exact_physical_width(self):
        icon = {"symbol": "界", "label": "設定🙂設定🙂設定"}
        app = types.SimpleNamespace(
            stdscr=types.SimpleNamespace(),
            icons=[icon],
            selected_icon=-1,
            get_icon_screen_pos=lambda index, frame_size=None: (2, 2),
        )
        _lines, render_height, render_width = icon_render_metrics(icon)

        with (
            mock.patch.object(rendering, "safe_addstr") as safe_addstr,
            mock.patch.object(rendering, "theme_attr", return_value=0),
        ):
            rendering.draw_icons(app, frame_size=(20, 40))

        rendered = [
            call.args[3]
            for call in safe_addstr.call_args_list
            if call.args[1] in (2, 2 + render_height)
        ]
        self.assertEqual(len(rendered), 2)
        self.assertTrue(all(text_display_width(text) == render_width for text in rendered))

    def test_selection_editor_uses_physical_tab_and_button_ranges(self):
        editor = app_manager._BaseSelectionEditorWindow.__new__(
            app_manager._BaseSelectionEditorWindow
        )
        editor.visible = True
        editor.active = True
        editor.x = 1
        editor.y = 1
        editor.w = 36
        editor.h = 16
        editor.in_list = True
        editor.selected_button = 0
        editor.buttons = ["保存", "取消"]
        editor._tab_ranges = []
        editor._btn_ranges = []
        editor._help_text = "管理🙂插件"
        editor._status_text = "選択é"
        editor.categories = ["插件"]
        editor.choices = {"插件": [["設定🙂", "plugin:test", True]]}
        editor.active_cat_idx = 0
        editor.sel_indices = {"插件": 0}
        editor.offsets = {"插件": 0}

        with (
            mock.patch.object(Window, "draw", return_value=None),
            mock.patch.object(app_manager, "safe_addstr") as safe_addstr,
            mock.patch.object(app_manager, "draw_box"),
            mock.patch.object(app_manager, "theme_attr", return_value=0),
        ):
            editor.draw(types.SimpleNamespace(), frame_size=(30, 80))

        tab = " 插件 "
        self.assertEqual(
            editor._tab_ranges[0][1] - editor._tab_ranges[0][0],
            text_display_width(tab),
        )
        for start, end, idx in editor._btn_ranges:
            self.assertEqual(
                end - start,
                text_display_width(f"[ {editor.buttons[idx]} ]"),
            )
        list_w = editor._list_rect()[2]
        row_texts = [
            call.args[3]
            for call in safe_addstr.call_args_list
            if call.args[1] == editor._list_rect()[1]
            and call.args[2] == editor._list_rect()[0]
        ]
        self.assertTrue(row_texts)
        self.assertEqual(text_display_width(row_texts[0]), list_w)

    def test_process_rows_clip_by_terminal_columns(self):
        window = process_manager.ProcessManagerWindow.__new__(
            process_manager.ProcessManagerWindow
        )
        window.visible = True
        window.active = True
        window.rows = [
            process_manager.ProcessRow(7, 1.2, 3.4, "命令🙂é-long-command", 1)
        ]
        window.selected_index = 0
        window.scroll_offset = 0
        window.sort_key = "cmd"
        window.sort_reverse = False
        window.summary_uptime = "01h 00m"
        window.summary_load = "0.10 0.20 0.30"
        window.summary_mem = "1MB/2MB"
        window._error_message = None
        window.window_menu = None
        window.draw_frame = lambda stdscr: 0
        window.body_rect = lambda: (1, 1, 24, 6)
        window._visible_rows = lambda: 3
        window._max_scroll = lambda: 0

        with (
            mock.patch.object(process_manager, "safe_addstr") as safe_addstr,
            mock.patch.object(process_manager, "theme_attr", return_value=0),
        ):
            window.draw(types.SimpleNamespace())

        fitted = [
            call.args[3]
            for call in safe_addstr.call_args_list
            if call.args[2] == 1 and isinstance(call.args[3], str)
        ]
        self.assertTrue(fitted)
        self.assertTrue(all(text_display_width(text) == 24 for text in fitted))


if __name__ == "__main__":
    unittest.main()

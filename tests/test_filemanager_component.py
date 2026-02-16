import importlib
import pathlib
import shutil
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
    fake.A_BOLD = 1
    fake.error = Exception
    fake.color_pair = lambda value: value * 10
    return fake


def _make_tmp_dir(name: str) -> pathlib.Path:
    root = pathlib.Path("tests") / f"_tmp_filemanager_component_{name}"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    return root


class FileManagerComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.apps.filemanager",
            "retrotui.core.actions",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.fm_mod = importlib.import_module("retrotui.apps.filemanager")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.apps.filemanager",
            "retrotui.core.actions",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_window(self, start_path="."):
        return self.fm_mod.FileManagerWindow(0, 0, 50, 14, start_path=start_path)

    def test_file_entry_size_format_units(self):
        small = self.fm_mod.FileEntry("a.bin", False, "/tmp/a.bin", size=99, use_unicode=False)
        kilo = self.fm_mod.FileEntry("b.bin", False, "/tmp/b.bin", size=2048, use_unicode=False)
        mega = self.fm_mod.FileEntry("c.bin", False, "/tmp/c.bin", size=2_500_000, use_unicode=False)

        self.assertIn("99B", small.display_text)
        self.assertIn("2.0K", kilo.display_text)
        self.assertIn("2.4M", mega.display_text)

    def test_index_helpers_map_between_content_and_entries(self):
        win = self._make_window()
        self.assertEqual(win._header_lines(), 2)
        self.assertEqual(win._entry_to_content_index(0), 2)
        self.assertEqual(win._content_to_entry_index(0), -1)
        self.assertEqual(win._content_to_entry_index(2), 0)

    def test_rebuild_content_empty_directory_placeholder(self):
        win = self._make_window()
        with (
            mock.patch("retrotui.apps.filemanager.os.path.dirname", return_value=win.current_path),
            mock.patch("retrotui.apps.filemanager.os.listdir", return_value=[]),
        ):
            win._rebuild_content()

        self.assertIn("(empty directory)", "\n".join(win.content))

    def test_update_title_excludes_parent_entry_from_count(self):
        win = self._make_window()
        win.entries = [
            self.fm_mod.FileEntry("..", True, "/tmp"),
            self.fm_mod.FileEntry("dir", True, "/tmp/dir"),
            self.fm_mod.FileEntry("file.txt", False, "/tmp/file.txt"),
        ]
        win._update_title()
        self.assertIn("(2 items)", win.title)

    def test_draw_highlight_and_dropdown_path(self):
        win = self._make_window()
        win.visible = True
        win.entries = [self.fm_mod.FileEntry("a.txt", False, "/tmp/a.txt", 1)]
        win.content = ["path", "sep", win.entries[0].display_text]
        win.selected_index = 0
        win.scroll_offset = 0
        win.window_menu.active = True

        with (
            mock.patch.object(self.fm_mod.Window, "draw", return_value=None),
            mock.patch.object(self.fm_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(win.window_menu, "draw_dropdown") as draw_dropdown,
        ):
            win.draw(None)

        self.assertGreater(safe_addstr.call_count, 0)
        draw_dropdown.assert_called_once()

    def test_draw_returns_early_when_no_entries(self):
        win = self._make_window()
        win.visible = True
        win.entries = []
        with (
            mock.patch.object(self.fm_mod.Window, "draw", return_value=None),
            mock.patch.object(self.fm_mod, "safe_addstr") as safe_addstr,
        ):
            win.draw(None)
        safe_addstr.assert_not_called()

    def test_navigate_to_ignores_non_directory(self):
        win = self._make_window()
        old_path = win.current_path
        with mock.patch("retrotui.apps.filemanager.os.path.isdir", return_value=False):
            win.navigate_to("/definitely-not-a-dir")
        self.assertEqual(win.current_path, old_path)

    def test_navigate_parent_noop_when_already_root(self):
        win = self._make_window()
        win.current_path = "/same"
        with mock.patch("retrotui.apps.filemanager.os.path.dirname", return_value="/same"):
            win.navigate_parent()
        self.assertEqual(win.current_path, "/same")

    def test_activate_selected_handles_empty_and_out_of_range(self):
        win = self._make_window()
        win.entries = []
        self.assertIsNone(win.activate_selected())

        win.entries = [self.fm_mod.FileEntry("a", True, "/tmp/a")]
        win.selected_index = 9
        self.assertIsNone(win.activate_selected())

    def test_select_up_down_and_ensure_visible(self):
        win = self._make_window()
        win.entries = [self.fm_mod.FileEntry(str(i), True, f"/tmp/{i}") for i in range(30)]
        win.selected_index = 0
        win.scroll_offset = 10

        win.select_up()
        self.assertEqual(win.selected_index, 0)

        win._ensure_visible()
        self.assertLessEqual(win.scroll_offset, win._entry_to_content_index(win.selected_index))

        win.selected_index = len(win.entries) - 2
        win.select_down()
        self.assertEqual(win.selected_index, len(win.entries) - 1)

    def test_execute_menu_action_branches(self):
        win = self._make_window()
        win.activate_selected = mock.Mock(return_value="open-result")
        win.navigate_parent = mock.Mock()
        win.toggle_hidden = mock.Mock()
        win._rebuild_content = mock.Mock()

        self.assertEqual(win._execute_menu_action(self.actions_mod.AppAction.FM_OPEN), "open-result")
        self.assertIsNone(win._execute_menu_action(self.actions_mod.AppAction.FM_PARENT))
        self.assertIsNone(win._execute_menu_action(self.actions_mod.AppAction.FM_TOGGLE_HIDDEN))
        self.assertIsNone(win._execute_menu_action(self.actions_mod.AppAction.FM_REFRESH))
        close_result = win._execute_menu_action(self.actions_mod.AppAction.FM_CLOSE)
        self.assertEqual(close_result.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(close_result.payload, self.actions_mod.AppAction.CLOSE_WINDOW)
        self.assertIsNone(win._execute_menu_action("unknown"))

    def test_handle_click_paths(self):
        win = self._make_window()
        win.window_menu.on_menu_bar = mock.Mock(return_value=True)
        win.window_menu.handle_click = mock.Mock(return_value=self.actions_mod.AppAction.FM_CLOSE)

        menu_result = win.handle_click(1, 1)
        self.assertEqual(menu_result.type, self.actions_mod.ActionType.EXECUTE)

        win.window_menu.on_menu_bar = mock.Mock(return_value=False)
        win.window_menu.active = False
        win.entries = [self.fm_mod.FileEntry("a.txt", False, "/tmp/a.txt", 1)]
        win.content = ["path", "sep", win.entries[0].display_text]
        win.activate_selected = mock.Mock(return_value="activated")
        bx, by, _, _ = win.body_rect()

        self.assertEqual(win.handle_click(bx, by), None)  # header row
        self.assertEqual(win.handle_click(bx, by + 2), "activated")  # entry row
        self.assertIsNone(win.handle_click(999, 999))

    def test_handle_click_menu_intercept_without_action_returns_none(self):
        win = self._make_window()
        win.window_menu.on_menu_bar = mock.Mock(return_value=True)
        win.window_menu.handle_click = mock.Mock(return_value=None)
        self.assertIsNone(win.handle_click(1, 1))

    def test_handle_key_menu_active_and_navigation(self):
        win = self._make_window()
        win.window_menu.active = True
        win.window_menu.handle_key = mock.Mock(return_value=None)
        self.assertIsNone(win.handle_key(10))

        win.window_menu.handle_key = mock.Mock(return_value=self.actions_mod.AppAction.FM_CLOSE)
        close_result = win.handle_key(10)
        self.assertEqual(close_result.type, self.actions_mod.ActionType.EXECUTE)

        win.window_menu.active = False
        win.entries = [self.fm_mod.FileEntry(str(i), True, f"/tmp/{i}") for i in range(5)]
        win.selected_index = 0
        win.handle_key(self.curses.KEY_END)
        self.assertEqual(win.selected_index, 4)
        win.handle_key(self.curses.KEY_HOME)
        self.assertEqual(win.selected_index, 0)

    def test_handle_key_up_down_enter_and_backspace_paths(self):
        win = self._make_window()
        win.window_menu.active = False
        win.entries = [self.fm_mod.FileEntry(str(i), True, f"/tmp/{i}") for i in range(3)]
        win.selected_index = 1
        win.activate_selected = mock.Mock(return_value="activated")
        win.navigate_parent = mock.Mock()

        win.handle_key(self.curses.KEY_UP)
        self.assertEqual(win.selected_index, 0)

        win.handle_key(self.curses.KEY_DOWN)
        self.assertEqual(win.selected_index, 1)

        self.assertEqual(win.handle_key(10), "activated")
        win.handle_key(self.curses.KEY_BACKSPACE)
        win.navigate_parent.assert_called_once_with()

    def test_handle_scroll_and_toggle_hidden_key(self):
        root = _make_tmp_dir("scroll")
        try:
            for i in range(5):
                (root / f"f{i}.txt").write_text("x", encoding="utf-8")
            win = self._make_window(start_path=str(root))
            start = win.selected_index
            win.handle_scroll("down", steps=2)
            self.assertGreaterEqual(win.selected_index, start)
            win.handle_scroll("up", steps=2)
            self.assertLessEqual(win.selected_index, start + 2)
            # Unknown direction should not crash or move.
            current = win.selected_index
            win.handle_scroll("noop", steps=3)
            self.assertEqual(win.selected_index, current)

            hidden_before = win.show_hidden
            win.handle_key(ord("h"))
            self.assertNotEqual(win.show_hidden, hidden_before)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

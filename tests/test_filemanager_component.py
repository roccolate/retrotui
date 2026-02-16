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
    fake.KEY_DC = 330
    fake.KEY_F2 = 266
    fake.KEY_F4 = 268
    fake.KEY_F5 = 269
    fake.KEY_IC = 331
    fake.KEY_F6 = 270
    fake.KEY_F7 = 271
    fake.KEY_F8 = 272
    fake.BUTTON1_PRESSED = 0x0002
    fake.BUTTON1_CLICKED = 0x0004
    fake.BUTTON1_DOUBLE_CLICKED = 0x0008
    fake.REPORT_MOUSE_POSITION = 0x200000
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
            "retrotui.core.clipboard",
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
            "retrotui.core.clipboard",
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

    def test_fit_text_to_cells_handles_wide_chars(self):
        fit = self.fm_mod._fit_text_to_cells
        width = lambda s: sum(self.fm_mod._cell_width(ch) for ch in s)

        fitted = fit("  📁 folder", 8)
        self.assertEqual(width(fitted), 8)
        self.assertTrue(fitted.startswith("  📁"))
        self.assertEqual(self.fm_mod._cell_width(""), 0)
        self.assertEqual(self.fm_mod._cell_width("\u0301"), 0)
        self.assertEqual(fit("abc", 0), "")

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
        copy_result = win._execute_menu_action(self.actions_mod.AppAction.FM_COPY)
        move_result = win._execute_menu_action(self.actions_mod.AppAction.FM_MOVE)
        rename_result = win._execute_menu_action(self.actions_mod.AppAction.FM_RENAME)
        delete_result = win._execute_menu_action(self.actions_mod.AppAction.FM_DELETE)
        new_dir_result = win._execute_menu_action(self.actions_mod.AppAction.FM_NEW_DIR)
        new_file_result = win._execute_menu_action(self.actions_mod.AppAction.FM_NEW_FILE)
        self.assertIsNone(win._execute_menu_action(self.actions_mod.AppAction.FM_PARENT))
        self.assertIsNone(win._execute_menu_action(self.actions_mod.AppAction.FM_TOGGLE_HIDDEN))
        self.assertIsNone(win._execute_menu_action(self.actions_mod.AppAction.FM_REFRESH))
        close_result = win._execute_menu_action(self.actions_mod.AppAction.FM_CLOSE)
        self.assertEqual(copy_result.type, self.actions_mod.ActionType.REQUEST_COPY_ENTRY)
        self.assertEqual(move_result.type, self.actions_mod.ActionType.REQUEST_MOVE_ENTRY)
        self.assertEqual(rename_result.type, self.actions_mod.ActionType.REQUEST_RENAME_ENTRY)
        self.assertEqual(delete_result.type, self.actions_mod.ActionType.REQUEST_DELETE_CONFIRM)
        self.assertEqual(new_dir_result.type, self.actions_mod.ActionType.REQUEST_NEW_DIR)
        self.assertEqual(new_file_result.type, self.actions_mod.ActionType.REQUEST_NEW_FILE)
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
        self.assertIsNone(win.handle_click(bx, by + 2))  # single-click selects only
        self.assertEqual(win.selected_index, 0)
        win.activate_selected.assert_not_called()
        self.assertEqual(
            win.handle_click(bx, by + 2, self.curses.BUTTON1_DOUBLE_CLICKED),
            "activated",
        )
        self.assertIsNone(win.handle_click(999, 999))

    def test_handle_click_menu_intercept_without_action_returns_none(self):
        win = self._make_window()
        win.window_menu.on_menu_bar = mock.Mock(return_value=True)
        win.window_menu.handle_click = mock.Mock(return_value=None)
        self.assertIsNone(win.handle_click(1, 1))

    def test_pending_drag_candidate_starts_only_after_mouse_move(self):
        win = self._make_window()
        file_entry = self.fm_mod.FileEntry("a.txt", False, "/tmp/a.txt", 1, use_unicode=False)
        dir_entry = self.fm_mod.FileEntry("docs", True, "/tmp/docs", use_unicode=False)
        win.entries = [file_entry, dir_entry]
        win.content = ["path", "sep", file_entry.display_text, dir_entry.display_text]
        bx, by, _, _ = win.body_rect()

        win.handle_click(bx, by + 2, self.curses.BUTTON1_PRESSED)
        self.assertIsNotNone(win._pending_drag_payload)
        self.assertEqual(win._pending_drag_payload["path"], "/tmp/a.txt")

        bstate_move = self.curses.BUTTON1_PRESSED | self.curses.REPORT_MOUSE_POSITION
        self.assertIsNone(win.consume_pending_drag(bx, by + 2, bstate_move))

        payload = win.consume_pending_drag(bx + 1, by + 2, bstate_move)
        self.assertEqual(payload["type"], "file_path")
        self.assertEqual(payload["path"], "/tmp/a.txt")
        self.assertIsNone(win._pending_drag_payload)
        self.assertIsNone(win._pending_drag_origin)

        win.handle_click(bx, by + 3, self.curses.BUTTON1_PRESSED)
        self.assertIsNone(win._pending_drag_payload)

        win.handle_click(999, 999, self.curses.BUTTON1_PRESSED)
        self.assertIsNone(win._pending_drag_payload)

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

    def test_handle_key_function_shortcuts_request_actions(self):
        win = self._make_window()
        win.window_menu.active = False
        win.entries = [self.fm_mod.FileEntry("demo.txt", False, "/tmp/demo.txt", 10)]
        win.selected_index = 0

        copy_result = win.handle_key(self.curses.KEY_F5)
        move_result = win.handle_key(self.curses.KEY_F4)
        rename_result = win.handle_key(self.curses.KEY_F2)
        delete_result = win.handle_key(self.curses.KEY_DC)
        new_dir_result = win.handle_key(self.curses.KEY_F7)
        new_file_result = win.handle_key(self.curses.KEY_F8)

        self.assertEqual(copy_result.type, self.actions_mod.ActionType.REQUEST_COPY_ENTRY)
        self.assertEqual(move_result.type, self.actions_mod.ActionType.REQUEST_MOVE_ENTRY)
        self.assertEqual(rename_result.type, self.actions_mod.ActionType.REQUEST_RENAME_ENTRY)
        self.assertEqual(delete_result.type, self.actions_mod.ActionType.REQUEST_DELETE_CONFIRM)
        self.assertEqual(new_dir_result.type, self.actions_mod.ActionType.REQUEST_NEW_DIR)
        self.assertEqual(new_file_result.type, self.actions_mod.ActionType.REQUEST_NEW_FILE)

    def test_rename_selected_success(self):
        root = _make_tmp_dir("rename_success")
        try:
            src = root / "a.txt"
            src.write_text("x", encoding="utf-8")
            win = self._make_window(start_path=str(root))
            for i, entry in enumerate(win.entries):
                if entry.name == "a.txt":
                    win.selected_index = i
                    break

            result = win.rename_selected("b.txt")

            self.assertIsNone(result)
            self.assertTrue((root / "b.txt").exists())
            self.assertFalse((root / "a.txt").exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_rename_selected_rejects_invalid_names(self):
        root = _make_tmp_dir("rename_invalid")
        try:
            src = root / "a.txt"
            src.write_text("x", encoding="utf-8")
            win = self._make_window(start_path=str(root))
            for i, entry in enumerate(win.entries):
                if entry.name == "a.txt":
                    win.selected_index = i
                    break

            empty = win.rename_selected("")
            slash = win.rename_selected("bad/name")

            self.assertEqual(empty.type, self.actions_mod.ActionType.ERROR)
            self.assertEqual(slash.type, self.actions_mod.ActionType.ERROR)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_delete_selected_file_success(self):
        root = _make_tmp_dir("delete_file")
        try:
            src = root / "a.txt"
            src.write_text("x", encoding="utf-8")
            trash_dir = root / ".trash"
            win = self._make_window(start_path=str(root))
            for i, entry in enumerate(win.entries):
                if entry.name == "a.txt":
                    win.selected_index = i
                    break

            with mock.patch.object(win, "_trash_base_dir", return_value=str(trash_dir)):
                result = win.delete_selected()

            self.assertIsNone(result)
            self.assertFalse(src.exists())
            self.assertTrue(trash_dir.exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_delete_selected_can_be_undone_from_trash(self):
        root = _make_tmp_dir("undo_delete")
        try:
            src = root / "a.txt"
            src.write_text("x", encoding="utf-8")
            trash_dir = root / ".trash"
            win = self._make_window(start_path=str(root))
            for i, entry in enumerate(win.entries):
                if entry.name == "a.txt":
                    win.selected_index = i
                    break

            with mock.patch.object(win, "_trash_base_dir", return_value=str(trash_dir)):
                delete_result = win.delete_selected()
                self.assertIsNone(delete_result)
                self.assertFalse(src.exists())
                self.assertIsNotNone(win._last_trash_move)
                trash_path = pathlib.Path(win._last_trash_move["trash"])
                self.assertTrue(trash_path.exists())

                undo_result = win.undo_last_delete()
                self.assertIsNone(undo_result)
                self.assertTrue(src.exists())
                self.assertFalse(trash_path.exists())

        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_create_directory_and_file_success(self):
        root = _make_tmp_dir("create_items")
        try:
            win = self._make_window(start_path=str(root))

            dir_result = win.create_directory("newdir")
            file_result = win.create_file("new.txt")

            self.assertIsNone(dir_result)
            self.assertIsNone(file_result)
            self.assertTrue((root / "newdir").is_dir())
            self.assertTrue((root / "new.txt").is_file())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_create_directory_and_file_reject_invalid_name(self):
        root = _make_tmp_dir("create_invalid")
        try:
            win = self._make_window(start_path=str(root))

            bad_dir = win.create_directory("bad/name")
            bad_file = win.create_file("")

            self.assertEqual(bad_dir.type, self.actions_mod.ActionType.ERROR)
            self.assertEqual(bad_file.type, self.actions_mod.ActionType.ERROR)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_copy_selected_file_success(self):
        root = _make_tmp_dir("copy_file")
        try:
            src = root / "a.txt"
            dest_dir = root / "dest"
            src.write_text("hello", encoding="utf-8")
            dest_dir.mkdir()

            win = self._make_window(start_path=str(root))
            for i, entry in enumerate(win.entries):
                if entry.name == "a.txt":
                    win.selected_index = i
                    break

            result = win.copy_selected(str(dest_dir))

            self.assertIsNone(result)
            self.assertTrue((dest_dir / "a.txt").is_file())
            self.assertEqual((dest_dir / "a.txt").read_text(encoding="utf-8"), "hello")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_move_selected_file_success(self):
        root = _make_tmp_dir("move_file")
        try:
            src = root / "a.txt"
            dest_dir = root / "dest"
            src.write_text("hello", encoding="utf-8")
            dest_dir.mkdir()

            win = self._make_window(start_path=str(root))
            for i, entry in enumerate(win.entries):
                if entry.name == "a.txt":
                    win.selected_index = i
                    break

            result = win.move_selected(str(dest_dir))

            self.assertIsNone(result)
            self.assertFalse(src.exists())
            self.assertTrue((dest_dir / "a.txt").is_file())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_move_selected_to_new_name_in_current_path(self):
        root = _make_tmp_dir("move_rename")
        try:
            src = root / "a.txt"
            src.write_text("hello", encoding="utf-8")
            win = self._make_window(start_path=str(root))
            for i, entry in enumerate(win.entries):
                if entry.name == "a.txt":
                    win.selected_index = i
                    break

            result = win.move_selected(str(root / "b.txt"))

            self.assertIsNone(result)
            self.assertFalse(src.exists())
            self.assertTrue((root / "b.txt").is_file())
            self.assertEqual(win.entries[win.selected_index].name, "b.txt")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_create_directory_and_file_reject_existing(self):
        root = _make_tmp_dir("create_existing")
        try:
            (root / "existing_dir").mkdir()
            (root / "existing.txt").write_text("x", encoding="utf-8")
            win = self._make_window(start_path=str(root))

            dup_dir = win.create_directory("existing_dir")
            dup_file = win.create_file("existing.txt")

            self.assertEqual(dup_dir.type, self.actions_mod.ActionType.ERROR)
            self.assertEqual(dup_file.type, self.actions_mod.ActionType.ERROR)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_create_directory_and_file_oserror_paths(self):
        root = _make_tmp_dir("create_oserror")
        try:
            win = self._make_window(start_path=str(root))
            with mock.patch.object(self.fm_mod.os, "mkdir", side_effect=OSError("mkdir denied")):
                dir_err = win.create_directory("x")
            with mock.patch("builtins.open", side_effect=OSError("open denied")):
                file_err = win.create_file("y.txt")
            self.assertEqual(dir_err.type, self.actions_mod.ActionType.ERROR)
            self.assertEqual(file_err.type, self.actions_mod.ActionType.ERROR)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_copy_selected_error_paths(self):
        root = _make_tmp_dir("copy_errors")
        try:
            src = root / "a.txt"
            src.write_text("hello", encoding="utf-8")
            win = self._make_window(start_path=str(root))

            no_sel = win.copy_selected(str(root / "dest"))
            self.assertEqual(no_sel.type, self.actions_mod.ActionType.ERROR)

            win.entries = [self.fm_mod.FileEntry("..", True, str(root.parent))]
            win.selected_index = 0
            parent_err = win.copy_selected(str(root / "dest"))
            self.assertEqual(parent_err.type, self.actions_mod.ActionType.ERROR)

            win = self._make_window(start_path=str(root))
            for i, entry in enumerate(win.entries):
                if entry.name == "a.txt":
                    win.selected_index = i
                    break

            empty_err = win.copy_selected("")
            missing_parent_err = win.copy_selected(str(root / "missing" / "x.txt"))
            same_err = win.copy_selected(str(src))
            exists_target = root / "exists.txt"
            exists_target.write_text("z", encoding="utf-8")
            exists_err = win.copy_selected(str(exists_target))

            self.assertEqual(empty_err.type, self.actions_mod.ActionType.ERROR)
            self.assertEqual(missing_parent_err.type, self.actions_mod.ActionType.ERROR)
            self.assertEqual(same_err.type, self.actions_mod.ActionType.ERROR)
            self.assertEqual(exists_err.type, self.actions_mod.ActionType.ERROR)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_copy_selected_directory_and_into_self_error(self):
        root = _make_tmp_dir("copy_dir")
        try:
            src_dir = root / "srcdir"
            src_dir.mkdir()
            (src_dir / "note.txt").write_text("x", encoding="utf-8")
            target_dir = root / "target"
            target_dir.mkdir()
            win = self._make_window(start_path=str(root))
            for i, entry in enumerate(win.entries):
                if entry.name == "srcdir":
                    win.selected_index = i
                    break

            copy_ok = win.copy_selected(str(target_dir))
            into_self = win.copy_selected(str(src_dir / "nested"))

            self.assertIsNone(copy_ok)
            self.assertTrue((target_dir / "srcdir").is_dir())
            self.assertEqual(into_self.type, self.actions_mod.ActionType.ERROR)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_copy_and_move_selected_oserror_paths(self):
        root = _make_tmp_dir("copy_move_oserror")
        try:
            src = root / "a.txt"
            src.write_text("hello", encoding="utf-8")
            win = self._make_window(start_path=str(root))
            for i, entry in enumerate(win.entries):
                if entry.name == "a.txt":
                    win.selected_index = i
                    break

            with mock.patch.object(self.fm_mod.shutil, "copy2", side_effect=OSError("copy denied")):
                copy_err = win.copy_selected(str(root / "b.txt"))
            with mock.patch.object(self.fm_mod.shutil, "move", side_effect=OSError("move denied")):
                move_err = win.move_selected(str(root / "c.txt"))

            self.assertEqual(copy_err.type, self.actions_mod.ActionType.ERROR)
            self.assertEqual(move_err.type, self.actions_mod.ActionType.ERROR)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_move_selected_error_paths_and_select_helper(self):
        root = _make_tmp_dir("move_errors")
        try:
            src = root / "a.txt"
            src.write_text("hello", encoding="utf-8")
            win = self._make_window(start_path=str(root))

            no_sel = win.move_selected(str(root / "b.txt"))
            self.assertEqual(no_sel.type, self.actions_mod.ActionType.ERROR)

            win.entries = [self.fm_mod.FileEntry("..", True, str(root.parent))]
            win.selected_index = 0
            parent_err = win.move_selected(str(root / "b.txt"))
            self.assertEqual(parent_err.type, self.actions_mod.ActionType.ERROR)

            self.assertFalse(win._select_entry_by_name("does-not-exist"))
        finally:
            shutil.rmtree(root, ignore_errors=True)

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

    def test_bookmark_navigation_and_assignment(self):
        root = _make_tmp_dir("bookmarks")
        try:
            subdir = root / "sub"
            subdir.mkdir()
            win = self._make_window(start_path=str(root))

            self.assertIsNone(win.set_bookmark(1, str(subdir)))
            self.assertEqual(win.bookmarks[1], str(subdir.resolve()))

            result_nav = win.navigate_bookmark(1)
            self.assertIsNone(result_nav)
            self.assertEqual(win.current_path, str(subdir.resolve()))

            invalid = win.set_bookmark(9, str(subdir))
            self.assertEqual(invalid.type, self.actions_mod.ActionType.ERROR)

        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_handle_key_bookmark_shortcuts(self):
        win = self._make_window()
        win.window_menu.active = False
        with (
            mock.patch.object(win, "navigate_bookmark", return_value=None) as navigate_bookmark,
            mock.patch.object(win, "set_bookmark", return_value=None) as set_bookmark,
        ):
            win.handle_key(ord("1"))
            win.handle_key(ord("!"))

        navigate_bookmark.assert_called_once_with(1)
        set_bookmark.assert_called_once_with(1)

    def test_draw_preview_pane_renders_preview_header_when_wide(self):
        root = _make_tmp_dir("preview_pane")
        try:
            target = root / "note.txt"
            target.write_text("line1\nline2\n", encoding="utf-8")
            win = self.fm_mod.FileManagerWindow(0, 0, 90, 14, start_path=str(root))
            for i, entry in enumerate(win.entries):
                if entry.name == "note.txt":
                    win.selected_index = i
                    break

            with (
                mock.patch.object(self.fm_mod.Window, "draw", return_value=None),
                mock.patch.object(self.fm_mod, "safe_addstr") as safe_addstr,
            ):
                win.draw(None)

            rendered = [call.args[3] for call in safe_addstr.call_args_list if len(call.args) >= 4]
            self.assertTrue(any("Preview" in str(text) for text in rendered))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_entry_preview_lines_uses_image_backend_for_image_extensions(self):
        win = self._make_window()
        entry = self.fm_mod.FileEntry("pic.png", False, "/tmp/pic.png", 10, use_unicode=False)
        with mock.patch.object(win, "_read_image_preview", return_value=["img"]) as read_image_preview:
            lines = win._entry_preview_lines(entry, 5, max_cols=20)
        self.assertEqual(lines, ["img"])
        read_image_preview.assert_called_once_with("/tmp/pic.png", max_lines=5, max_cols=20)

    def test_handle_tab_key_toggles_active_pane_only_in_dual_mode(self):
        win = self._make_window()
        win.dual_pane_enabled = False
        self.assertFalse(win.handle_tab_key())

        win.dual_pane_enabled = True
        win.active_pane = 0
        self.assertTrue(win.handle_tab_key())
        self.assertEqual(win.active_pane, 1)

    def test_toggle_dual_pane_requires_min_width(self):
        win = self._make_window()
        win.dual_pane_enabled = False
        win.w = 80

        result = win.toggle_dual_pane()

        self.assertEqual(result.type, self.actions_mod.ActionType.ERROR)
        self.assertFalse(win.dual_pane_enabled)

    def test_toggle_dual_pane_enables_and_disables_when_wide(self):
        win = self.fm_mod.FileManagerWindow(0, 0, 100, 14, start_path=".")
        win.dual_pane_enabled = False

        with mock.patch.object(win, "_rebuild_secondary_content") as rebuild_secondary:
            enabled = win.toggle_dual_pane()
        self.assertIsNone(enabled)
        self.assertTrue(win.dual_pane_enabled)
        rebuild_secondary.assert_called_once_with()

        disabled = win.toggle_dual_pane()
        self.assertIsNone(disabled)
        self.assertFalse(win.dual_pane_enabled)

    def test_handle_key_d_toggles_dual_pane(self):
        win = self.fm_mod.FileManagerWindow(0, 0, 100, 14, start_path=".")
        win.window_menu.active = False
        win.dual_pane_enabled = False

        with mock.patch.object(win, "toggle_dual_pane", return_value=None) as toggle_dual:
            result = win.handle_key(ord("d"))

        self.assertIsNone(result)
        toggle_dual.assert_called_once_with()

    def test_selected_entry_for_operation_uses_active_pane(self):
        win = self._make_window()
        left_entry = self.fm_mod.FileEntry("left.txt", False, "/tmp/left.txt", 1, use_unicode=False)
        right_entry = self.fm_mod.FileEntry("right.txt", False, "/tmp/right.txt", 1, use_unicode=False)
        win.entries = [left_entry]
        win.selected_index = 0
        win.secondary_entries = [right_entry]
        win.secondary_selected_index = 0

        win.dual_pane_enabled = False
        self.assertEqual(win.selected_entry_for_operation().name, "left.txt")

        win.dual_pane_enabled = True
        win.active_pane = 1
        self.assertEqual(win.selected_entry_for_operation().name, "right.txt")

    def test_handle_key_f5_in_dual_mode_uses_cross_pane_copy(self):
        win = self._make_window()
        win.dual_pane_enabled = True
        with mock.patch.object(win, "_dual_copy_move_between_panes", return_value=None) as cross_copy:
            result = win.handle_key(self.curses.KEY_F5)
        self.assertIsNone(result)
        cross_copy.assert_called_once_with(move=False)

    def test_handle_key_copy_shortcut_copies_selected_entry_path(self):
        win = self._make_window()
        win.window_menu.active = False
        win.entries = [self.fm_mod.FileEntry("demo.txt", False, "/tmp/demo.txt", 10)]
        win.selected_index = 0
        with mock.patch.object(self.fm_mod, "copy_text") as copy_text:
            win.handle_key(self.curses.KEY_F6)
        copy_text.assert_called_once_with("/tmp/demo.txt")

    def test_handle_key_copy_shortcut_noop_without_entries(self):
        win = self._make_window()
        win.window_menu.active = False
        win.entries = []
        with mock.patch.object(self.fm_mod, "copy_text") as copy_text:
            win.handle_key(self.curses.KEY_F6)
        copy_text.assert_not_called()

    def test_handle_key_ctrl_c_no_longer_triggers_copy(self):
        win = self._make_window()
        win.window_menu.active = False
        win.entries = [self.fm_mod.FileEntry("demo.txt", False, "/tmp/demo.txt", 10)]
        win.selected_index = 0
        with mock.patch.object(self.fm_mod, "copy_text") as copy_text:
            win.handle_key(3)
        copy_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()

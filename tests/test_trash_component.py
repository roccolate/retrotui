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
    root = pathlib.Path("tests") / f"_tmp_trash_component_{name}"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    return root


class TrashComponentTests(unittest.TestCase):
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
            "retrotui.apps.trash",
            "retrotui.core.actions",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.trash_mod = importlib.import_module("retrotui.apps.trash")
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
            "retrotui.apps.trash",
            "retrotui.core.actions",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_window(self, trash_root: pathlib.Path):
        with mock.patch.object(
            self.trash_mod.TrashWindow, "_trash_base_dir", return_value=str(trash_root)
        ):
            return self.trash_mod.TrashWindow(0, 0, 60, 18)

    def test_init_sets_trash_menu_and_hides_parent_entry_at_root(self):
        root = _make_tmp_dir("init")
        try:
            (root / "a.txt").write_text("x", encoding="utf-8")
            win = self._make_window(root)
            self.assertFalse(win.dual_pane_enabled)
            self.assertEqual(win.current_path, str(root.resolve()))
            self.assertTrue(win.title.startswith("Trash - root"))
            self.assertTrue(all(entry.name != ".." for entry in win.entries))
            file_labels = [label for label, _ in win.window_menu.items["File"]]
            self.assertIn("Empty Trash    E", file_labels)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_navigate_to_stays_within_trash_subtree(self):
        root = _make_tmp_dir("navigate")
        try:
            sub = root / "subdir"
            sub.mkdir()
            win = self._make_window(root)

            win.navigate_to(str(sub))
            self.assertEqual(win.current_path, str(sub.resolve()))

            outside = root.parent
            win.navigate_to(str(outside))
            self.assertEqual(win.current_path, str(sub.resolve()))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_delete_selected_deletes_permanently_and_handles_errors(self):
        root = _make_tmp_dir("delete")
        try:
            target = root / "gone.txt"
            target.write_text("bye", encoding="utf-8")
            (root / "keep.txt").write_text("stay", encoding="utf-8")
            win = self._make_window(root)
            for idx, entry in enumerate(win.entries):
                if entry.name == "gone.txt":
                    win.selected_index = idx
                    break

            with mock.patch.object(win, "_ensure_visible") as ensure_visible:
                self.assertIsNone(win.delete_selected())
                ensure_visible.assert_called_once_with()
            self.assertFalse(target.exists())

            win.entries = []
            err = win.delete_selected()
            self.assertEqual(err.type, self.actions_mod.ActionType.ERROR)

            win.entries = [self.fm_mod.FileEntry("..", True, str(root.parent))]
            win.selected_index = 0
            parent_err = win.delete_selected()
            self.assertEqual(parent_err.type, self.actions_mod.ActionType.ERROR)

            win.entries = [self.fm_mod.FileEntry("x.txt", False, str(root / "x.txt"), 1)]
            win.selected_index = 0
            with mock.patch.object(win, "_delete_path", side_effect=OSError("nope")):
                os_err = win.delete_selected()
            self.assertEqual(os_err.type, self.actions_mod.ActionType.ERROR)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_delete_path_handles_file_and_directory(self):
        root = _make_tmp_dir("delete_path")
        try:
            file_path = root / "a.txt"
            file_path.write_text("x", encoding="utf-8")
            dir_path = root / "dir"
            dir_path.mkdir()
            (dir_path / "b.txt").write_text("x", encoding="utf-8")

            self.trash_mod.TrashWindow._delete_path(str(file_path))
            self.trash_mod.TrashWindow._delete_path(str(dir_path))

            self.assertFalse(file_path.exists())
            self.assertFalse(dir_path.exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_empty_trash_success_and_error_paths(self):
        root = _make_tmp_dir("empty")
        try:
            (root / "a.txt").write_text("x", encoding="utf-8")
            (root / "dir").mkdir()
            (root / "dir" / "b.txt").write_text("x", encoding="utf-8")
            win = self._make_window(root)

            self.assertIsNone(win.empty_trash())
            self.assertEqual(list(root.iterdir()), [])
            self.assertEqual(win.current_path, str(root.resolve()))

            with mock.patch.object(self.trash_mod.os, "listdir", side_effect=OSError("list fail")):
                err = win.empty_trash()
            self.assertEqual(err.type, self.actions_mod.ActionType.ERROR)

            (root / "x.txt").write_text("x", encoding="utf-8")
            with mock.patch.object(win, "_delete_path", side_effect=OSError("del fail")):
                err = win.empty_trash()
            self.assertEqual(err.type, self.actions_mod.ActionType.ERROR)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_execute_action_and_key_shortcuts(self):
        root = _make_tmp_dir("actions")
        try:
            win = self._make_window(root)

            with mock.patch.object(win, "empty_trash", return_value="emptied"):
                self.assertEqual(win.execute_action("trash_empty"), "emptied")

            close = win.execute_action("trash_close")
            self.assertEqual(close.type, self.actions_mod.ActionType.EXECUTE)
            self.assertEqual(close.payload, self.actions_mod.AppAction.CLOSE_WINDOW)

            with mock.patch.object(
                self.fm_mod.FileManagerWindow, "execute_action", return_value="super-result"
            ):
                self.assertEqual(win.execute_action("unknown"), "super-result")

            with mock.patch.object(win, "empty_trash", return_value="from-key"):
                self.assertEqual(win.handle_key(ord("E")), "from-key")

            with mock.patch.object(win, "_rebuild_content") as rebuild:
                self.assertIsNone(win.handle_key(ord("R")))
                self.assertIsNone(win.handle_key(self.curses.KEY_F5))
            self.assertEqual(rebuild.call_count, 2)

            with mock.patch.object(
                self.fm_mod.FileManagerWindow, "handle_key", return_value="fallback"
            ) as super_handle:
                self.assertEqual(win.handle_key(ord("z")), "fallback")
            super_handle.assert_called_once()
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_undo_last_delete_is_not_supported(self):
        root = _make_tmp_dir("undo")
        try:
            win = self._make_window(root)
            result = win.undo_last_delete()
            self.assertEqual(result.type, self.actions_mod.ActionType.ERROR)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

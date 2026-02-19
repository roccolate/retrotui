import importlib
import pathlib
import sys
import types
import unittest
from unittest import mock

# --- Fake curses setup ---
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

class FileManagerComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        # Clean up affected modules to ensure clean import
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.clipboard",
            "retrotui.apps.filemanager",
            "retrotui.apps.filemanager.window",
            "retrotui.core.actions",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.fm_mod = importlib.import_module("retrotui.apps.filemanager")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        # Restore sys.modules
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.clipboard",
            "retrotui.apps.filemanager",
            "retrotui.apps.filemanager.window",
            "retrotui.core.actions",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_window(self, start_path="."):
        # Mock os.path.realpath/expanduser to avoid side effects during init
        with mock.patch("os.path.realpath", return_value="/tmp"), \
             mock.patch("os.path.expanduser", return_value="/tmp"), \
             mock.patch("os.path.exists", return_value=True), \
             mock.patch("retrotui.apps.filemanager.window.FileManagerWindow._rebuild_content"):
            return self.fm_mod.FileManagerWindow(0, 0, 50, 14, start_path=start_path)

    def test_rename_selected_success(self):
        win = self._make_window()
        win.entries = [self.fm_mod.FileEntry("a.txt", False, "/tmp/a.txt")]
        win.selected_index = 0
        
        with mock.patch("retrotui.apps.filemanager.window.perform_move") as mock_move:
            result = win.rename_selected("b.txt")
            
        # Expect platform-specific separator
        expected_dest = str(pathlib.Path("/tmp/b.txt"))
        # But wait, the app uses os.path.join(dirname, new_name).
        # dirname("/tmp/a.txt") might be "/tmp" (posix) or "\tmp" (win mixed).
        # Let's just create the expected string using os.path.join
        import os
        expected_dest = os.path.join(os.path.dirname("/tmp/a.txt"), "b.txt")
        mock_move.assert_called_once_with("/tmp/a.txt", expected_dest)

    def test_delete_selected_file_success(self):
        win = self._make_window()
        win.entries = [self.fm_mod.FileEntry("a.txt", False, "/tmp/a.txt")]
        win.selected_index = 0

        with mock.patch("retrotui.apps.filemanager.window.perform_delete", return_value="/trash/a.txt") as mock_delete:
            result = win.delete_selected()

        mock_delete.assert_called_once_with("/tmp/a.txt")
        self.assertEqual(result.type, self.actions_mod.ActionType.REFRESH)
        self.assertEqual(win._last_trash_move, {'source': '/tmp/a.txt', 'trash': '/trash/a.txt'})

    def test_delete_selected_can_be_undone(self):
        win = self._make_window()
        win._last_trash_move = {'source': '/tmp/a.txt', 'trash': '/trash/a.txt'}

        with mock.patch("retrotui.apps.filemanager.window.perform_undo", return_value=None) as mock_undo:
            result = win.undo_delete()
        
        mock_undo.assert_called_once_with({'source': '/tmp/a.txt', 'trash': '/trash/a.txt'})
        self.assertEqual(result.type, self.actions_mod.ActionType.REFRESH)
        self.assertIsNone(win._last_trash_move)

    def test_create_directory_success(self):
        win = self._make_window()
        win.current_path = "/tmp"
        
        with mock.patch("retrotui.apps.filemanager.window.create_directory", 
                        return_value=self.actions_mod.ActionResult(self.actions_mod.ActionType.REFRESH)) as mock_mkdir:
            result = win.create_directory("newdir")
            
        mock_mkdir.assert_called_once_with("/tmp", "newdir")
        self.assertEqual(result.type, self.actions_mod.ActionType.REFRESH)

    def test_create_file_success(self):
        win = self._make_window()
        win.current_path = "/tmp"

        with mock.patch("retrotui.apps.filemanager.window.create_file",
                        return_value=self.actions_mod.ActionResult(self.actions_mod.ActionType.REFRESH)) as mock_mkfile:
            result = win.create_file("new.txt")

        mock_mkfile.assert_called_once_with("/tmp", "new.txt")
        self.assertEqual(result.type, self.actions_mod.ActionType.REFRESH)

    def test_copy_selected_file_success(self):
        win = self._make_window()
        win.entries = [self.fm_mod.FileEntry("a.txt", False, "/tmp/a.txt")]
        win.selected_index = 0

        with mock.patch("retrotui.apps.filemanager.window.perform_copy",
                        return_value=self.actions_mod.ActionResult(self.actions_mod.ActionType.REFRESH)) as mock_copy:
            result = win.copy_selected("/dest")

        mock_copy.assert_called_once_with("/tmp/a.txt", "/dest")
        self.assertEqual(result.type, self.actions_mod.ActionType.REFRESH)

    def test_move_selected_file_success(self):
        win = self._make_window()
        win.entries = [self.fm_mod.FileEntry("a.txt", False, "/tmp/a.txt")]
        win.selected_index = 0

        with mock.patch("retrotui.apps.filemanager.window.perform_move",
                        return_value=self.actions_mod.ActionResult(self.actions_mod.ActionType.REFRESH)) as mock_move:
            result = win.move_selected("/dest")

        mock_move.assert_called_once_with("/tmp/a.txt", "/dest")
        self.assertEqual(result.type, self.actions_mod.ActionType.REFRESH)

    def test_dual_copy_move_copy(self):
        win = self._make_window()
        win.dual_pane_enabled = True
        win.active_pane = 0
        win.current_path = "/left"
        win.secondary_path = "/right"
        win.entries = [self.fm_mod.FileEntry("a.txt", False, "/left/a.txt", size=100)]
        win.selected_index = 0
        
        with mock.patch("retrotui.apps.filemanager.window.perform_copy") as mock_copy, \
             mock.patch("retrotui.apps.filemanager.window.os.path.exists", return_value=False):
            result = win._dual_copy_move_between_panes(move=False)
            
        import os
        expected_dest = os.path.join("/right", "a.txt")
        mock_copy.assert_called_with("/left/a.txt", expected_dest)
        self.assertEqual(result.type, self.actions_mod.ActionType.REFRESH)

    def test_dual_copy_move_move(self):
        win = self._make_window()
        win.dual_pane_enabled = True
        win.active_pane = 0
        win.current_path = "/left"
        win.secondary_path = "/right"
        win.entries = [self.fm_mod.FileEntry("a.txt", False, "/left/a.txt", size=100)]
        win.selected_index = 0

        with mock.patch("retrotui.apps.filemanager.window.perform_move") as mock_move, \
             mock.patch("retrotui.apps.filemanager.window.os.path.exists", return_value=False):
            result = win._dual_copy_move_between_panes(move=True)

        import os
        expected_dest = os.path.join("/right", "a.txt")
        mock_move.assert_called_with("/left/a.txt", expected_dest)
        self.assertEqual(result.type, self.actions_mod.ActionType.REFRESH)

    def test_handle_click_sets_active_pane(self):
        win = self._make_window()
        win.dual_pane_enabled = True
        win.active_pane = 1
        
        # Mock body_rect to return 0,0,100,20
        with mock.patch.object(win, "body_rect", return_value=(0, 0, 100, 20)):
             # Click on left pane (x=10)
             result = win.handle_click(10, 5, 0)
        
        self.assertEqual(win.active_pane, 0)
        self.assertEqual(result.type, self.actions_mod.ActionType.REFRESH)

    def test_bookmarks(self):
        win = self._make_window()
        # Test read
        win.bookmarks = {1: '/mark'}
        
        with mock.patch("retrotui.apps.filemanager.window.navigate_bookmark", return_value="/mark") as mock_nav:
            win.navigate_bookmark(1)
            # Should call navigate_to if string returned
            # unittest mock ensures we called it, win.navigate_to calls os.path which is mocked/safe

        # Test set
        with mock.patch("retrotui.apps.filemanager.window.set_bookmark") as mock_set:
            win.set_bookmark(1, "/new")
            
        mock_set.assert_called_with(win.bookmarks, 1, "/new")

if __name__ == "__main__":
    unittest.main()

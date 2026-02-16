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
    fake.KEY_MOUSE = 409
    fake.KEY_RESIZE = 410
    fake.KEY_F10 = 266
    fake.ALL_MOUSE_EVENTS = 0xFFFFFFFF
    fake.REPORT_MOUSE_POSITION = 0x200000
    fake.BUTTON1_CLICKED = 0x0004
    fake.BUTTON1_PRESSED = 0x0002
    fake.BUTTON1_DOUBLE_CLICKED = 0x0008
    fake.BUTTON1_RELEASED = 0x0001
    fake.BUTTON4_PRESSED = 0x100000
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.A_DIM = 4
    fake.COLOR_WHITE = 7
    fake.COLOR_BLUE = 4
    fake.COLOR_BLACK = 0
    fake.COLOR_CYAN = 6
    fake.COLOR_YELLOW = 3
    fake.COLORS = 256
    fake.error = Exception
    fake.color_pair = lambda _: 0
    fake.can_change_color = lambda: False
    fake.start_color = lambda: None
    fake.use_default_colors = lambda: None
    fake.init_color = lambda *_: None
    fake.init_pair = lambda *_: None
    fake.curs_set = lambda *_: None
    fake.noecho = lambda: None
    fake.cbreak = lambda: None
    fake.mousemask = lambda *_: None
    fake.update_lines_cols = lambda: None
    fake.doupdate = lambda: None
    fake.getmouse = lambda: (0, 0, 0, 0, 0)
    return fake


class CoreAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        cls._prev_termios = sys.modules.get("termios")
        sys.modules["curses"] = _install_fake_curses()

        fake_termios = types.ModuleType("termios")
        fake_termios.error = OSError
        fake_termios.IXON = 0x0200
        fake_termios.IXOFF = 0x0400
        fake_termios.TCSANOW = 0
        fake_termios.tcgetattr = lambda *_: [0, 0, 0, 0, 0, 0, 0]
        fake_termios.tcsetattr = lambda *_: None
        sys.modules["termios"] = fake_termios

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
            "retrotui.ui.window",
            "retrotui.apps.notepad",
            "retrotui.apps.filemanager",
            "retrotui.core.actions",
            "retrotui.core.app",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.app_mod = importlib.import_module("retrotui.core.app")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
            "retrotui.ui.window",
            "retrotui.apps.notepad",
            "retrotui.apps.filemanager",
            "retrotui.core.actions",
            "retrotui.core.app",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

        if cls._prev_termios is not None:
            sys.modules["termios"] = cls._prev_termios
        else:
            sys.modules.pop("termios", None)

    def _make_app(self):
        app = self.app_mod.RetroTUI.__new__(self.app_mod.RetroTUI)
        app.running = True
        app.dialog = None
        app.windows = []
        app.menu = types.SimpleNamespace(
            active=False,
            selected_menu=3,
            selected_item=3,
            handle_key=mock.Mock(return_value=None),
        )
        return app

    def test_normalize_action_maps_legacy_string(self):
        app = self._make_app()

        self.assertEqual(
            app._normalize_action("filemanager"),
            self.actions_mod.AppAction.FILE_MANAGER,
        )
        self.assertEqual(app._normalize_action("unknown_action"), "unknown_action")

    def test_dispatch_open_file_calls_file_viewer(self):
        app = self._make_app()
        app.open_file_viewer = mock.Mock()
        result = self.actions_mod.ActionResult(
            self.actions_mod.ActionType.OPEN_FILE, "/tmp/demo.txt"
        )

        app._dispatch_window_result(result, source_win=None)

        app.open_file_viewer.assert_called_once_with("/tmp/demo.txt")

    def test_dispatch_execute_close_window_prefers_close(self):
        app = self._make_app()
        source = object()
        app.close_window = mock.Mock()
        app.execute_action = mock.Mock()
        result = self.actions_mod.ActionResult(
            self.actions_mod.ActionType.EXECUTE, self.actions_mod.AppAction.CLOSE_WINDOW
        )

        app._dispatch_window_result(result, source)

        app.close_window.assert_called_once_with(source)
        app.execute_action.assert_not_called()

    def test_dispatch_request_save_as_calls_dialog_builder(self):
        app = self._make_app()
        source = object()
        app.show_save_as_dialog = mock.Mock()
        result = self.actions_mod.ActionResult(self.actions_mod.ActionType.REQUEST_SAVE_AS)

        app._dispatch_window_result(result, source)

        app.show_save_as_dialog.assert_called_once_with(source)

    def test_dispatch_save_error_creates_dialog(self):
        app = self._make_app()
        result = self.actions_mod.ActionResult(
            self.actions_mod.ActionType.SAVE_ERROR, "disk full"
        )

        app._dispatch_window_result(result, source_win=None)

        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "Save Error")
        self.assertIn("disk full", app.dialog.message)

    def test_handle_global_menu_key_executes_selected_action(self):
        app = self._make_app()
        app.menu.active = True
        app.menu.handle_key = mock.Mock(return_value=self.actions_mod.AppAction.ABOUT)
        app.execute_action = mock.Mock()

        handled = app._handle_global_menu_key(10)

        self.assertTrue(handled)
        app.menu.handle_key.assert_called_once_with(10)
        app.execute_action.assert_called_once_with(self.actions_mod.AppAction.ABOUT)

    def test_handle_menu_hotkeys_f10_toggles_global_menu(self):
        app = self._make_app()
        app.menu.active = False

        handled = app._handle_menu_hotkeys(self.curses.KEY_F10)

        self.assertTrue(handled)
        self.assertTrue(app.menu.active)
        self.assertEqual(app.menu.selected_menu, 0)
        self.assertEqual(app.menu.selected_item, 0)

    def test_handle_menu_hotkeys_escape_closes_window_menu_first(self):
        app = self._make_app()
        window_menu = types.SimpleNamespace(active=True, selected_menu=2, selected_item=4)
        active_win = types.SimpleNamespace(window_menu=window_menu)
        app.get_active_window = mock.Mock(return_value=active_win)
        app.menu.active = True

        handled = app._handle_menu_hotkeys(27)

        self.assertTrue(handled)
        self.assertFalse(window_menu.active)
        self.assertTrue(app.menu.active)

    def test_resolve_dialog_result_exit_yes_stops_app(self):
        app = self._make_app()
        app.dialog = types.SimpleNamespace(title="Exit RetroTUI", buttons=["Yes", "No"])
        app.running = True

        app._resolve_dialog_result(0)

        self.assertFalse(app.running)
        self.assertIsNone(app.dialog)

    def test_resolve_dialog_result_dispatches_input_callback_result(self):
        app = self._make_app()
        dialog = self.app_mod.InputDialog("Save As", "Enter filename:")
        dialog.value = "note.txt"
        callback_result = self.actions_mod.ActionResult(
            self.actions_mod.ActionType.REQUEST_SAVE_AS
        )
        dialog.callback = mock.Mock(return_value=callback_result)
        app.dialog = dialog
        app._dispatch_window_result = mock.Mock()
        app.get_active_window = mock.Mock(return_value="active-window")

        app._resolve_dialog_result(0)

        dialog.callback.assert_called_once_with("note.txt")
        app._dispatch_window_result.assert_called_once_with(
            callback_result, "active-window"
        )


if __name__ == "__main__":
    unittest.main()

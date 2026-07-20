import importlib
import sys
import types
import unittest
from unittest import mock


class CloseLifecycleContractTests(unittest.TestCase):
    def test_window_manager_defers_close_and_dispatches_request(self):
        from retrotui.core.window_manager import WindowManager

        request = types.SimpleNamespace(type="confirm", payload={})
        app = types.SimpleNamespace(_dispatch_window_result=mock.Mock())
        manager = WindowManager(app)
        win = types.SimpleNamespace(
            id="dirty",
            title="Dirty",
            active=True,
            visible=True,
            always_on_top=False,
            request_close=mock.Mock(return_value=request),
            close=mock.Mock(),
        )
        manager.windows = [win]
        manager._active_window = win

        closed = manager.close_window(win)

        self.assertFalse(closed)
        self.assertIn(win, manager.windows)
        win.close.assert_not_called()
        app._dispatch_window_result.assert_called_once_with(request, win)

    def test_window_manager_force_close_bypasses_request(self):
        from retrotui.core.window_manager import WindowManager

        app = types.SimpleNamespace()
        manager = WindowManager(app)
        win = types.SimpleNamespace(
            id="dirty",
            title="Dirty",
            active=True,
            visible=True,
            always_on_top=False,
            request_close=mock.Mock(return_value=False),
            close=mock.Mock(),
        )
        manager.windows = [win]
        manager._active_window = win

        closed = manager.close_window(win, force=True)

        self.assertTrue(closed)
        self.assertNotIn(win, manager.windows)
        win.request_close.assert_not_called()
        win.close.assert_called_once_with()

    def test_notepad_close_confirmation_is_transactional(self):
        previous_curses = sys.modules.get("curses")
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
        fake.A_BOLD = 1
        fake.A_REVERSE = 2
        fake.error = Exception
        fake.color_pair = lambda value: value * 10

        module_names = (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.clipboard",
            "retrotui.apps.notepad",
            "retrotui.core.actions",
        )
        try:
            sys.modules["curses"] = fake
            for name in module_names:
                sys.modules.pop(name, None)

            actions = importlib.import_module("retrotui.core.actions")
            notepad = importlib.import_module("retrotui.apps.notepad")
            win = notepad.NotepadWindow(0, 0, 32, 12)

            self.assertIsNone(win._open_path_confirm_pending)
            win.modified = True
            request = win.request_close()

            self.assertEqual(request.type, actions.ActionType.REQUEST_SAVE_CONFIRM)
            self.assertFalse(win._force_close)
            self.assertFalse(win.request_close())

            request.payload["on_cancel"]()
            self.assertFalse(win._close_confirm_pending)

            request = win.request_close()
            result = request.payload["on_discard"]()
            self.assertEqual(result.type, actions.ActionType.EXECUTE)
            self.assertEqual(result.payload, actions.AppAction.CLOSE_WINDOW)
            self.assertTrue(win._force_close)
            self.assertTrue(win.request_close())

            win._open_path_confirm_pending = "/tmp/example.txt"
            win._cancel_open_path()
            self.assertIsNone(win._open_path_confirm_pending)
        finally:
            for name in module_names:
                sys.modules.pop(name, None)
            if previous_curses is None:
                sys.modules.pop("curses", None)
            else:
                sys.modules["curses"] = previous_curses


if __name__ == "__main__":
    unittest.main()

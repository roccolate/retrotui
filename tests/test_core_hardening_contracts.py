import types
import unittest
from unittest import mock

from retrotui.apps.terminal import TerminalWindow
from retrotui.core import key_router
from retrotui.core.window_manager import WindowManager


class CoreHardeningContractTests(unittest.TestCase):
    def test_cleanup_false_keeps_window_registered(self):
        app = types.SimpleNamespace(event_bus=None, _active_window_menu_owner=None)
        manager = WindowManager(app)
        window = types.SimpleNamespace(
            id="terminal",
            title="Terminal",
            active=True,
            visible=True,
            always_on_top=False,
            close=mock.Mock(return_value=False),
        )
        manager.windows = [window]
        manager._active_window = window

        self.assertFalse(manager.close_window(window))
        self.assertEqual(manager.windows, [window])
        self.assertIs(manager.get_active_window(), window)

    def test_hidden_active_window_yields_focus_to_visible_window(self):
        app = types.SimpleNamespace(event_bus=None)
        manager = WindowManager(app)
        visible = types.SimpleNamespace(active=False, visible=True)
        hidden = types.SimpleNamespace(active=True, visible=False)
        manager.windows = [visible, hidden]
        manager._active_window = hidden

        self.assertIs(manager.get_active_window(), visible)
        self.assertFalse(hidden.active)
        self.assertTrue(visible.active)

    def test_terminal_close_failure_preserves_session(self):
        terminal = TerminalWindow.__new__(TerminalWindow)
        session = types.SimpleNamespace(close=mock.Mock(return_value=False))
        terminal._session = session
        terminal._session_error = None
        terminal._reported_session_error = False
        terminal._pending_output = "pending"
        terminal._last_pty_size = (80, 24)

        self.assertFalse(terminal.close())
        self.assertIs(terminal._session, session)
        self.assertEqual(terminal._pending_output, "pending")
        self.assertIn("still alive", terminal._session_error)

    def test_terminal_close_success_releases_session(self):
        terminal = TerminalWindow.__new__(TerminalWindow)
        session = types.SimpleNamespace(close=mock.Mock(return_value=True))
        terminal._session = session
        terminal._session_error = None
        terminal._reported_session_error = False
        terminal._pending_output = "pending"
        terminal._last_pty_size = (80, 24)

        self.assertTrue(terminal.close())
        self.assertIsNone(terminal._session)
        self.assertEqual(terminal._pending_output, "")
        self.assertIsNone(terminal._last_pty_size)

    def test_focus_reorder_failure_is_logged_without_secondary_name_error(self):
        current = types.SimpleNamespace(active=True, visible=True, always_on_top=False)
        target = types.SimpleNamespace(active=False, visible=True, always_on_top=False)
        app = types.SimpleNamespace(
            windows=[current, target],
            window_mgr=types.SimpleNamespace(
                set_active_window=mock.Mock(side_effect=ValueError("bad z-order"))
            ),
        )

        key_router.cycle_focus(app)

        self.assertTrue(target.active)
        app.window_mgr.set_active_window.assert_called_once_with(target)


if __name__ == "__main__":
    unittest.main()

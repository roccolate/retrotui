import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_MOUSE = 409
    fake.KEY_RESIZE = 410
    fake.error = RuntimeError
    fake.doupdate = mock.Mock()
    fake.update_lines_cols = mock.Mock()
    fake.getmouse = mock.Mock(return_value=(0, 0, 0, 0, 0))
    return fake


class TerminalBackgroundTickContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._previous_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()
        sys.modules.pop("retrotui.core.event_loop", None)
        cls.event_loop = importlib.import_module("retrotui.core.event_loop")

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("retrotui.core.event_loop", None)
        if cls._previous_curses is None:
            sys.modules.pop("curses", None)
        else:
            sys.modules["curses"] = cls._previous_curses

    def test_hidden_service_window_ticks_without_visual_redraw(self):
        session = types.SimpleNamespace(running=True)
        window = types.SimpleNamespace(
            visible=False,
            tick_when_hidden=True,
            tick=mock.Mock(return_value=True),
            _session=session,
            _animated=False,
        )
        app = types.SimpleNamespace(windows=[window])

        changed, has_live, has_animated = self.event_loop._tick_and_probe_windows(app)

        window.tick.assert_called_once_with()
        self.assertFalse(changed)
        self.assertTrue(has_live)
        self.assertFalse(has_animated)

    def test_hidden_regular_window_remains_suspended(self):
        window = types.SimpleNamespace(
            visible=False,
            tick_when_hidden=False,
            tick=mock.Mock(return_value=True),
            _session=types.SimpleNamespace(running=True),
            _animated=True,
        )
        app = types.SimpleNamespace(windows=[window])

        changed, has_live, has_animated = self.event_loop._tick_and_probe_windows(app)

        window.tick.assert_not_called()
        self.assertFalse(changed)
        self.assertFalse(has_live)
        self.assertFalse(has_animated)


if __name__ == "__main__":
    unittest.main()

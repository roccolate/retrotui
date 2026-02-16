import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.ALL_MOUSE_EVENTS = 0xFFFFFFFF
    fake.REPORT_MOUSE_POSITION = 0x200000
    fake.BUTTON1_CLICKED = 0x0004
    fake.BUTTON1_PRESSED = 0x0002
    fake.BUTTON1_DOUBLE_CLICKED = 0x0008
    fake.BUTTON1_RELEASED = 0x0001
    fake.BUTTON5_PRESSED = 0x200000
    fake.curs_set = mock.Mock()
    fake.noecho = mock.Mock()
    fake.cbreak = mock.Mock()
    fake.mousemask = mock.Mock()
    return fake


def _install_fake_termios():
    fake = types.ModuleType("termios")
    fake.error = OSError
    fake.IXON = 0x0200
    fake.IXOFF = 0x0400
    fake.TCSANOW = 0
    fake.tcgetattr = mock.Mock(return_value=[fake.IXON | fake.IXOFF, 0, 0, 0, 0, 0, 0])
    fake.tcsetattr = mock.Mock()
    return fake


class BootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        cls._prev_termios = sys.modules.get("termios")
        cls.fake_curses = _install_fake_curses()
        cls.fake_termios = _install_fake_termios()
        sys.modules["curses"] = cls.fake_curses
        sys.modules["termios"] = cls.fake_termios
        sys.modules.pop("retrotui.core.bootstrap", None)
        cls.bootstrap = importlib.import_module("retrotui.core.bootstrap")

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("retrotui.core.bootstrap", None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)
        if cls._prev_termios is not None:
            sys.modules["termios"] = cls._prev_termios
        else:
            sys.modules.pop("termios", None)

    def test_configure_terminal_applies_curses_setup(self):
        stdscr = types.SimpleNamespace(
            keypad=mock.Mock(),
            nodelay=mock.Mock(),
            timeout=mock.Mock(),
        )

        self.bootstrap.configure_terminal(stdscr, timeout_ms=777)

        self.fake_curses.curs_set.assert_called_once_with(0)
        self.fake_curses.noecho.assert_called_once_with()
        self.fake_curses.cbreak.assert_called_once_with()
        stdscr.keypad.assert_called_once_with(True)
        stdscr.nodelay.assert_called_once_with(False)
        stdscr.timeout.assert_called_once_with(777)

    def test_disable_flow_control_updates_termios_flags(self):
        self.fake_termios.tcgetattr.reset_mock()
        self.fake_termios.tcsetattr.reset_mock()
        stream = types.SimpleNamespace(fileno=mock.Mock(return_value=9))

        self.bootstrap.disable_flow_control(stream)

        self.fake_termios.tcgetattr.assert_called_once_with(9)
        self.fake_termios.tcsetattr.assert_called_once()
        _, _, attrs = self.fake_termios.tcsetattr.call_args.args
        self.assertEqual(attrs[0] & self.fake_termios.IXON, 0)
        self.assertEqual(attrs[0] & self.fake_termios.IXOFF, 0)

    def test_disable_flow_control_ignores_termios_failures(self):
        self.fake_termios.tcgetattr.reset_mock()
        self.fake_termios.tcsetattr.reset_mock()
        stream = types.SimpleNamespace(fileno=mock.Mock(return_value=9))
        before_calls = self.fake_termios.tcsetattr.call_count
        self.fake_termios.tcgetattr.side_effect = OSError("termios unavailable")
        try:
            self.bootstrap.disable_flow_control(stream)
        finally:
            self.fake_termios.tcgetattr.side_effect = None

        self.assertEqual(self.fake_termios.tcsetattr.call_count, before_calls)

    def test_enable_mouse_support_returns_masks(self):
        with mock.patch("builtins.print") as print_mock:
            click_flags, stop_drag_flags, scroll_down_mask = self.bootstrap.enable_mouse_support()

        self.fake_curses.mousemask.assert_called_once_with(
            self.fake_curses.ALL_MOUSE_EVENTS | self.fake_curses.REPORT_MOUSE_POSITION
        )
        self.assertEqual(
            click_flags,
            self.fake_curses.BUTTON1_CLICKED
            | self.fake_curses.BUTTON1_PRESSED
            | self.fake_curses.BUTTON1_DOUBLE_CLICKED,
        )
        self.assertEqual(
            stop_drag_flags,
            self.fake_curses.BUTTON1_RELEASED
            | self.fake_curses.BUTTON1_CLICKED
            | self.fake_curses.BUTTON1_DOUBLE_CLICKED,
        )
        self.assertEqual(scroll_down_mask, self.fake_curses.BUTTON5_PRESSED)
        self.assertEqual(print_mock.call_count, 2)

    def test_disable_mouse_support_prints_restore_sequences(self):
        with mock.patch("builtins.print") as print_mock:
            self.bootstrap.disable_mouse_support()

        self.assertEqual(print_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()

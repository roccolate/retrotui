"""Tests for v0.9.5 mouse pass-through and GPM compat.

These cover the contract added in v0.9.5:

* When the child program enables DEC private mouse modes (``?1000h`` /
  ``?1002h`` / ``?1003h`` / ``?1005h`` / ``?1006h`` / ``?1015h``), the
  terminal forwards clicks, drags, scroll wheel and motion events as
  SGR mouse escape sequences to the PTY.
* When the child has not enabled mouse reporting, RetroTUI keeps using
  the mouse for selection/scrollback (the GPM-compat path).
"""

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.A_DIM = 4
    fake.A_UNDERLINE = 8
    fake.color_pair = lambda value: int(value) * 10
    fake.has_colors = lambda: False
    fake.init_pair = lambda *_args, **_kwargs: None
    fake.error = Exception
    fake.BUTTON1_PRESSED = 0x2
    fake.BUTTON1_RELEASED = 0x4
    fake.BUTTON1_CLICKED = 0x8
    fake.BUTTON1_DOUBLE_CLICKED = 0x10
    fake.BUTTON2_PRESSED = 0x40
    fake.BUTTON2_RELEASED = 0x80
    fake.BUTTON2_CLICKED = 0x100
    fake.BUTTON2_DOUBLE_CLICKED = 0x200
    fake.BUTTON3_PRESSED = 0x400
    fake.BUTTON3_RELEASED = 0x800
    fake.BUTTON3_CLICKED = 0x1000
    fake.BUTTON3_DOUBLE_CLICKED = 0x2000
    fake.BUTTON4_PRESSED = 0x20000
    fake.BUTTON4_CLICKED = 0x40000
    fake.BUTTON5_PRESSED = 0x80000
    fake.BUTTON5_CLICKED = 0x100000
    fake.REPORT_MOUSE_POSITION = 0x10000
    return fake


_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "tests"))
sys.path.insert(0, str(_REPO_ROOT))

for mod_name in (
    "retrotui.constants",
    "retrotui.utils",
    "retrotui.ui.menu",
    "retrotui.ui.window",
    "retrotui.core.actions",
    "retrotui.core.clipboard",
    "retrotui.core.terminal_session",
    "retrotui.apps.terminal",
):
    sys.modules.pop(mod_name, None)

sys.modules["curses"] = _install_fake_curses()

terminal_mod = importlib.import_module("retrotui.apps.terminal")


class _FakeSession:
    instances = []

    def __init__(self, *args, **kwargs):
        self.running = True
        self.cols = kwargs.get("cols", 80)
        self.rows = kwargs.get("rows", 24)
        self.master_fd = 1
        self.writes = []
        _FakeSession.instances.append(self)

    @staticmethod
    def is_supported():
        return True

    def start(self):
        pass

    def read(self, *_):
        return ""

    def poll_exit(self):
        return False

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def close(self):
        self.running = False


class MousePassthroughTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.actions",
            "retrotui.core.clipboard",
            "retrotui.core.terminal_session",
            "retrotui.apps.terminal",
        ):
            sys.modules.pop(mod_name, None)
        cls.terminal_mod = importlib.import_module("retrotui.apps.terminal")
        cls.curses = sys.modules["curses"]

    def setUp(self):
        _FakeSession.instances = []
        with mock.patch.object(self.terminal_mod, "theme_attr", return_value=0):
            with mock.patch.object(self.terminal_mod, "TerminalSession", _FakeSession):
                self.win = self.terminal_mod.TerminalWindow(2, 3, 80, 24)
                self.win.body_rect = mock.Mock(return_value=(4, 5, 70, 18))
                self.win._sync_screen_size()
                # Lazy-start the session so _forward_payload can write to it.
                self.win._ensure_session()
        self.session = _FakeSession.instances[0]  # populated by TerminalWindow._ensure_session()

    def _enable_mouse_mode(self, mode):
        self.win._consume_output(f"\x1b[?{mode}h")

    def _disable_mouse_mode(self, mode):
        self.win._consume_output(f"\x1b[?{mode}l")

    def test_no_mouse_modes_by_default(self):
        self.assertEqual(self.win._mouse_modes, set())

    def test_sgr_mode_1006_is_tracked(self):
        self._enable_mouse_mode(1006)
        self.assertIn(1006, self.win._mouse_modes)
        self._disable_mouse_mode(1006)
        self.assertNotIn(1006, self.win._mouse_modes)

    def test_legacy_modes_1000_1002_1003_are_tracked(self):
        for mode in (1000, 1002, 1003):
            self._enable_mouse_mode(mode)
            self.assertIn(mode, self.win._mouse_modes)
        for mode in (1000, 1002, 1003):
            self._disable_mouse_mode(mode)
            self.assertNotIn(mode, self.win._mouse_modes)

    def test_non_mouse_dec_modes_are_ignored(self):
        # ?25h toggles cursor visibility — not a mouse mode.
        self._enable_mouse_mode(25)
        self.assertEqual(self.win._mouse_modes, set())

    def test_click_forwarded_as_sgr_when_child_enabled(self):
        self._enable_mouse_mode(1006)
        # Click inside the body at (5, 6) with BUTTON1 pressed.
        self.win.handle_click(5, 6, self.curses.BUTTON1_PRESSED)
        self.assertEqual(len(self.session.writes), 1)
        # SGR encoding: \e[<0;Cx;CyM  (Cx = col+1 = 2, Cy = row+1 = 2)
        self.assertEqual(self.session.writes[0], "\x1b[<0;2;2M")

    def test_click_outside_body_not_forwarded(self):
        self._enable_mouse_mode(1006)
        # Outside the body — RetroTUI keeps its title-bar / border logic.
        self.win.handle_click(0, 0, self.curses.BUTTON1_PRESSED)
        self.assertEqual(self.session.writes, [])

    def test_right_click_forwarded_as_button_2(self):
        self._enable_mouse_mode(1006)
        self.win.handle_click(5, 6, self.curses.BUTTON2_PRESSED)
        self.assertEqual(len(self.session.writes), 1)
        self.assertTrue(self.session.writes[0].startswith("\x1b[<1;"))

    def test_motion_forwarded_only_when_motion_mode_enabled(self):
        # 1006 alone = press/release only.
        self._enable_mouse_mode(1006)
        self.win.handle_mouse_drag(5, 6, self.curses.BUTTON1_PRESSED | self.curses.REPORT_MOUSE_POSITION)
        self.assertEqual(self.session.writes, [])
        # 1003 = all motion, including no-button motion.
        self._enable_mouse_mode(1003)
        self.win.handle_mouse_drag(5, 6, self.curses.BUTTON1_PRESSED | self.curses.REPORT_MOUSE_POSITION)
        self.assertGreaterEqual(len(self.session.writes), 1)
        # Drag with button: cb = 0 + 32 = 32 in motion.
        self.assertTrue(self.session.writes[-1].startswith("\x1b[<32;"))

    def test_release_event_uses_m_suffix(self):
        self._enable_mouse_mode(1006)
        self.win.handle_click(5, 6, self.curses.BUTTON1_RELEASED)
        self.assertEqual(self.session.writes[-1], "\x1b[<0;2;2m")

    def test_click_without_mouse_mode_kept_by_retrotui(self):
        # GPM compat: with no mouse modes, RetroTUI starts its own selection.
        self.win.handle_click(5, 6, self.curses.BUTTON1_PRESSED)
        self.assertEqual(self.session.writes, [])
        self.assertIsNotNone(self.win.selection_anchor)

    def test_scroll_wheel_forwarded_when_mouse_mode_on(self):
        self._enable_mouse_mode(1006)
        self.win.handle_scroll("up", 1)
        self.assertEqual(self.session.writes[-1], "\x1b[<64;1;1M")
        self.win.handle_scroll("down", 1)
        self.assertEqual(self.session.writes[-1], "\x1b[<65;1;1M")

    def test_scroll_wheel_stays_in_retrotui_when_mouse_mode_off(self):
        # GPM compat path: scroll wheel moves the scrollback, not the PTY.
        # Populate scrollback so the wheel has somewhere to go.
        for ch in "abcdefghij":
            self.win._consume_output(ch + "\n")
        self.win.handle_scroll("up", 3)
        self.assertEqual(self.session.writes, [])
        self.assertGreater(self.win.scrollback_offset, 0)

    def test_legacy_mode_1000_still_triggers_forward(self):
        # Even when the child asks for the legacy byte-encoded protocol,
        # RetroTUI emits SGR sequences (close enough for modern clients;
        # only ancient clients like pre-3.14 vim complain).
        self._enable_mouse_mode(1000)
        self.win.handle_click(5, 6, self.curses.BUTTON1_PRESSED)
        self.assertEqual(len(self.session.writes), 1)
        self.assertTrue(self.session.writes[0].startswith("\x1b[<"))

    def test_mouse_modes_reset_on_restart(self):
        self._enable_mouse_mode(1006)
        self.win._session = _FakeSession()
        with mock.patch.object(self.terminal_mod, "TerminalSession", _FakeSession):
            self.win.restart_session()
        # After restart the child is fresh and hasn't re-enabled mouse.
        self.assertEqual(self.win._mouse_modes, set())


if __name__ == "__main__":
    unittest.main()

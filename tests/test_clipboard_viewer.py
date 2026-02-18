import importlib
import sys
import types
import unittest
from unittest import mock

from _support import make_fake_curses


class ClipboardViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = make_fake_curses()

        for mod_name in (
            "retrotui.apps.clipboard_viewer",
            "retrotui.ui.window",
            "retrotui.utils",
            "retrotui.core.clipboard",
        ):
            sys.modules.pop(mod_name, None)

        cls.mod = importlib.import_module("retrotui.apps.clipboard_viewer")
        cls.clip = importlib.import_module("retrotui.core.clipboard")

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.clipboard_viewer",
            "retrotui.ui.window",
            "retrotui.utils",
            "retrotui.core.clipboard",
        ):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_show_and_clear(self):
        win = self.mod.ClipboardViewerWindow(0, 0, 40, 12)
        # Set clipboard text
        self.clip.copy_text("hello")
        with mock.patch.object(win, "draw_frame", return_value=0), mock.patch.object(
            self.mod, "safe_addstr"
        ) as safe_addstr, mock.patch.object(self.mod, "theme_attr", return_value=0):
            win.draw(None)

        # Click first item to copy it (should not raise)
        bx, by, bw, bh = win.body_rect()
        win.handle_click(bx, by)

        # Clear via key
        win.handle_key(ord('c'))
        self.assertFalse(self.clip.has_clipboard_text())

import importlib
import sys
import types
import unittest
from unittest import mock

from _support import make_fake_curses


class CharMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = make_fake_curses()

        for mod_name in (
            "retrotui.apps.charmap",
            "retrotui.ui.window",
            "retrotui.utils",
        ):
            sys.modules.pop(mod_name, None)

        cls.mod = importlib.import_module("retrotui.apps.charmap")

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.charmap",
            "retrotui.ui.window",
            "retrotui.utils",
        ):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_init_draw_and_click_select(self):
        win = self.mod.CharacterMapWindow(0, 0, 40, 12)
        with mock.patch.object(win, "draw_frame", return_value=0), mock.patch.object(
            self.mod, "safe_addstr"
        ) as safe_addstr, mock.patch.object(self.mod, "theme_attr", return_value=0):
            win.draw(None)

        bx, by, bw, bh = win.body_rect()
        info = win.handle_click(bx, by)
        self.assertIsNotNone(info)
        self.assertIn('char', info)

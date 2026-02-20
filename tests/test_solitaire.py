import importlib
import sys
import types
import unittest
from unittest import mock

from _support import make_fake_curses


class SolitaireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = make_fake_curses()

        for mod_name in (
            "retrotui.apps.solitaire",
            "retrotui.ui.window",
            "retrotui.utils",
        ):
            sys.modules.pop(mod_name, None)

        cls.mod = importlib.import_module("retrotui.apps.solitaire")

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.solitaire",
            "retrotui.ui.window",
            "retrotui.utils",
        ):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_init_draw_and_click(self):
        win = self.mod.SolitaireWindow(0, 0, 60, 20)
        with mock.patch.object(win, "draw_frame", return_value=0), mock.patch.object(
            self.mod, "safe_addstr"
        ) as safe_addstr, mock.patch.object(self.mod, "theme_attr", return_value=0):
            win.draw(None)

        # Click toggles selection on the first column face-up card (bx+2=3, by+5=8)
        self.assertIsNone(win.selected)
        win.handle_click(3, 8)
        self.assertIsNotNone(win.selected)
        # Click outside to deselect
        win.handle_click(40, 20)
        self.assertIsNone(win.selected)

    def test_auto_move_drain_behavior(self):
        # Create a contrived small position: put an Ace in waste and ensure it moves
        win = self.mod.SolitaireWindow(0, 0, 60, 20)
        
        # Populate card_rects by calling draw
        with mock.patch.object(win, "draw_frame", return_value=0), mock.patch.object(
            self.mod, "safe_addstr"
        ) as safe_addstr, mock.patch.object(self.mod, "theme_attr", return_value=0):
            win.draw(None)
            
        # empty foundations and stock/waste
        win.foundations = [[] for _ in range(4)]
        win.waste = ['AS']
        
        # Double-click waste (bx+8=9, by+1=4) to auto-move
        win.handle_click(9, 4)
        win.handle_click(9, 4)
        
        # waste should be empty and foundation should contain the Ace
        self.assertEqual(win.waste, [])
        found_any = any(f and f[-1] == 'AS' for f in win.foundations)
        self.assertTrue(found_any)

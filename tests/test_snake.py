import importlib
import sys
import types
import unittest
from unittest import mock

from _support import make_fake_curses


class SnakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = make_fake_curses()

        for mod_name in (
            "retrotui.apps.snake",
            "retrotui.ui.window",
            "retrotui.utils",
        ):
            sys.modules.pop(mod_name, None)

        cls.mod = importlib.import_module("retrotui.apps.snake")

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.snake",
            "retrotui.ui.window",
            "retrotui.utils",
        ):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_init_draw_and_movement(self):
        win = self.mod.SnakeWindow(0, 0, 60, 20)
        # Force a draw to initialize rows/cols
        with mock.patch.object(win, "draw_frame", return_value=0), mock.patch.object(
            self.mod, "safe_addstr"
        ), mock.patch.object(self.mod, "theme_attr", return_value=0):
            win.draw(None)
            
        self.assertGreater(win.rows, 0)
        self.assertGreater(win.cols, 0)

        old_head = win.snake[0]
        # Use curses constants from the mock
        win.handle_key(self.mod.curses.KEY_RIGHT)
        win.step()
        self.assertNotEqual(win.snake[0], old_head)

    def test_execute_actions(self):
        win = self.mod.SnakeWindow(0, 0, 60, 20)
        # Mock body_rect to set rows/cols
        win.body_rect = mock.Mock(return_value=(0, 0, 10, 10))
        win._reset_game()
        
        # Test Pause
        self.assertFalse(win.paused)
        win.execute_action(self.mod.AppAction.SNAKE_PAUSE)
        self.assertTrue(win.paused)
        win.execute_action(self.mod.AppAction.SNAKE_PAUSE)
        self.assertFalse(win.paused)
        
        # Test Wrap Toggle
        self.assertFalse(win.wrap_mode)
        win.execute_action(self.mod.AppAction.SNAKE_TOGGLE_WRAP)
        self.assertTrue(win.wrap_mode)
        
        # Test Restart
        win.score = 10
        win.execute_action(self.mod.AppAction.SNAKE_NEW)
        self.assertEqual(win.score, 0)
        
    def test_wrap_movement(self):
        win = self.mod.SnakeWindow(0, 0, 60, 20)
        win.rows = 10
        win.cols = 10
        win.wrap_mode = True
        win.snake = self.mod.deque([(0, 9)])
        win.direction = (0, 1)
        
        win.step()
        self.assertEqual(win.snake[head := 0], (0, 0))
        
    def test_collision_and_game_over(self):
        win = self.mod.SnakeWindow(0, 0, 60, 20)
        win.rows = 5
        win.cols = 5
        win.snake = self.mod.deque([(0, 0), (0, 1)])
        win.direction = (0, 1) # Moving into itself
        
        win.step()
        self.assertTrue(win.game_over)
        
    def test_food_consumption(self):
        win = self.mod.SnakeWindow(0, 0, 60, 20)
        win.rows = 5
        win.cols = 5
        win.snake = self.mod.deque([(0, 0)])
        win.food = (0, 1)
        win.direction = (0, 1)
        
        win.step()
        self.assertEqual(win.score, 1)
        self.assertEqual(len(win.snake), 2)
        self.assertNotEqual(win.food, (0, 1))

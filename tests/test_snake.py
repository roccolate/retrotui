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

    def test_wrap_movement(self):
        win = self.mod.SnakeWindow(0, 0, 60, 20)
        win.rows = 10
        win.cols = 10
        win.wrap_mode = True
        win.snake = self.mod.deque([(0, 9)])
        win.direction = (0, 1)
        
        win.step()
        self.assertEqual(win.snake[head := 0], (0, 0))

    def test_tick_respects_base_speed(self):
        win = self.mod.SnakeWindow(0, 0, 60, 20)
        win.rows = 10
        win.cols = 10
        win.snake = self.mod.deque([(5, 5)])
        win.direction = (0, 1)
        win.food = (0, 0)
        win.base_speed = 1.0
        win._last_move = 100.0
        win._last_special_spawn = 100.0

        with mock.patch.object(self.mod.time, "time", return_value=100.2):
            self.assertFalse(win.tick())
            self.assertEqual(win.snake[0], (5, 5))

        with mock.patch.object(self.mod.time, "time", return_value=101.2):
            self.assertTrue(win.tick())
            self.assertEqual(win.snake[0], (5, 6))
        
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

    def test_difficulty_back_to_back_keeps_menu_consistent(self):
        """Switching difficulty twice in a row keeps the checkmark in sync."""
        win = self.mod.SnakeWindow(0, 0, 60, 20)
        # Cycle through every difficulty and ensure the menu check still
        # reports the new value after repeated updates.
        for new_diff in ("Easy", "Normal", "Hard", "Normal", "Easy"):
            win.execute_action(
                "snake_diff_" + new_diff.lower(),
            )
            diff_items = win.window_menu.items.get("Difficulty", [])
            marks = [label.split(" ", 1)[0] for label, _ in diff_items]
            checked = [name for mark, name in zip(marks, ("Easy", "Normal", "Hard")) if mark == "√"]
            self.assertEqual(checked, [new_diff])
            # The label for every difficulty row must still parse back
            # to the underlying name (the 2-char prefix invariant).
            for label, _ in diff_items:
                base = label[2:] if len(label) > 2 else label
                self.assertIn(base, ("Easy", "Normal", "Hard"))

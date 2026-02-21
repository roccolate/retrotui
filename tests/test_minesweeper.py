import importlib
import sys
import types
import unittest
from unittest import mock

from _support import make_fake_curses


class MinesweeperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = make_fake_curses()

        for mod_name in (
            "retrotui.apps.minesweeper",
            "retrotui.ui.window",
            "retrotui.utils",
        ):
            sys.modules.pop(mod_name, None)

        cls.mod = importlib.import_module("retrotui.apps.minesweeper")

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.minesweeper",
            "retrotui.ui.window",
            "retrotui.utils",
        ):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_init_and_draw_and_click(self):
        win = self.mod.MinesweeperWindow(0, 0, 36, 14)
        # Patch drawing helpers to avoid real curses calls
        with mock.patch.object(win, "draw_frame", return_value=0), mock.patch.object(
            self.mod, "safe_addstr"
        ) as safe_addstr, mock.patch.object(self.mod, "theme_attr", return_value=0):
            win.draw(None)

        bx, by, bw, bh = win.body_rect()
        grid_start_y = by + 3
        grid_start_x = bx + max(0, (bw - win.cols * 3) // 2)
        
        # Click somewhere inside grid to reveal (row 1, col 1)
        # use offset 4 to land in column 1 with 3-char cells
        win.handle_click(grid_start_x + 4, grid_start_y + 1)
        
        # After reveal, at least one cell should be revealed
        revealed_any = any(any(row) for row in win.revealed)
        self.assertTrue(revealed_any)

    def test_first_click_safety_and_count(self):
        # Ensure bombs are not placed on the first-click cell or its neighbors,
        # and that the total number of bombs equals the requested count.
        win = self.mod.MinesweeperWindow(0, 0, 40, 20)
        
        # We use Beginner sizing: 9x9, 10 bombs
        self.assertEqual(win.bombs, 10)
        
        with mock.patch.object(win, "draw_frame", return_value=0), mock.patch.object(
            self.mod, "safe_addstr"
        ) as safe_addstr, mock.patch.object(self.mod, "theme_attr", return_value=0):
            bx, by, bw, bh = win.body_rect()
            grid_start_y = by + 3
            grid_start_x = bx + max(0, (bw - win.cols * 3) // 2)
            
            # Click near the center to trigger safe placement (row 2, col 2)
            # use offset 7 to target column 2 with 3-char cells
            cx = grid_start_x + 7
            cy = grid_start_y + 2
            win.handle_click(cx, cy)

        # Build excluded set (clicked cell + neighbors)
        col = (cx - grid_start_x) // 3
        row = cy - grid_start_y
        exclude = set()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = row + dr, col + dc
                if 0 <= nr < win.rows and 0 <= nc < win.cols:
                    exclude.add((nr, nc))

        # No excluded cell should be a bomb
        for r, c in exclude:
            self.assertNotEqual(win._grid[r][c], -1)

        # Total bombs should match requested
        bomb_count = sum(1 for r in range(win.rows) for c in range(win.cols) if win._grid[r][c] == -1)
        self.assertEqual(bomb_count, win.bombs)

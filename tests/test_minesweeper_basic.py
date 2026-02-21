import time

from retrotui.apps.minesweeper import MinesweeperWindow


def test_reset_and_dimensions():
    ms = MinesweeperWindow(0, 0, 80, 24)
    ms._reset_game('Beginner')
    assert ms.rows == 9 and ms.cols == 9 and ms.bombs == 10
    assert ms.w >= 36 and ms.h >= 14


def test_place_bombs_safe_excludes_click_and_neighbor():
    ms = MinesweeperWindow(0, 0, 80, 24)
    ms._reset_game('Beginner')
    # Use corner click; ensure bombs placed and excluded area has no bomb
    click_r, click_c = 0, 0
    ms._place_bombs_safe(click_r, click_c)
    assert ms._bombs_placed
    # Count bombs
    bombs_found = sum(1 for r in range(ms.rows) for c in range(ms.cols) if ms._grid[r][c] == -1)
    # Compute expected cells the same way implementation does (exclude neighbors that are in-grid)
    exclude = {(click_r + dr, click_c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
    cells = [(r, c) for r in range(ms.rows) for c in range(ms.cols) if (r, c) not in exclude]
    assert bombs_found == min(ms.bombs, len(cells))
    # Exclude neighbors (click and around) should not contain bombs
    exclude = {(click_r + dr, click_c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
    for (r, c) in exclude:
        if 0 <= r < ms.rows and 0 <= c < ms.cols:
            assert ms._grid[r][c] != -1


def test_reveal_and_victory_on_empty_grid():
    ms = MinesweeperWindow(0, 0, 80, 24)
    # Make an empty grid (no bombs)
    ms._reset_game('Beginner')
    for r in range(ms.rows):
        for c in range(ms.cols):
            ms._grid[r][c] = 0
            ms.revealed[r][c] = False
    ms._bombs_placed = True
    # Reveal a cell and expect cascade reveal and victory
    ms._reveal_cell(0, 0)
    assert ms.victory
    assert ms.game_over


def test_toggle_flag_and_handle_click_flagging():
    ms = MinesweeperWindow(0, 0, 80, 24)
    ms._reset_game('Beginner')
    bx, by, bw, bh = ms.body_rect()
    grid_start_y = by + 3
    grid_w = ms.cols * 3
    grid_start_x = bx + max(1, (bw - grid_w) // 2)

    # Click first cell with right-click simulation
    mx = grid_start_x
    my = grid_start_y

    class BState:
        right = True

    ms.handle_click(mx, my, bstate=BState())
    # Toggling flag sets flagged True
    col = (mx - grid_start_x) // 3
    row = my - grid_start_y
    assert ms.flagged[row][col]
import unittest

from retrotui.apps.minesweeper import MinesweeperWindow
from retrotui.core.actions import ActionResult, ActionType


class MinesweeperBasicTests(unittest.TestCase):
    def test_reset_and_place_bombs_safe_first_click_safety(self):
        mw = MinesweeperWindow(0, 0, 40, 20)
        # simulate a left click inside the grid area so bombs are placed
        bx, by, bw, bh = mw.body_rect()
        grid_w = mw.cols * 3
        grid_start_y = by + 3
        grid_start_x = bx + max(1, (bw - grid_w) // 2)
        # click the top-left cell of the grid
        click_x = grid_start_x
        click_y = grid_start_y
        mw.handle_click(click_x, click_y)
        # bombs should be placed and clicked cell should be revealed
        self.assertTrue(mw._bombs_placed)
        self.assertFalse(mw.game_over)

    def test_execute_action_difficulty_switch(self):
        mw = MinesweeperWindow(0, 0, 40, 20)
        res = mw.execute_action('minesweeper_intermediate')
        self.assertIsInstance(res, ActionResult)
        self.assertEqual(res.type, ActionType.REFRESH)


if __name__ == '__main__':
    unittest.main()

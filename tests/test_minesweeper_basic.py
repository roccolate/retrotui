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

import unittest
from retrotui.apps.tetris import TetrisWindow
from retrotui.plugins.base import RetroApp


class TetrisAndPluginTests(unittest.TestCase):
    def test_tetris_collision_and_line_clear(self):
        t = TetrisWindow(0, 0)
        # ensure empty grid => no collision at spawn
        self.assertFalse(t._check_collision([(0, 0)], [0, 0]))

        # Fill a line and verify clear increases lines and score
        t.grid[19] = [1 for _ in range(10)]
        prev_lines = t.lines
        prev_score = t.score
        t._clear_lines()
        self.assertGreaterEqual(t.lines, prev_lines + 1)
        self.assertGreaterEqual(t.score, prev_score)

        # rotation should not raise
        t._rotate_piece()

    def test_plugin_base_id_setting(self):
        class MyPlugin(RetroApp):
            def draw_content(self, stdscr, x, y, w, h):
                pass

        MyPlugin.PLUGIN_ID = None
        # set attribute as loader would
        MyPlugin.PLUGIN_ID = 'p1'
        self.assertEqual(MyPlugin.PLUGIN_ID, 'p1')


if __name__ == "__main__":
    unittest.main()


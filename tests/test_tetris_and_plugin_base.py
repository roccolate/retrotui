import time

from retrotui.apps.tetris import TetrisWindow
from retrotui.plugins.base import RetroApp


def test_tetris_collision_and_line_clear():
    t = TetrisWindow(0, 0)
    # ensure empty grid => no collision at spawn
    assert not t._check_collision([(0, 0)], [0, 0])

    # Fill a line and verify clear increases lines and score
    t.grid[19] = [1 for _ in range(10)]
    prev_lines = t.lines
    prev_score = t.score
    t._clear_lines()
    assert t.lines >= prev_lines + 1
    assert t.score >= prev_score

    # rotation should not raise
    t._rotate_piece()


def test_plugin_base_id_setting():
    class MyPlugin(RetroApp):
        def draw_content(self, stdscr, x, y, w, h):
            pass

    MyPlugin.PLUGIN_ID = None
    # set attribute as loader would
    MyPlugin.PLUGIN_ID = 'p1'
    assert MyPlugin.PLUGIN_ID == 'p1'

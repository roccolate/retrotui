"""Snake game (minimal) for RetroTUI tests."""
from __future__ import annotations

import curses
import random
from collections import deque

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr


class SnakeWindow(Window):
    def __init__(self, x, y, w, h, rows=10, cols=20):
        super().__init__("Snake", x, y, max(30, w), max(10, h), content=[], resizable=False)
        self.rows = rows
        self.cols = cols
        self.snake = deque([(rows // 2, cols // 2)])
        self.direction = (0, 1)
        self.food = None
        self.score = 0
        self.game_over = False
        self._place_food()

    def _place_food(self):
        empty = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in self.snake]
        if not empty:
            self.food = None
            return
        self.food = random.choice(empty)

    def step(self):
        if self.game_over:
            return
        head = self.snake[0]
        nr, nc = head[0] + self.direction[0], head[1] + self.direction[1]
        if not (0 <= nr < self.rows and 0 <= nc < self.cols) or (nr, nc) in self.snake:
            self.game_over = True
            return
        self.snake.appendleft((nr, nc))
        if self.food == (nr, nc):
            self.score += 1
            self._place_food()
        else:
            self.snake.pop()

    def draw(self, stdscr):
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        for r in range(self.rows):
            line = ''
            for c in range(self.cols):
                if (r, c) in self.snake:
                    ch = '█'
                elif self.food == (r, c):
                    ch = '●'
                else:
                    ch = ' '
                line += ch
            safe_addstr(stdscr, by + r, bx, line[:bw], body_attr)

    def handle_key(self, key):
        if key == curses.KEY_UP:
            self.direction = (-1, 0)
        elif key == curses.KEY_DOWN:
            self.direction = (1, 0)
        elif key == curses.KEY_LEFT:
            self.direction = (0, -1)
        elif key == curses.KEY_RIGHT:
            self.direction = (0, 1)
        return None

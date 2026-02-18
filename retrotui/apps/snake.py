"""Snake game (minimal) for RetroTUI tests."""
from __future__ import annotations

import curses
import random
import time
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
        self.paused = False
        self.base_speed = 1.0  # conceptual speed value
        self._last_move = time.time()

    def _place_food(self):
        empty = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in self.snake]
        if not empty:
            self.food = None
            return
        self.food = random.choice(empty)

    def step(self, now: float | None = None, force: bool = False):
        """
        Advance the snake. If `now` is provided the method respects `base_speed` timing
        unless `force` is True. Calling without `now` preserves previous immediate behavior
        for tests that call `step()` directly.
        """
        if self.game_over or self.paused:
            return
        # Preserve legacy behavior: calling step() without a `now` parameter
        # should move immediately (useful for tests). When `now` is provided
        # the caller expects timing-based movement unless `force` is True.
        if now is None:
            now = time.time()
            force = True

        interval = max(0.05, self.base_speed)
        if not force and (now - self._last_move) < interval:
            return

        self._last_move = now

        head = self.snake[0]
        nr, nc = head[0] + self.direction[0], head[1] + self.direction[1]
        if not (0 <= nr < self.rows and 0 <= nc < self.cols) or (nr, nc) in self.snake:
            self.game_over = True
            return
        self.snake.appendleft((nr, nc))
        if self.food == (nr, nc):
            self.score += 1
            self._place_food()
            # increase conceptual speed as score grows (lower interval)
            self.base_speed = max(0.05, 1.0 - (self.score * 0.05))
        else:
            self.snake.pop()

    def draw(self, stdscr):
        if not self.visible:
            return
        # show score and paused state in title
        pfx = "[PAUSED] " if self.paused and not self.game_over else ""
        self.title = f"{pfx}Snake  ♟ {self.score}"
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
        # restart
        if getattr(key, '__int__', None) and int(key) == ord('r'):
            self.snake = deque([(self.rows // 2, self.cols // 2)])
            self.direction = (0, 1)
            self._place_food()
            self.score = 0
            self.game_over = False
            self.paused = False
            self.base_speed = 1.0
            return None
        # pause/resume
        if getattr(key, '__int__', None) and int(key) == ord('p'):
            self.paused = not self.paused
            return None
        # Prevent reversing directly into the snake's neck
        if key == curses.KEY_UP and self.direction != (1, 0):
            self.direction = (-1, 0)
        elif key == curses.KEY_DOWN and self.direction != (-1, 0):
            self.direction = (1, 0)
        elif key == curses.KEY_LEFT and self.direction != (0, 1):
            self.direction = (0, -1)
        elif key == curses.KEY_RIGHT and self.direction != (0, -1):
            self.direction = (0, 1)
        return None

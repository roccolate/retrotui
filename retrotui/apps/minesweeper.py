"""Minesweeper app (minimal, test-friendly)."""
from __future__ import annotations

import curses
import random
import time
from typing import List, Tuple

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr


class MinesweeperWindow(Window):
    def __init__(self, x, y, w, h, rows=9, cols=9, bombs=10):
        super().__init__("Minesweeper", x, y, max(30, w), max(10, h), content=[], resizable=False)
        self.base_title = "Minesweeper"
        self.rows = rows
        self.cols = cols
        self.bombs = bombs
        self.start_time = None
        self.elapsed = 0

        # Grid state: -1 = bomb, 0..8 numbers; revealed and flagged sets
        self._grid = [[0 for _ in range(cols)] for _ in range(rows)]
        self.revealed = [[False for _ in range(cols)] for _ in range(rows)]
        self.flagged = [[False for _ in range(cols)] for _ in range(rows)]
        self._place_bombs()
        self._compute_numbers()
        self.game_over = False
        self.victory = False

    def _place_bombs(self):
        cells = [(r, c) for r in range(self.rows) for c in range(self.cols)]
        bombs = random.sample(cells, min(self.bombs, len(cells)))
        for r, c in bombs:
            self._grid[r][c] = -1

    def _compute_numbers(self):
        for r in range(self.rows):
            for c in range(self.cols):
                if self._grid[r][c] == -1:
                    continue
                count = 0
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < self.rows and 0 <= cc < self.cols:
                            if self._grid[rr][cc] == -1:
                                count += 1
                self._grid[r][c] = count

    def _reveal_cell(self, r, c):
        if self.game_over or self.revealed[r][c] or self.flagged[r][c]:
            return
        self.revealed[r][c] = True
        if self._grid[r][c] == -1:
            self.game_over = True
            return
        if self._grid[r][c] == 0:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < self.rows and 0 <= cc < self.cols and not self.revealed[rr][cc]:
                        self._reveal_cell(rr, cc)

    def toggle_flag(self, r, c):
        if self.game_over or self.revealed[r][c]:
            return
        self.flagged[r][c] = not self.flagged[r][c]

    def _check_victory(self):
        for r in range(self.rows):
            for c in range(self.cols):
                if self._grid[r][c] != -1 and not self.revealed[r][c]:
                    return False
        self.victory = True
        return True

    def draw(self, stdscr):
        if not self.visible:
            return
        # Update title with timer
        if self.start_time and not self.game_over:
            self.elapsed = int(time.time() - self.start_time)
        self.title = f"{self.base_title}  ⏱ {self.elapsed}s"
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        # Draw grid within body
        for r in range(self.rows):
            line = ''
            for c in range(self.cols):
                if self.flagged[r][c]:
                    ch = '🚩'
                elif not self.revealed[r][c]:
                    ch = '█'
                else:
                    v = self._grid[r][c]
                    if v == -1:
                        ch = '💣'
                    elif v == 0:
                        ch = ' '
                    else:
                        ch = str(v)
                line += ch + ' '
            safe_addstr(stdscr, by + r, bx, line[:bw], body_attr)

    def handle_click(self, mx, my, bstate=None):
        # Map click to grid cell
        bx, by, bw, bh = self.body_rect()
        if not (by <= my < by + self.rows and bx <= mx < bx + self.cols * 2):
            return None
        if self.start_time is None:
            self.start_time = time.time()
        col = (mx - bx) // 2
        row = my - by
        # Right-click toggles flag (simulate by bstate truthiness)
        if bstate and getattr(bstate, 'right', False):
            self.toggle_flag(row, col)
        else:
            self._reveal_cell(row, col)
            if self.game_over:
                # reveal all
                for r in range(self.rows):
                    for c in range(self.cols):
                        self.revealed[r][c] = True
            else:
                self._check_victory()
        return None

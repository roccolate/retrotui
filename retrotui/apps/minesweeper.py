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
        # Defer bomb placement until first click so we can guarantee a safe first move
        self._bombs_placed = False
        self.game_over = False
        self.victory = False

    def _place_bombs(self):
        # Backwards-compatible simple placement (no exclusions)
        cells = [(r, c) for r in range(self.rows) for c in range(self.cols)]
        k = min(self.bombs, len(cells))
        bombs = random.sample(cells, k)
        for r, c in bombs:
            self._grid[r][c] = -1
        self._bombs_placed = True

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

    def _place_bombs_safe(self, exclude: set):
        """Place bombs avoiding any coordinates in `exclude` (used for first-click safety)."""
        cells = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in exclude]
        k = min(self.bombs, len(cells))
        if not cells or k <= 0:
            self._bombs_placed = True
            self._compute_numbers()
            return

        # Greedy spread strategy to avoid clustering: pick first bomb randomly,
        # then choose subsequent bombs from a random candidate sample maximizing
        # the minimum Manhattan distance to already-placed bombs.
        bombs: List[Tuple[int, int]] = []
        first = random.choice(cells)
        bombs.append(first)
        remaining = set(cells)
        remaining.discard(first)

        while len(bombs) < k and remaining:
            sample_size = min(50, len(remaining))
            candidates = random.sample(list(remaining), sample_size)
            best = None
            best_min_dist = -1
            for cand in candidates:
                # Manhattan distance to nearest existing bomb
                min_dist = min(abs(cand[0] - b[0]) + abs(cand[1] - b[1]) for b in bombs)
                if min_dist > best_min_dist:
                    best_min_dist = min_dist
                    best = cand
            if best is None:
                best = remaining.pop()
            else:
                remaining.discard(best)
            bombs.append(best)

        for r, c in bombs:
            self._grid[r][c] = -1
        self._bombs_placed = True
        # compute numbers after placement
        self._compute_numbers()

    def _reveal_cell(self, r, c):
        # Iterative flood-fill to avoid deep recursion and duplicate work.
        if self.game_over or self.revealed[r][c] or self.flagged[r][c]:
            return
        stack = [(r, c)]
        while stack:
            rr, cc = stack.pop()
            if self.revealed[rr][cc] or self.flagged[rr][cc]:
                continue
            self.revealed[rr][cc] = True
            if self._grid[rr][cc] == -1:
                self.game_over = True
                return
            if self._grid[rr][cc] == 0:
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        nr, nc = rr + dr, cc + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols and not self.revealed[nr][nc]:
                            stack.append((nr, nc))
        # After revealing, check victory condition (unless game over)
        if not self.game_over:
            self._check_victory()

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
        # Per-cell draw to support colored numbers and chording visuals
        num_role_map = {
            1: 'file_directory',
            2: 'file_selected',
            3: 'menu_selected',
            4: 'button',
            5: 'button_selected',
            6: 'status',
            7: 'icon',
            8: 'icon_selected',
        }
        for r in range(self.rows):
            for c in range(self.cols):
                x = bx + c * 2
                y = by + r
                attr = body_attr
                if self.flagged[r][c]:
                    ch = '🚩'
                    attr |= curses.A_BOLD
                elif not self.revealed[r][c]:
                    ch = '█'
                else:
                    v = self._grid[r][c]
                    if v == -1:
                        ch = '💣'
                        attr |= curses.A_BOLD
                    elif v == 0:
                        ch = ' '
                    else:
                        ch = str(v)
                        # Apply a number-based color role when available
                        role = num_role_map.get(v)
                        try:
                            if role:
                                attr |= theme_attr(role)
                        except Exception:
                            pass
                        attr |= curses.A_BOLD
                safe_addstr(stdscr, y, x, ch, attr)

    def handle_click(self, mx, my, bstate=None):
        # Map click to grid cell
        bx, by, bw, bh = self.body_rect()
        if not (by <= my < by + self.rows and bx <= mx < bx + self.cols * 2):
            return None
        col = (mx - bx) // 2
        row = my - by
        # On first click, place bombs while guaranteeing the clicked cell and neighbors are safe
        if not self._bombs_placed:
            exclude = set()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nr, nc = row + dr, col + dc
                    if 0 <= nr < self.rows and 0 <= nc < self.cols:
                        exclude.add((nr, nc))
            self._place_bombs_safe(exclude)
        if self.start_time is None:
            self.start_time = time.time()
        # Right-click toggles flag (simulate by bstate truthiness)
        if bstate and getattr(bstate, 'right', False):
            self.toggle_flag(row, col)
        else:
            # If clicking a revealed number, perform chording: reveal neighbors
            if self.revealed[row][col] and self._grid[row][col] > 0:
                need = self._grid[row][col]
                flags = 0
                neighbors = []
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        nr, nc = row + dr, col + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols:
                            if self.flagged[nr][nc]:
                                flags += 1
                            elif not self.revealed[nr][nc]:
                                neighbors.append((nr, nc))
                if flags >= need:
                    for nr, nc in neighbors:
                        self._reveal_cell(nr, nc)
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

    def handle_key(self, key):
        # 'r' to restart the game
        if getattr(key, '__int__', None) and int(key) == ord('r'):
            # reset grids
            self._grid = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
            self.revealed = [[False for _ in range(self.cols)] for _ in range(self.rows)]
            self.flagged = [[False for _ in range(self.cols)] for _ in range(self.rows)]
            # Defer bomb placement until first click to preserve safe-first-click behavior
            self._bombs_placed = False
            self.start_time = None
            self.elapsed = 0
            self.game_over = False
            self.victory = False
            return None
        return None

"""Minesweeper app (classic UI)."""
from __future__ import annotations

import curses
import random
import time

from ..ui.window import Window
from ..ui.menu import WindowMenu
from ..core.actions import AppAction, ActionResult, ActionType
from ..utils import safe_addstr, theme_attr


class MinesweeperWindow(Window):
    def __init__(self, x, y, w, h):
        # We will resize internally based on difficulty.
        super().__init__("Minesweeper", x, y, max(30, w), max(16, h), content=[], resizable=False)
        self.window_menu = WindowMenu({
            "Game": [
                ("Beginner (9x9, 10)", "minesweeper_beginner"),
                ("Intermediate (16x16, 40)", "minesweeper_intermediate"),
                ("Expert (30x16, 99)", "minesweeper_expert"),
                ("-", None),
                ("Restart (R)", "minesweeper_restart"),
                ("Close (Q)", AppAction.CLOSE_WINDOW)
            ]
        })
        self.difficulty = "Beginner"
        self._reset_game()

    def _reset_game(self, new_diff=None):
        if new_diff:
            self.difficulty = new_diff
            
        if self.difficulty == "Beginner":
            self.rows, self.cols, self.bombs = 9, 9, 10
        elif self.difficulty == "Intermediate":
            self.rows, self.cols, self.bombs = 16, 16, 40
        else:
            self.rows, self.cols, self.bombs = 16, 30, 99

        # Adjust window size to fit contents:
        # Header = 2 lines + grid + borders
        req_w = max(34, self.cols * 2 + 4)
        req_h = max(12, self.rows + 5)
        self.w, self.h = req_w, req_h

        self.start_time = None
        self.elapsed = 0
        self._grid = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        self.revealed = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        self.flagged = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        self._bombs_placed = False
        self.game_over = False
        self.victory = False

    def execute_action(self, action: str | AppAction) -> ActionResult | None:
        if action == "minesweeper_beginner":
            self._reset_game("Beginner")
            return ActionResult(ActionType.REFRESH)
        elif action == "minesweeper_intermediate":
            self._reset_game("Intermediate")
            return ActionResult(ActionType.REFRESH)
        elif action == "minesweeper_expert":
            self._reset_game("Expert")
            return ActionResult(ActionType.REFRESH)
        elif action == "minesweeper_restart":
            self._reset_game()
            return ActionResult(ActionType.REFRESH)
        elif action == AppAction.CLOSE_WINDOW:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

    def _place_bombs_safe(self, click_r: int, click_c: int):
        exclude = {(click_r + dr, click_c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
        cells = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in exclude]
        
        k = min(self.bombs, len(cells))
        bombs = random.sample(cells, k) if cells else []
        for r, c in bombs:
            self._grid[r][c] = -1
        self._bombs_placed = True
        
        # compute numbers
        for r in range(self.rows):
            for c in range(self.cols):
                if self._grid[r][c] == -1: continue
                count = sum(1 for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                            if 0 <= r+dr < self.rows and 0 <= c+dc < self.cols and self._grid[r+dr][c+dc] == -1)
                self._grid[r][c] = count

    def _reveal_cell(self, r, c):
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

        if not self.game_over:
            self._check_victory()

    def toggle_flag(self, r, c):
        if self.game_over or self.revealed[r][c]: return
        self.flagged[r][c] = not self.flagged[r][c]

    def _check_victory(self):
        for r in range(self.rows):
            for c in range(self.cols):
                if self._grid[r][c] != -1 and not self.revealed[r][c]:
                    return
        self.victory = True
        self.game_over = True

    def draw(self, stdscr):
        if not self.visible: return
        
        if self.start_time and not self.game_over:
            self.elapsed = int(time.time() - self.start_time)
            
        self.title = f"Minesweeper - {self.difficulty}"
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        
        # Clear body
        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, " " * bw, body_attr)
            
        # Draw Classic Header
        flags_used = sum(1 for r in range(self.rows) for c in range(self.cols) if self.flagged[r][c])
        bombs_left = max(0, self.bombs - flags_used)
        
        timer_str = f"{min(999, self.elapsed):03d}"
        bombs_str = f"{bombs_left:03d}"
        
        smiley = "🙂"
        if self.victory: smiley = "😎"
        elif self.game_over: smiley = "😵"
        
        header_y = by + 1
        safe_addstr(stdscr, header_y, bx + 2, bombs_str, curses.color_pair(1) | curses.A_BOLD) # Red text if possible
        
        center_x = bx + (bw // 2) - 1
        safe_addstr(stdscr, header_y, center_x, smiley, body_attr)
        
        safe_addstr(stdscr, header_y, bx + bw - 5, timer_str, curses.color_pair(1) | curses.A_BOLD)
        
        # Draw Grid horizontally centered
        grid_start_y = by + 3
        grid_w = self.cols * 2
        grid_start_x = bx + max(0, (bw - grid_w) // 2)
        
        from ..constants import C_ANSI_START
        color_map = {
            1: getattr(curses, 'COLOR_BLUE', 4),
            2: getattr(curses, 'COLOR_GREEN', 2),
            3: getattr(curses, 'COLOR_RED', 1),
            4: getattr(curses, 'COLOR_BLUE', 4),
            5: getattr(curses, 'COLOR_RED', 1),
            6: getattr(curses, 'COLOR_CYAN', 6),
            7: getattr(curses, 'COLOR_WHITE', 7),
            8: getattr(curses, 'COLOR_WHITE', 7),
        }

        for r in range(self.rows):
            for c in range(self.cols):
                x = grid_start_x + c * 2
                y = grid_start_y + r
                attr = body_attr
                
                if self.flagged[r][c] and (not self.game_over or self._grid[r][c] == -1):
                    ch = '🚩'
                elif self.flagged[r][c] and self.game_over and self._grid[r][c] != -1:
                    ch = '❌' # wrongly flagged
                elif not self.revealed[r][c]:
                    ch = '█' if not (self.game_over and not self.victory and self._grid[r][c] == -1) else '💣'
                else:
                    v = self._grid[r][c]
                    if v == -1:
                        ch = '💥'
                    elif v == 0:
                        ch = '·' # Empty space subtle dot
                        attr = curses.A_DIM
                    else:
                        ch = str(v)
                        c_val = color_map.get(v, curses.COLOR_WHITE)
                        attr = curses.color_pair(C_ANSI_START + c_val) | curses.A_BOLD
                        
                safe_addstr(stdscr, y, x, ch, attr)

        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def handle_click(self, mx, my, bstate=None):
        if self.window_menu and (self.window_menu.active or self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w)):
            res = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
            if res: return self.execute_action(res)
            return None

        bx, by, bw, bh = self.body_rect()
        
        # Check Smiley click
        header_y = by + 1
        center_x = bx + (bw // 2) - 1
        if my == header_y and center_x <= mx <= center_x + 2:
            self._reset_game()
            return None

        # Grid bounds check
        grid_start_y = by + 3
        grid_w = self.cols * 2
        grid_start_x = bx + max(0, (bw - grid_w) // 2)
        
        if not (grid_start_y <= my < grid_start_y + self.rows and grid_start_x <= mx < grid_start_x + grid_w):
            return None
            
        col = (mx - grid_start_x) // 2
        row = my - grid_start_y
        
        if bstate and getattr(bstate, 'right', False): # Right click
            self.toggle_flag(row, col)
            return None

        # Double click (or middle, simulate chord on previously revealed cell)
        # We will use simple chord if you left-click a revealed number
        if self.revealed[row][col] and self._grid[row][col] > 0:
            need = self._grid[row][col]
            flags = sum(1 for dr in (-1,0,1) for dc in (-1,0,1) 
                        if 0<=row+dr<self.rows and 0<=col+dc<self.cols and self.flagged[row+dr][col+dc])
            if flags >= need:
                for dr in (-1,0,1):
                    for dc in (-1,0,1):
                        nr, nc = row+dr, col+dc
                        if 0<=nr<self.rows and 0<=nc<self.cols:
                            self._reveal_cell(nr, nc)
            return None

        # Normal left click
        if not self._bombs_placed:
            self._place_bombs_safe(row, col)
            self.start_time = time.time()
            
        self._reveal_cell(row, col)
        return None

    def handle_key(self, key):
        if self.window_menu and self.window_menu.active:
            res = self.window_menu.handle_key(key)
            if res: return self.execute_action(res)
            return None

        if getattr(key, '__int__', None) and int(key) == ord('r'):
            self._reset_game()
        elif getattr(key, '__int__', None) and int(key) == ord('f'):
            # Fallback flag key if no mouse right click
            # But we don't know the cursor pos precisely. Ignore.
            pass
        return None


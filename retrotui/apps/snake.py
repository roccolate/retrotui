"""Snake game for RetroTUI."""
from __future__ import annotations

import curses
import random
import time
from collections import deque

from ..ui.window import Window
from ..ui.menu import WindowMenu
from ..core.actions import AppAction, ActionResult, ActionType
from ..constants import (
    ICONS, ICONS_ASCII, TASKBAR_TITLE_MAX_LEN, BINARY_DETECT_CHUNK_SIZE,
    C_ANSI_START
)
from ..utils import safe_addstr, theme_attr, normalize_key_code


class SnakeWindow(Window):
    def __init__(self, x, y, w, h):
        super().__init__("Snake", x, y, max(34, w), max(12, h), content=[], resizable=True)
        self.snake = deque()
        self.direction = (0, 1)
        self.food = None
        self.score = 0
        self.game_over = False
        self.paused = False
        self.wrap_mode = False
        self.base_speed = 0.2  # Interval in seconds
        self._last_move = time.time()
        
        # Grid dimensions will be calculated during draw based on body_rect
        self.rows = 0
        self.cols = 0

        self.window_menu = WindowMenu({
            "Game": [
                ("New Game (R)", AppAction.SNAKE_NEW),
                ("-", None),
                ("Pause (P)", AppAction.SNAKE_PAUSE),
                ("Close (Q)", AppAction.CLOSE_WINDOW),
            ],
            "Options": [
                ("  Wrap Around", AppAction.SNAKE_TOGGLE_WRAP),
            ],
        })
        
        self._reset_game()

    def _reset_game(self):
        bx, by, bw, bh = self.body_rect()
        self.rows = bh
        self.cols = bw
        self.snake = deque([(self.rows // 2, self.cols // 2)])
        self.direction = (0, 1)
        self._place_food()
        self.score = 0
        self.game_over = False
        self.paused = False
        self.base_speed = 0.2
        self._last_move = time.time()

    def _place_food(self):
        if self.rows <= 0 or self.cols <= 0:
            return
        empty = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in self.snake]
        if not empty:
            self.food = None
            return
        self.food = random.choice(empty)

    def execute_action(self, action: str | AppAction) -> ActionResult | None:
        if action == AppAction.SNAKE_NEW:
            self._reset_game()
            return ActionResult(ActionType.REFRESH)
        elif action == AppAction.SNAKE_PAUSE:
            if not self.game_over:
                self.paused = not self.paused
            return ActionResult(ActionType.REFRESH)
        elif action == AppAction.SNAKE_TOGGLE_WRAP:
            self.wrap_mode = not self.wrap_mode
            self._update_menu_checks()
            return ActionResult(ActionType.REFRESH)
        elif action == AppAction.CLOSE_WINDOW:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

    def _update_menu_checks(self):
        items = self.window_menu.items.get("Options", [])
        for i, (label, action) in enumerate(items):
            if action == AppAction.SNAKE_TOGGLE_WRAP:
                mark = "√" if self.wrap_mode else " "
                items[i] = (f"{mark} Wrap Around", action)

    def step(self, now: float | None = None, force: bool = False):
        if self.game_over or self.paused:
            return
        
        if now is None:
            now = time.time()
            force = True

        if not force and (now - self._last_move) < self.base_speed:
            return

        self._last_move = now

        head = self.snake[0]
        nr, nc = head[0] + self.direction[0], head[1] + self.direction[1]
        
        if self.wrap_mode:
            nr %= self.rows
            nc %= self.cols
        elif not (0 <= nr < self.rows and 0 <= nc < self.cols):
            self.game_over = True
            return

        if (nr, nc) in self.snake:
            self.game_over = True
            return

        self.snake.appendleft((nr, nc))
        if self.food == (nr, nc):
            self.score += 1
            self._place_food()
            # Increase speed slightly
            self.base_speed = max(0.05, 0.2 - (self.score * 0.005))
        else:
            self.snake.pop()

    def draw(self, stdscr):
        if not self.visible:
            return
            
        self.step()  # Update game state
        
        bx, by, bw, bh = self.body_rect()
        # Update grid dimensions if window was resized
        if bh != self.rows or bw != self.cols:
            self.rows = bh
            self.cols = bw
            # Ensure snake and food are still in bounds, or reset
            if not all(0 <= r < self.rows and 0 <= c < self.cols for r, c in self.snake):
                self._reset_game()
            elif self.food and not (0 <= self.food[0] < self.rows and 0 <= self.food[1] < self.cols):
                self._place_food()

        # Update title
        state = ""
        if self.game_over:
            state = "[GAME OVER] "
        elif self.paused:
            state = "[PAUSED] "
        self.title = f"{state}Snake  ♟ {self.score}"
        
        body_attr = self.draw_frame(stdscr)
        
        # Clear body with background
        for r in range(bh):
            safe_addstr(stdscr, by + r, bx, " " * bw, body_attr)
            
        # Draw food (Red)
        if self.food:
            fr, fc = self.food
            food_attr = curses.color_pair(C_ANSI_START + curses.COLOR_RED) | curses.A_BOLD
            safe_addstr(stdscr, by + fr, bx + fc, "●", food_attr)
            
        # Draw snake (Green, or Red if Game Over)
        color = curses.COLOR_RED if self.game_over else curses.COLOR_GREEN
        snake_attr = curses.color_pair(C_ANSI_START + color) | curses.A_BOLD
        for i, (r, c) in enumerate(self.snake):
            char = "O" if i == 0 else "o"
            if self.game_over:
                char = "X"
            safe_addstr(stdscr, by + r, bx + c, char, snake_attr)
            
        # Draw window menu dropdown on top
        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def handle_key(self, key):
        if self.window_menu.active:
            res = self.window_menu.handle_key(key)
            if res:
                return self.execute_action(res)

        k = normalize_key_code(key)
        
        if k == ord('r') or k == ord('R'):
            return self.execute_action(AppAction.SNAKE_NEW)
        if k == ord('p') or k == ord('P'):
            return self.execute_action(AppAction.SNAKE_PAUSE)
        if k == ord('q') or k == ord('Q'):
            return self.execute_action(AppAction.CLOSE_WINDOW)

        # Movement keys (Arrows or WASD)
        if (k == curses.KEY_UP or k == ord('w')) and self.direction != (1, 0):
            self.direction = (-1, 0)
        elif (k == curses.KEY_DOWN or k == ord('s')) and self.direction != (-1, 0):
            self.direction = (1, 0)
        elif (k == curses.KEY_LEFT or k == ord('a')) and self.direction != (0, 1):
            self.direction = (0, -1)
        elif (k == curses.KEY_RIGHT or k == ord('d')) and self.direction != (0, -1):
            self.direction = (0, 1)
            
        return None

    def handle_click(self, mx, my, bstate=None):
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                res = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if res:
                    return self.execute_action(res)
                return None
        return super().handle_click(mx, my)

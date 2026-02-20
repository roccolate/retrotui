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
        self.obstacles_mode = False
        self.obstacles = set()
        self.special_food = None
        self.special_food_expires = 0
        self._last_special_spawn = time.time()
        
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
                ("  Obstacles", AppAction.SNAKE_TOGGLE_OBSTACLES),
            ],
        })
        
        self._reset_game()

    def _reset_game(self):
        bx, by, bw, bh = self.body_rect()
        self.rows = bh
        self.cols = bw
        self.snake = deque([(self.rows // 2, self.cols // 2)])
        self.direction = (0, 1)
        self.obstacles.clear()
        if self.obstacles_mode:
            self._place_obstacles()
        self._place_food()
        self.special_food = None
        self.special_food_expires = 0
        self._last_special_spawn = time.time()
        self.score = 0
        self.game_over = False
        self.paused = False
        self.base_speed = 0.2
        self._last_move = time.time()

    def _place_obstacles(self):
        # Place about 10% of the grid as obstacles
        count = (self.rows * self.cols) // 10
        attempts = 0
        while len(self.obstacles) < count and attempts < count * 2:
            r = random.randint(0, self.rows - 1)
            c = random.randint(0, self.cols - 1)
            # Avoid snake start position and its surroundings
            if (r, c) not in self.snake and abs(r - self.rows // 2) > 2 and abs(c - self.cols // 2) > 2:
                self.obstacles.add((r, c))
            attempts += 1

    def _place_food(self, special=False):
        if self.rows <= 0 or self.cols <= 0:
            return
        
        # Combined occupied cells
        occupied = set(self.snake) | self.obstacles
        if self.food: occupied.add(self.food)
        if self.special_food: occupied.add(self.special_food)
        
        empty = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in occupied]
        if not empty:
            if special: self.special_food = None
            else: self.food = None
            return
            
        pos = random.choice(empty)
        if special:
            self.special_food = pos
            self.special_food_expires = time.time() + 5.0
        else:
            self.food = pos

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
        elif action == AppAction.SNAKE_TOGGLE_OBSTACLES:
            self.obstacles_mode = not self.obstacles_mode
            self._update_menu_checks()
            # If turning on or off, a new game is best to apply/clear obstacles
            self._reset_game()
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
            elif action == AppAction.SNAKE_TOGGLE_OBSTACLES:
                mark = "√" if self.obstacles_mode else " "
                items[i] = (f"{mark} Obstacles", action)

    def step(self, now: float | None = None, force: bool = False):
        if self.game_over or self.paused:
            return
        
        if now is None:
            now = time.time()
            force = True

        # Special food expiration
        if self.special_food and now > self.special_food_expires:
            self.special_food = None

        # Special food spawning (every ~15s)
        if not self.special_food and (now - self._last_special_spawn) > 15.0:
            self._last_special_spawn = now
            self._place_food(special=True)

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

        # Collision with self, obstacles
        target = (nr, nc)
        if target in self.snake or target in self.obstacles:
            self.game_over = True
            return

        self.snake.appendleft(target)
        if target == self.food:
            self.score += 1
            self._place_food()
            # Increase speed slightly
            self.base_speed = max(0.05, 0.2 - (self.score * 0.005))
        elif target == self.special_food:
            self.score += 5
            self.special_food = None
            # Do NOT increase speed for special food as much (optional)
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
            
        # Draw obstacles
        obs_attr = body_attr | theme_attr("window_inactive")
        for r, c in self.obstacles:
            safe_addstr(stdscr, by + r, bx + c, "▒", obs_attr)

        # Draw food (Red)
        if self.food:
            fr, fc = self.food
            food_attr = curses.color_pair(C_ANSI_START + curses.COLOR_RED) | curses.A_BOLD
            safe_addstr(stdscr, by + fr, bx + fc, "●", food_attr)

        # Draw special food (Yellow)
        if self.special_food:
            sr, sc = self.special_food
            s_attr = curses.color_pair(C_ANSI_START + curses.COLOR_YELLOW) | curses.A_BOLD
            safe_addstr(stdscr, by + sr, bx + sc, "★", s_attr)
            
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

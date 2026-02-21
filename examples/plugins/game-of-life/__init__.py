"""Conway's Game of Life plugin (example).

Controls:
- 's' start/stop simulation
- 'n' step once
- 'c' clear
"""
import time
import random
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = False
        self.last_tick = time.time()
        self.grid = {}

    def _ensure_grid(self, w, h):
        for yy in range(h):
            for xx in range(w):
                self.grid.setdefault((xx, yy), False)

    def _step(self, w, h):
        new = {}
        for yy in range(h):
            for xx in range(w):
                alive = self.grid.get((xx, yy), False)
                neighbors = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        if self.grid.get(((xx + dx) % w, (yy + dy) % h), False):
                            neighbors += 1
                if alive and neighbors in (2, 3):
                    new[(xx, yy)] = True
                elif not alive and neighbors == 3:
                    new[(xx, yy)] = True
                else:
                    new[(xx, yy)] = False
        self.grid = new

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        self._ensure_grid(w, h)
        now = time.time()
        if self.running and now - self.last_tick > 0.3:
            self._step(w, h)
            self.last_tick = now

        for yy in range(h):
            line = ''
            for xx in range(w):
                ch = '█' if self.grid.get((xx, yy), False) else ' '
                line += ch
            safe_addstr(stdscr, y + yy, x, line[:w], attr)

    def handle_key(self, key):
        if key == ord('s'):
            self.running = not self.running
        elif key == ord('n'):
            # step once
            # need current body size; fallback to modest size
            w, h = max(10, self.w - 2), max(6, self.h - 2)
            self._ensure_grid(w, h)
            self._step(w, h)
        elif key == ord('c'):
            self.grid = {}
        elif key == ord('r'):
            # randomize
            w, h = max(10, self.w - 2), max(6, self.h - 2)
            self.grid = {}
            for yy in range(h):
                for xx in range(w):
                    self.grid[(xx, yy)] = (random.random() < 0.2)

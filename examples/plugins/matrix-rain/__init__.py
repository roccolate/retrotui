"""Matrix Rain plugin (example).

Simple column-based falling characters effect. Non-blocking and safe.
"""
import time
import random
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cols = []
        self.last_w = 0

    def _ensure(self, w, h):
        if w != self.last_w:
            self.cols = [0] * max(1, w)
            self.last_w = w

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        self._ensure(w, h)
        t = time.time()
        for row in range(h):
            line = [' '] * w
            for col in range(w):
                # occasionally start a drop
                if random.random() < 0.02:
                    self.cols[col] = 1
                if self.cols[col] > 0:
                    ch = chr(33 + (int(t * 100) + col) % 94)
                    line[col] = ch
                    # advance with some probability
                    if random.random() < 0.25:
                        self.cols[col] += 1
                    # fade out
                    if self.cols[col] > h + 5:
                        self.cols[col] = 0
            safe_addstr(stdscr, y + row, x, ''.join(line)[:w], attr)

    def handle_key(self, key):
        if key == ord('c'):
            self.cols = [0] * max(1, self.last_w)

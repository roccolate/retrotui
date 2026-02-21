"""ASCII Aquarium plugin (example animated widget).

Simple time-based animation that draws fish and bubbles. Safe and
non-blocking: relies on repeated draw calls from the host.
"""
import time
import random
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seed = random.randint(0, 1000000)

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        t = int(time.time() * 2) + (self.seed % 10)
        # draw water background with simple gradient dots
        for row in range(h):
            line = ''
            for col in range(w):
                # occasional bubble
                if (col + row + t) % 23 == 0:
                    ch = 'o'
                else:
                    ch = ' '
                line += ch
            safe_addstr(stdscr, y + row, x, line[:w], attr)

        # draw a few fish moving horizontally
        for i in range(3):
            ry = y + (i * 2) + 1
            cx = (t * (i + 1) * 3) % max(1, w)
            fish = '<><' if (i + t) % 2 == 0 else '><>'
            safe_addstr(stdscr, ry, x + (cx % max(1, w)), fish[:max(0, w - cx)], attr)

    def handle_key(self, key):
        # 'r' reseed
        if key == ord('r'):
            self.seed = random.randint(0, 1000000)

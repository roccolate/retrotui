"""Fortune Cookie plugin (example)."""
import os
import random
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


DEFAULT_FORTUNES = [
    "You will have a pleasant surprise.",
    "Now is the time to try something new.",
    "A friend asks only for your time, not your money.",
    "Happiness begins with facing life with a smile and a wink.",
]


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fortune = self._pick()

    def _pick(self):
        # try system fortune files briefly
        paths = ['/usr/share/games/fortunes', '/usr/share/fortune']
        for p in paths:
            if os.path.isdir(p):
                try:
                    # pick a random file inside
                    files = [os.path.join(p, f) for f in os.listdir(p) if os.path.isfile(os.path.join(p,f))]
                    if files:
                        f = random.choice(files)
                        with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                            lines = [l.strip() for l in fh if l.strip()]
                        if lines:
                            return random.choice(lines)
                except Exception:
                    pass
        return random.choice(DEFAULT_FORTUNES)

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        safe_addstr(stdscr, y + (h // 2), x + 2, self.fortune[: max(0, w-4) ], attr)

    def handle_key(self, key):
        # press 'n' for new fortune
        if key == ord('n'):
            self.fortune = self._pick()

"""Weather Widget plugin (example).

Fetches a one-line weather summary from wttr.in (best-effort, non-blocking
on draw). Press 'r' to refresh.
"""
import urllib.request
import time
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, location='auto', **kwargs):
        super().__init__(*args, **kwargs)
        self.location = location
        self.summary = 'Weather: N/A'
        self.last = 0

    def _fetch(self):
        try:
            url = f'https://wttr.in/{self.location}?format=1'
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = resp.read().decode('utf-8', 'ignore').strip()
                if data:
                    self.summary = data
                    self.last = time.time()
        except Exception:
            pass

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        # auto-refresh every 10 minutes
        if time.time() - self.last > 600:
            self._fetch()
        safe_addstr(stdscr, y + (h // 2), x + 1, self.summary[: max(0, w-2) ], attr)

    def handle_key(self, key):
        if key == ord('r'):
            self._fetch()

"""Pomodoro Timer plugin (example)."""
import time
import os
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = 'idle'  # idle, running, break
        self.start_ts = None
        self.duration = 25 * 60
        self.completed = 0
        self._load()

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        safe_addstr(stdscr, y, x, f"Pomodoro: {self.state}", attr)
        if self.start_ts:
            rem = max(0, int(self.duration - (time.time() - self.start_ts)))
            m, s = divmod(rem, 60)
            safe_addstr(stdscr, y + 1, x, f"Remaining: {m:02d}:{s:02d}", attr)

    def handle_key(self, key):
        # simplistic controls: 's' start/stop, 'r' reset
        if key == ord('s'):
            if self.state == 'running':
                self.state = 'idle'
                self.start_ts = None
            else:
                self.state = 'running'
                self.start_ts = time.time()
        elif key == ord('r'):
            self.start_ts = time.time() if self.state == 'running' else None

    def _data_path(self):
        return os.path.expanduser('~/.config/retrotui/pomodoro.json')

    def _load(self):
        path = self._data_path()
        try:
            if os.path.exists(path):
                import json
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.completed = int(data.get('completed', 0))
        except Exception:
            self.completed = 0

    def _save(self):
        path = self._data_path()
        try:
            import json
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'completed': self.completed}, f)
        except Exception:
            pass

    def _check_complete(self):
        if self.state == 'running' and self.start_ts:
            rem = self.duration - (time.time() - self.start_ts)
            if rem <= 0:
                # session finished
                self.state = 'idle'
                self.start_ts = None
                self.completed += 1
                try:
                    import curses
                    curses.beep()
                except Exception:
                    pass
                self._save()


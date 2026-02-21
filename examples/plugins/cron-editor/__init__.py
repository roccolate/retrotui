"""Cron Editor plugin (example).

This plugin reads the current user's crontab via `crontab -l` and allows
appending a sample line. On systems without `crontab`, it falls back to a
local config file under ~/.config/retrotui/cron.txt for demo purposes.
"""
import os
import shutil
import subprocess
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lines = []
        self._load()

    def _data_path(self):
        return os.path.expanduser('~/.config/retrotui/cron.txt')

    def _load(self):
        # prefer crontab -l
        if shutil.which('crontab'):
            try:
                out = subprocess.check_output(['crontab', '-l'], stderr=subprocess.DEVNULL)
                self.lines = out.decode('utf-8', 'ignore').splitlines()
                return
            except subprocess.CalledProcessError:
                # no crontab or empty
                self.lines = []
                return
            except Exception:
                self.lines = []
                return

        # fallback file
        p = self._data_path()
        try:
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    self.lines = f.read().splitlines()
        except Exception:
            self.lines = []

    def _save(self):
        if shutil.which('crontab'):
            try:
                data = '\n'.join(self.lines) + '\n'
                subprocess.run(['crontab', '-'], input=data.encode('utf-8'), check=True)
                return
            except Exception:
                pass
        try:
            p = self._data_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.lines) + '\n')
        except Exception:
            pass

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        header = 'Crontab (press a to append sample, s to save)'
        safe_addstr(stdscr, y, x, header[:w], attr)
        for i, line in enumerate(self.lines[: max(0, h-1) ]):
            safe_addstr(stdscr, y + 1 + i, x, line[:w], attr)

    def handle_key(self, key):
        if key == ord('a'):
            # append a harmless sample job (runs every day at midnight)
            self.lines.append('0 0 * * * /usr/bin/true')
        elif key == ord('s'):
            self._save()

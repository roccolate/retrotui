"""Service Manager plugin (example).

This plugin is conservative: it will only call `systemctl` if present and
wraps invocations in try/except to avoid crashing the host app.
"""
import shutil
import subprocess
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.services = []  # list of (name, load, active, sub)
        self.selected = 0
        self._load()

    def _load(self):
        if not shutil.which('systemctl'):
            self.services = []
            return
        try:
            out = subprocess.check_output(['systemctl', 'list-units', '--type=service', '--all', '--no-legend'], stderr=subprocess.DEVNULL)
            lines = out.decode('utf-8', 'ignore').splitlines()
            services = []
            for L in lines:
                parts = L.split(None, 4)
                if len(parts) >= 4:
                    name = parts[0]
                    load = parts[1]
                    active = parts[2]
                    sub = parts[3]
                    services.append((name, load, active, sub))
            self.services = services
        except Exception:
            self.services = []

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        if not self.services:
            safe_addstr(stdscr, y, x, "systemctl not available or no services detected"[:w], attr)
            return
        for i, s in enumerate(self.services[:h]):
            name, load, active, sub = s
            a = attr
            if i == self.selected:
                a = theme_attr('menu_selected')
            line = f"{name:40} {active:8} {sub:10}"
            safe_addstr(stdscr, y + i, x, line[:w], a)

    def handle_key(self, key):
        if key == ord('j'):
            self.selected = min(self.selected + 1, len(self.services) - 1)
        elif key == ord('k'):
            self.selected = max(0, self.selected - 1)
        elif key == ord('r'):
            self._load()
        elif key == ord('s'):
            # try to start/stop selected service (toggle based on 'active')
            if not self.services:
                return
            name, load, active, sub = self.services[self.selected]
            if not shutil.which('systemctl'):
                return
            try:
                if active == 'active':
                    subprocess.check_call(['systemctl', 'stop', name])
                else:
                    subprocess.check_call(['systemctl', 'start', name])
            except Exception:
                pass
            finally:
                self._load()

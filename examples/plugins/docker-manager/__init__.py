"""Docker Manager plugin (example).

Uses the `docker` CLI if available to list containers and toggle start/stop.
All subprocess calls are wrapped to avoid crashing the host.
"""
import shutil
import subprocess
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.containers = []  # list of (id, name, status)
        self.selected = 0
        self._load()

    def _load(self):
        if not shutil.which('docker'):
            self.containers = []
            return
        try:
            out = subprocess.check_output(['docker', 'ps', '-a', '--format', '{{.ID}}\t{{.Names}}\t{{.Status}}'], stderr=subprocess.DEVNULL)
            lines = out.decode('utf-8', 'ignore').splitlines()
            self.containers = [tuple(l.split('\t', 2)) for l in lines]
        except Exception:
            self.containers = []

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        if not self.containers:
            safe_addstr(stdscr, y, x, 'docker CLI not found or no containers'[:w], attr)
            return
        for i, (cid, name, status) in enumerate(self.containers[:h]):
            a = attr
            if i == self.selected:
                a = theme_attr('menu_selected')
            line = f"{cid[:12]} {status:20} {name}"
            safe_addstr(stdscr, y + i, x, line[:w], a)

    def handle_key(self, key):
        if key == ord('j'):
            self.selected = min(self.selected + 1, len(self.containers) - 1)
        elif key == ord('k'):
            self.selected = max(0, self.selected - 1)
        elif key == ord('r'):
            self._load()
        elif key == ord('t'):
            # toggle start/stop
            if not self.containers:
                return
            cid, name, status = self.containers[self.selected]
            try:
                if status.lower().startswith('up'):
                    subprocess.check_call(['docker', 'stop', cid])
                else:
                    subprocess.check_call(['docker', 'start', cid])
            except Exception:
                pass
            finally:
                self._load()

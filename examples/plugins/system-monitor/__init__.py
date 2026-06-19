"""System Monitor plugin (example)."""
import os
import shutil
import time
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    needs_redraw = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_ts = time.time()

    def _read_mem(self):
        try:
            data = {}
            with open('/proc/meminfo', 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    k, v = line.split(':', 1)
                    data[k.strip()] = int(v.strip().split()[0])
            total = data.get('MemTotal', 0)
            free = data.get('MemAvailable', data.get('MemFree', 0))
            used = total - free
            return total * 1024, used * 1024, free * 1024
        except (OSError, ValueError, IndexError):
            return None

    def _read_uptime(self):
        try:
            with open('/proc/uptime', 'r', encoding='utf-8', errors='replace') as f:
                u = float(f.read().split()[0])
            return int(u)
        except (OSError, ValueError, IndexError):
            return None

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        # Load average
        try:
            load = os.getloadavg()
            safe_addstr(stdscr, y, x, f"Load avg: {load[0]:.2f} {load[1]:.2f} {load[2]:.2f}"[:w], attr)
        except (OSError, AttributeError):
            safe_addstr(stdscr, y, x, "Load avg: N/A"[:w], attr)

        mem = self._read_mem()
        if mem:
            total, used, free = mem
            safe_addstr(stdscr, y + 1, x, f"Memory: {used//1024//1024}MB / {total//1024//1024}MB"[:w], attr)
        else:
            safe_addstr(stdscr, y + 1, x, "Memory: N/A"[:w], attr)

        try:
            du = shutil.disk_usage('/')
            disk_text = f"Disk /: {du.used//1024//1024}MB / {du.total//1024//1024}MB"
        except OSError:
            disk_text = "Disk /: N/A"
        safe_addstr(stdscr, y + 2, x, disk_text[:w], attr)

        uptime = self._read_uptime()
        if uptime is not None:
            safe_addstr(stdscr, y + 3, x, f"Uptime: {uptime}s"[:w], attr)
        else:
            safe_addstr(stdscr, y + 3, x, "Uptime: N/A"[:w], attr)

    def handle_key(self, key):
        # 'r' refresh (no-op here since draw reads live)
        if key == ord('r'):
            pass

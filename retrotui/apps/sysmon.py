"""System Monitor application for RetroTUI."""
import curses
import os
import time
from collections import deque

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr

class SystemMonitorWindow(Window):
    """Real-time system resource monitor with ASCII graphs."""

    def __init__(self, x, y, w, h):
        super().__init__('System Monitor', x, y, w, h)
        self.cpu_history = deque([0] * 30, maxlen=30)
        self.last_cpu_times = self._get_cpu_times()
        self.mem_info = {'total': 0, 'free': 0, 'available': 0}
        self._update_stats()
        self.last_update = time.time()
        self.update_interval = 1.0

    def _get_cpu_times(self):
        """Read /proc/stat to get total and idle CPU times."""
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
                if line.startswith('cpu '):
                    parts = [float(x) for x in line.split()[1:]]
                    idle = parts[3] # idle
                    total = sum(parts)
                    return idle, total
        except (OSError, ValueError, IndexError):
            pass
        return 0, 0

    def _get_mem_info(self):
        """Read /proc/meminfo for RAM stats."""
        mem = {'total': 0, 'available': 0}
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        mem['total'] = int(line.split()[1])
                    elif line.startswith('MemAvailable:'):
                        mem['available'] = int(line.split()[1])
        except (OSError, ValueError, IndexError):
            pass
        return mem

    def _update_stats(self):
        """Calculate current CPU usage since last call and update RAM."""
        new_idle, new_total = self._get_cpu_times()
        old_idle, old_total = self.last_cpu_times
        
        diff_idle = new_idle - old_idle
        diff_total = new_total - old_total
        
        if diff_total > 0:
            usage = 100.0 * (1.0 - diff_idle / diff_total)
            self.cpu_history.append(usage)
        
        self.last_cpu_times = (new_idle, new_total)
        self.mem_info = self._get_mem_info()

    def draw(self, stdscr):
        if not self.visible:
            return

        # Update stats if interval passed
        now = time.time()
        if now - self.last_update > self.update_interval:
            self._update_stats()
            self.last_update = now

        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        
        # Clear background
        for i in range(bh):
            safe_addstr(stdscr, by + i, bx, ' ' * bw, body_attr)

        y = by
        # CPU Section
        cpu_usage = self.cpu_history[-1]
        safe_addstr(stdscr, y, bx + 1, f"CPU Usage: {cpu_usage:5.1f}%", body_attr | curses.A_BOLD)
        y += 1
        
        # CPU Graph (Bar chart using history)
        graph_h = 6
        graph_w = min(len(self.cpu_history), bw - 4)
        for i in range(graph_h):
            threshold = (graph_h - i) * (100 / graph_h)
            line = ""
            for val in list(self.cpu_history)[-graph_w:]:
                if val >= threshold:
                    line += "█"
                elif val >= threshold - (100/graph_h/2):
                    line += "▄"
                else:
                    line += " "
            safe_addstr(stdscr, y + i, bx + 2, line, body_attr)
        
        y += graph_h + 1
        
        # Memory Section
        total = self.mem_info.get('total', 0)
        available = self.mem_info.get('available', 0)
        used = total - available
        usage_pct = (used / total * 100) if total > 0 else 0
        
        safe_addstr(stdscr, y, bx + 1, f"RAM: {used//1024}/{total//1024} MB ({usage_pct:.1f}%)", body_attr | curses.A_BOLD)
        y += 1
        
        # RAM Bar
        bar_w = bw - 4
        filled = int(usage_pct / 100 * bar_w)
        bar = "█" * filled + "░" * (bar_w - filled)
        safe_addstr(stdscr, y, bx + 2, f"[{bar}]", body_attr)
        y += 2
        
        # System Info
        try:
            load = os.getloadavg()
            safe_addstr(stdscr, y, bx + 1, f"Load: {load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}", body_attr)
        except (AttributeError, OSError):
            pass
        y += 1
        
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_sec = float(f.readline().split()[0])
                hours = int(uptime_sec // 3600)
                minutes = int((uptime_sec % 3600) // 60)
                safe_addstr(stdscr, y, bx + 1, f"Uptime: {hours}h {minutes}m", body_attr)
        except (OSError, ValueError, IndexError):
            pass

    def handle_key(self, key):
        # Refresh on space
        if key in (ord(' '), 10, 13):
            self._update_stats()
            return None
        return super().handle_key(key)

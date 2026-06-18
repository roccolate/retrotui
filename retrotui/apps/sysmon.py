"""System Monitor application for RetroTUI."""
import os
import sys
import time
from collections import deque

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr

_PROC_AVAILABLE = sys.platform.startswith("linux") and os.path.isdir("/proc")


class SystemMonitorWindow(Window):
    """Real-time system resource monitor with ASCII graphs."""

    def __init__(self, x, y, w, h):
        super().__init__('System Monitor', x, y, w, h)
        self.cpu_history = deque([0] * 30, maxlen=30)
        self.last_cpu_times = self._get_cpu_times()
        self.mem_info = {'total': 0, 'available': 0}
        # Cached uptime string refreshed by `_update_stats` so the render
        # path does not reopen `/proc/uptime` on every frame.
        self.uptime_str = "-"
        self.platform_supported = _PROC_AVAILABLE
        if self.platform_supported:
            self._update_stats()
        self.last_update = time.time()
        self.update_interval = 1.0

    def _get_cpu_times(self):
        """Read /proc/stat to get total and idle CPU times."""
        if not _PROC_AVAILABLE:
            return 0, 0
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
                if line.startswith('cpu '):
                    parts = [float(x) for x in line.split()[1:]]
                    idle = parts[3]  # idle
                    total = sum(parts)
                    return idle, total
        except (OSError, ValueError, IndexError):
            pass
        return 0, 0

    def _get_mem_info(self):
        """Read /proc/meminfo for RAM stats."""
        mem = {'total': 0, 'available': 0}
        if not _PROC_AVAILABLE:
            return mem
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

    def _read_uptime(self):
        """Return uptime in seconds from /proc/uptime, or None if unavailable."""
        if not _PROC_AVAILABLE:
            return None
        try:
            with open('/proc/uptime', 'r') as f:
                return float(f.readline().split()[0])
        except (OSError, ValueError, IndexError):
            return None

    def _format_uptime(self, seconds):
        """Format a duration in seconds as ``Xh YYm`` (days if >= 24h)."""
        total = max(0, int(seconds))
        hours, rem = divmod(total, 3600)
        minutes = rem // 60
        return f"{hours}h {minutes:02d}m"

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
        uptime_sec = self._read_uptime()
        self.uptime_str = self._format_uptime(uptime_sec) if uptime_sec is not None else "-"
        self._resize_history_to_viewport()

    def _resize_history_to_viewport(self):
        """Resize the CPU history deque so its width matches the current graph."""
        _, _, bw, _ = self.body_rect()
        target_w = max(8, min(len(self.cpu_history), bw - 4))
        if target_w == self.cpu_history.maxlen:
            return
        if target_w <= 0:
            return
        if target_w > len(self.cpu_history):
            # Pad with leading zeros so the graph keeps its shape.
            padded = [0] * (target_w - len(self.cpu_history)) + list(self.cpu_history)
            self.cpu_history = deque(padded, maxlen=target_w)
            return
        self.cpu_history = deque(list(self.cpu_history)[-target_w:], maxlen=target_w)

    def tick(self):
        """Refresh stats outside the render path."""
        self._resize_history_to_viewport()
        now = time.time()
        if (now - self.last_update) <= self.update_interval:
            return False
        self._update_stats()
        self.last_update = now
        return True

    def draw(self, stdscr):
        if not self.visible:
            return

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
        if self.platform_supported:
            try:
                load = os.getloadavg()
                safe_addstr(stdscr, y, bx + 1, f"Load: {load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}", body_attr)
            except (AttributeError, OSError):
                pass
            y += 1

            # Uptime is cached by `_update_stats` and refreshed on the same
            # 1-second cadence as CPU/RAM, so the draw path is read-free.
            safe_addstr(stdscr, y, bx + 1, f"Uptime: {self.uptime_str}", body_attr)
        else:
            safe_addstr(
                stdscr,
                y,
                bx + 1,
                "System stats unavailable on this platform.",
                body_attr,
            )

    def handle_key(self, key):
        # Refresh on space
        if key in (ord(' '), 10, 13):
            self._update_stats()
            return None
        return super().handle_key(key)

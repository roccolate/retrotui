"""Network Monitor plugin (example)."""
import time
import os
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


def _parse_proc_net_dev():
    data = {}
    try:
        with open('/proc/net/dev', 'r', encoding='utf-8') as f:
            lines = f.readlines()[2:]
        for line in lines:
            if ':' not in line:
                continue
            iface, rest = line.split(':', 1)
            parts = rest.split()
            rx = int(parts[0])
            tx = int(parts[8])
            data[iface.strip()] = (rx, tx)
    except Exception:
        pass
    return data


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last = _parse_proc_net_dev()
        self.last_ts = time.time()

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        cur = _parse_proc_net_dev()
        now = time.time()
        dt = max(1e-6, now - self.last_ts)
        lines = []
        for iface, (rx, tx) in cur.items():
            lrx, ltx = self.last.get(iface, (0, 0))
            rx_rate = (rx - lrx) / dt
            tx_rate = (tx - ltx) / dt
            lines.append((iface, rx_rate, tx_rate))

        for i, (iface, rxr, txr) in enumerate(lines[:h]):
            line = f"{iface:10} RX: {int(rxr):8d} B/s TX: {int(txr):8d} B/s"
            safe_addstr(stdscr, y + i, x, line[:w], attr)

        # store
        self.last = cur
        self.last_ts = now

    def handle_key(self, key):
        if key == ord('r'):
            self.last = _parse_proc_net_dev()
            self.last_ts = time.time()

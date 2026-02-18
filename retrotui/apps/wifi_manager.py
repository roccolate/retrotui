"""WiFi Manager window (minimal, graceful fallback if nmcli missing)."""
from __future__ import annotations

import shutil
import subprocess

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr


class WifiManagerWindow(Window):
    def __init__(self, x, y, w, h):
        super().__init__("WiFi Manager", x, y, max(50, w), max(12, h), content=[], resizable=False)
        self.networks = []
        self.connected = None
        self.nmcli = shutil.which("nmcli")

    def refresh(self):
        self.networks = []
        if not self.nmcli:
            return
        try:
            result = subprocess.run([self.nmcli, "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "dev", "wifi"],
                                    text=True, capture_output=True, check=False)
            if result.returncode != 0:
                return
            for line in result.stdout.splitlines():
                parts = line.split(":")
                if not parts:
                    continue
                ssid = parts[0]
                signal = parts[1] if len(parts) > 1 else "0"
                sec = parts[2] if len(parts) > 2 else ""
                inuse = parts[3] if len(parts) > 3 else ""
                self.networks.append({"ssid": ssid, "signal": signal, "sec": sec, "inuse": inuse})
        except OSError:
            self.nmcli = None

    def draw(self, stdscr):
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        if not self.nmcli:
            safe_addstr(stdscr, by, bx, "nmcli no disponible", body_attr)
            return
        # Ensure we have a fresh list
        if not self.networks:
            self.refresh()
        for i, net in enumerate(self.networks[: bh]):
            label = f"{net.get('ssid')[:20]:20} {net.get('signal'):>3}% {net.get('sec') or 'OPEN'}"
            safe_addstr(stdscr, by + i, bx, label[:bw], body_attr)

    def handle_click(self, mx, my, bstate=None):
        bx, by, bw, bh = self.body_rect()
        if not (by <= my < by + bh):
            return None
        idx = my - by
        if idx < 0 or idx >= len(self.networks):
            return None
        net = self.networks[idx]
        # For tests, attempt to connect without a password (will likely fail gracefully)
        if not self.nmcli:
            return None
        try:
            subprocess.run([self.nmcli, "dev", "wifi", "connect", net.get('ssid')], check=False)
        except OSError:
            pass
        return None

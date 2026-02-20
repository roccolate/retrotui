"""WiFi Manager window inspired by tui-network."""
from __future__ import annotations

import curses
import shutil
import subprocess
import time

from ..ui.window import Window
from ..ui.dialog import InputDialog
from ..utils import safe_addstr, theme_attr, draw_box


class WifiManagerWindow(Window):
    def __init__(self, x, y, w, h):
        super().__init__("WiFi Manager", x, y, max(50, w), max(15, h), content=[], resizable=False)
        self.networks = []
        self.selected_idx = 0
        self.scroll_offset = 0
        self.nmcli = shutil.which("nmcli")
        
        self.radio_on = True
        self._check_radio_state()
        
        self._dialog = None
        self._connecting_ssid = None
        self._status_msg = ""
        
        if self.nmcli and self.radio_on:
            self.refresh()

    def _check_radio_state(self):
        if not self.nmcli: return
        try:
            res = subprocess.run([self.nmcli, "radio", "wifi"], capture_output=True, text=True)
            self.radio_on = "enabled" in res.stdout.strip().lower()
        except OSError:
            pass

    def _toggle_radio(self):
        if not self.nmcli: return
        target = "off" if self.radio_on else "on"
        try:
            subprocess.run([self.nmcli, "radio", "wifi", target], check=False)
            self.radio_on = (target == "on")
            if self.radio_on:
                self.refresh()
            else:
                self.networks.clear()
        except OSError:
            pass

    def refresh(self):
        if not self.nmcli or not self.radio_on:
            return
        
        self._status_msg = "Rescanning..."
        try:
            # Tell nmcli to rescan (returns immediately usually)
            subprocess.run([self.nmcli, "dev", "wifi", "rescan"], check=False)
            # Sleep briefly to let it populate
            time.sleep(1)
            
            result = subprocess.run([self.nmcli, "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE,BSSID", "dev", "wifi"],
                                    text=True, capture_output=True, check=False)
            
            new_networks = []
            seen_ssids = set()
            
            for line in result.stdout.splitlines():
                parts = line.split(":", 4)
                if len(parts) < 4: continue
                
                ssid = parts[0].strip()
                if ssid.startswith('"') and ssid.endswith('"'): ssid = ssid[1:-1]
                if not ssid: continue
                
                signal = parts[1].strip() if parts[1] else "0"
                sec = parts[2].strip()
                inuse = parts[3].strip() == "*"
                bssid = parts[4].strip() if len(parts) > 4 else ""
                
                # Combine duplicates by prioritizing the strongest signal or in-use
                if ssid in seen_ssids and not inuse:
                    continue
                seen_ssids.add(ssid)
                
                new_networks.append({
                    "ssid": ssid, 
                    "signal": int(signal), 
                    "sec": sec, 
                    "inuse": inuse,
                    "bssid": bssid
                })
                
            self.networks = sorted(new_networks, key=lambda n: (not n["inuse"], -n["signal"]))
            self._status_msg = "Scan complete."
            
            if self.selected_idx >= len(self.networks):
                self.selected_idx = max(0, len(self.networks) - 1)
        except OSError:
            self._status_msg = "Scan failed."

    def _signal_bars(self, signal: int) -> str:
        if signal >= 80: return "[||||]"
        if signal >= 60: return "[||| ]"
        if signal >= 40: return "[||  ]"
        if signal >= 20: return "[|   ]"
        return "[    ]"

    def draw(self, stdscr):
        if not self.visible: return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        
        # Clear body
        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, " " * bw, body_attr)
            
        if getattr(self, '_fetch_error', False):
            safe_addstr(stdscr, by + 2, bx + 2, "Error: 'nmcli' could not be found.", theme_attr('window_body') | curses.A_BOLD)
            return
            
        header_attr = theme_attr('title_bar') | curses.A_BOLD
        safe_addstr(stdscr, by, bx, " " * bw, header_attr)
        
        state_str = "RADIO: ON" if self.radio_on else "RADIO: OFF"
        safe_addstr(stdscr, by, bx + 1, f" {state_str} | [Ctrl+1] Toggle | [Ctrl+R] Rescan | {self._status_msg} ", header_attr)
        
        if not self.radio_on:
            safe_addstr(stdscr, by + 4, bx + 4, "WiFi Radio is currently DISABLED.", body_attr)
            safe_addstr(stdscr, by + 5, bx + 4, "Press Ctrl+1 to turn it ON.", body_attr)
        elif not self.networks:
             safe_addstr(stdscr, by + 4, bx + 4, "No networks found. Press Ctrl+R to rescan.", body_attr)
        else:
            list_y = by + 2
            list_h = bh - 2
            
            if self.selected_idx < self.scroll_offset:
                self.scroll_offset = self.selected_idx
            elif self.selected_idx >= self.scroll_offset + list_h:
                self.scroll_offset = self.selected_idx - list_h + 1
                
            for i in range(list_h):
                idx = self.scroll_offset + i
                if idx >= len(self.networks): break
                
                net = self.networks[idx]
                y = list_y + i
                
                is_sel = (idx == self.selected_idx)
                attr = theme_attr('menu_selected') if is_sel else body_attr
                
                safe_addstr(stdscr, y, bx, " " * bw, attr)
                
                bars = self._signal_bars(net["signal"])
                lock = "🔒" if net["sec"] and net["sec"] != "--" else "  "
                conn = "✔ CONNECTED" if net["inuse"] else ""
                if self._connecting_ssid == net["ssid"]:
                    conn = "...CONNECTING"
                
                # Format:  [||||] 🔒 My_WiFi_Network        ✔ CONNECTED
                ssid_disp = net["ssid"][:bw - 35]
                row_text = f" {bars} {lock} {ssid_disp:<25} {conn}"
                
                if net["inuse"]:
                    attr |= curses.A_BOLD | curses.color_pair(2) # Green text for active
                    
                safe_addstr(stdscr, y, bx + 1, row_text, attr)
                
        # Draw dialog on top if present
        if self._dialog:
            self._dialog.draw(stdscr)

    def _initiate_connection(self, net):
        self._connecting_ssid = net["ssid"]
        self._status_msg = f"Connecting to {net['ssid']}..."
        
        if not net["sec"] or net["sec"] == "--":
            # Open network
            self._execute_nmcli_connect(net["ssid"], None)
        else:
            # Secure, prompt password
            self._dialog = InputDialog("Wi-Fi Password", f"Enter password for {net['ssid']}:", width=40)

    def _execute_nmcli_connect(self, ssid, password):
        cmd = [self.nmcli, "dev", "wifi", "connect", ssid]
        if password:
            cmd.extend(["password", password])
        
        # Run blocking for now; nmcli connects synchronously
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                self._status_msg = f"Connected to {ssid}."
            else:
                self._status_msg = "Connection failed."
        except OSError:
            self._status_msg = "Execution failed."
            
        self._connecting_ssid = None
        self.refresh()

    def handle_click(self, mx, my, bstate=None):
        if self._dialog:
            res = self._dialog.handle_click(mx, my)
            if res != -1:
                if res == 0: # OK
                    self._execute_nmcli_connect(self._connecting_ssid, self._dialog.value)
                else: # Cancel
                    self._connecting_ssid = None
                    self._status_msg = "Connection cancelled."
                self._dialog = None
            return None

        bx, by, bw, bh = self.body_rect()
        list_y = by + 2
        list_h = bh - 2
        
        if list_y <= my < list_y + list_h and bx <= mx < bx + bw:
            clicked_idx = self.scroll_offset + (my - list_y)
            if 0 <= clicked_idx < len(self.networks):
                if self.selected_idx == clicked_idx:
                    # Double click equivalent -> connect
                    self._initiate_connection(self.networks[clicked_idx])
                else:
                    self.selected_idx = clicked_idx
        return None

    def handle_key(self, key):
        if self._dialog:
            res = self._dialog.handle_key(key)
            if res != -1:
                if res == 0:
                    self._execute_nmcli_connect(self._connecting_ssid, self._dialog.value)
                else:
                    self._connecting_ssid = None
                    self._status_msg = "Connection cancelled."
                self._dialog = None
            return None

        from ..core.key_router import normalize_key_code
        kc = normalize_key_code(key)

        if kc == 18:       # Ctrl+R
            self.refresh()
        elif kc == 1:      # Ctrl+1
            self._toggle_radio()
        elif kc == curses.KEY_UP:
            self.selected_idx = max(0, self.selected_idx - 1)
        elif kc == curses.KEY_DOWN:
            if self.networks:
                self.selected_idx = min(len(self.networks) - 1, self.selected_idx + 1)
        elif kc in (curses.KEY_ENTER, 10, 13):
            if self.networks and 0 <= self.selected_idx < len(self.networks):
                self._initiate_connection(self.networks[self.selected_idx])
        
        return None


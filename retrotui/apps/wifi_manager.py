"""WiFi Manager window inspired by tui-network."""
from __future__ import annotations

import curses
import shutil
import subprocess
import threading

from ..core.key_router import normalize_key_code
from ..ui.window import Window
from ..ui.dialog import InputDialog
from ..utils import safe_addstr, theme_attr

NMCLI_QUICK_TIMEOUT = 5.0
NMCLI_SCAN_TIMEOUT = 15.0
NMCLI_CONNECT_TIMEOUT = 45.0


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

        # Background-scan state.
        self._scan_lock = threading.Lock()
        self._scan_thread = None
        self._scan_in_progress = False
        self._scan_error = None
        self._scan_result_ready = False
        # Background-connect state.
        self._connect_lock = threading.Lock()
        self._connect_thread = None
        self._connect_in_progress = False
        self._connect_result = None

        if self.nmcli and self.radio_on:
            self.refresh()

    def _check_radio_state(self):
        if not self.nmcli: return
        try:
            res = subprocess.run(
                [self.nmcli, "radio", "wifi"],
                capture_output=True,
                text=True,
                check=False,
                timeout=NMCLI_QUICK_TIMEOUT,
            )
            self.radio_on = "enabled" in res.stdout.strip().lower()
        except (OSError, subprocess.SubprocessError):
            pass

    def _toggle_radio(self):
        if not self.nmcli: return
        target = "off" if self.radio_on else "on"
        try:
            subprocess.run(
                [self.nmcli, "radio", "wifi", target],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=NMCLI_QUICK_TIMEOUT,
            )
            self.radio_on = (target == "on")
            if self.radio_on:
                self.refresh()
            else:
                self.networks.clear()
        except (OSError, subprocess.SubprocessError):
            pass

    def refresh(self):
        if not self.nmcli or not self.radio_on:
            return
        with self._scan_lock:
            if self._scan_in_progress:
                return
            self._scan_in_progress = True
            self._scan_error = None
            self._scan_result_ready = False
        self._status_msg = "Rescanning..."
        thread = threading.Thread(target=self._scan_worker, daemon=True)
        self._scan_thread = thread
        thread.start()

    @staticmethod
    def _split_nmcli_fields(line, expected=5):
        """Split an `nmcli -t` line on unescaped ``:`` separators.

        ``nmcli`` escapes literal colons inside a field as ``\\:``. The
        default ``str.split(":")`` does not honour this and corrupts
        SSIDs that contain colons. We split on unescaped colons here so
        the field boundaries line up with the requested column order.
        """
        fields = []
        current = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\" and i + 1 < len(line) and line[i + 1] == ":":
                # Escaped colon belongs to the current field.
                current.append(":")
                i += 2
                continue
            if ch == ":" and len(fields) < expected - 1:
                fields.append("".join(current))
                current = []
                i += 1
                continue
            current.append(ch)
            i += 1
        fields.append("".join(current))
        return fields

    def _scan_worker(self):
        new_networks = []
        error_message = None
        try:
            subprocess.run(
                [self.nmcli, "dev", "wifi", "rescan"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=NMCLI_SCAN_TIMEOUT,
            )
            result = subprocess.run(
                [self.nmcli, "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE,BSSID", "dev", "wifi"],
                text=True,
                capture_output=True,
                check=False,
                timeout=NMCLI_SCAN_TIMEOUT,
            )
            seen_ssids = set()
            for line in result.stdout.splitlines():
                parts = self._split_nmcli_fields(line, expected=5)
                if len(parts) < 4:
                    continue
                ssid = parts[0].strip()
                if ssid.startswith('"') and ssid.endswith('"'):
                    ssid = ssid[1:-1]
                if not ssid:
                    continue
                signal = parts[1].strip() if parts[1] else "0"
                sec = parts[2].strip()
                inuse = parts[3].strip() == "*"
                bssid = parts[4].strip() if len(parts) > 4 else ""
                try:
                    signal_strength = int(signal)
                except ValueError:
                    signal_strength = 0

                if ssid in seen_ssids and not inuse:
                    continue
                seen_ssids.add(ssid)
                new_networks.append({
                    "ssid": ssid,
                    "signal": signal_strength,
                    "sec": sec,
                    "inuse": inuse,
                    "bssid": bssid,
                })
        except (OSError, subprocess.SubprocessError) as exc:
            error_message = str(exc) or "Scan failed."

        with self._scan_lock:
            self._scan_in_progress = False
            if error_message is not None:
                self._scan_error = error_message
                self._status_msg = "Scan failed."
            else:
                self.networks = sorted(new_networks, key=lambda n: (not n["inuse"], -n["signal"]))
                self._status_msg = "Scan complete."
                if self.selected_idx >= len(self.networks):
                    self.selected_idx = max(0, len(self.networks) - 1)
            self._scan_result_ready = True

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

        if not self.nmcli:
            safe_addstr(stdscr, by + 2, bx + 2, "Error: 'nmcli' could not be found.", theme_attr('window_body') | curses.A_BOLD)
            return

        header_attr = theme_attr('window_title') | curses.A_BOLD
        safe_addstr(stdscr, by, bx, " " * bw, header_attr)

        with self._scan_lock:
            scanning = self._scan_in_progress
        with self._connect_lock:
            connecting = self._connect_in_progress
            connecting_ssid = self._connecting_ssid
        state_str = "RADIO: ON" if self.radio_on else "RADIO: OFF"
        if connecting and connecting_ssid:
            status_msg = f"Connecting to {connecting_ssid}..."
        elif scanning:
            status_msg = f"{self._status_msg}"
        else:
            status_msg = self._status_msg
        safe_addstr(stdscr, by, bx + 1, f" {state_str} | [Ctrl+R] Rescan | {status_msg} ", header_attr)

        if not self.radio_on:
            safe_addstr(stdscr, by + 4, bx + 4, "WiFi Radio is currently DISABLED.", body_attr)
            safe_addstr(stdscr, by + 5, bx + 4, "Press Ctrl+1 to turn it ON.", body_attr)
        elif scanning and not self.networks:
            safe_addstr(stdscr, by + 4, bx + 4, "Scanning for networks...", body_attr)
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
                if connecting_ssid and net["ssid"] == connecting_ssid:
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
            self._start_connect(net["ssid"], None)
        else:
            # Secure, prompt password
            self._dialog = InputDialog("Wi-Fi Password", f"Enter password for {net['ssid']}:", width=40)

    def _start_connect(self, ssid, password):
        with self._connect_lock:
            if self._connect_in_progress:
                return
            self._connect_in_progress = True
            self._connect_result = None
        self._connecting_ssid = ssid
        self._status_msg = f"Connecting to {ssid}..."
        thread = threading.Thread(
            target=self._connect_worker,
            args=(ssid, password),
            daemon=True,
        )
        self._connect_thread = thread
        thread.start()

    def _finish_connect(self, success, error_message):
        with self._connect_lock:
            self._connect_in_progress = False
            self._connect_result = (success, error_message)
            self._connecting_ssid = None
        if success:
            self.refresh()

    def _connect_worker(self, ssid, password):
        cmd = [self.nmcli, "dev", "wifi", "connect", ssid]
        if password:
            # Prefer stdin (--ask) so the password does not appear in process listings.
            error_message = ""
            try:
                res = subprocess.run(
                    [self.nmcli, "--ask", "dev", "wifi", "connect", ssid],
                    input=password + "\n",
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=NMCLI_CONNECT_TIMEOUT,
                )
                success = res.returncode == 0
                if not success:
                    error_message = (res.stderr or res.stdout or "").strip() or "Connection failed."
                self._finish_connect(success, error_message)
                return
            except subprocess.TimeoutExpired:
                self._finish_connect(False, "Connection timed out.")
                return
            except OSError:
                pass
            cmd.extend(["password", password])
        success = False
        error_message = ""
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=NMCLI_CONNECT_TIMEOUT,
            )
            success = res.returncode == 0
            if not success:
                error_message = (res.stderr or res.stdout or "").strip() or "Connection failed."
        except subprocess.TimeoutExpired:
            error_message = "Connection timed out."
        except OSError as exc:
            error_message = str(exc) or "Execution failed."
        self._finish_connect(success, error_message)

    def tick(self):
        """Apply background scan/connect results outside the render path."""
        changed = False
        with self._scan_lock:
            if self._scan_error is not None:
                self._scan_error = None
                changed = True
            if self._scan_result_ready:
                self._scan_result_ready = False
                changed = True
        with self._connect_lock:
            result = self._connect_result
            if result is not None:
                self._connect_result = None
                success, error_message = result
                self._status_msg = f"Connected to {self._status_msg[12:]}." if success and self._status_msg.startswith("Connecting to ") else ("Connection failed." if not success else self._status_msg)
                if not success and error_message:
                    self._status_msg = f"Connection failed: {error_message[:60]}"
                changed = True
        return changed

    def handle_click(self, mx, my, bstate=None):
        if self._dialog:
            res = self._dialog.handle_click(mx, my)
            if res != -1:
                if res == 0: # OK
                    self._start_connect(self._connecting_ssid, self._dialog.value)
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
                    self._start_connect(self._connecting_ssid, self._dialog.value)
                else:
                    self._connecting_ssid = None
                    self._status_msg = "Connection cancelled."
                self._dialog = None
            return None

        kc = normalize_key_code(key)

        if kc == 18:       # Ctrl+R
            self.refresh()
        elif kc == 1:      # Ctrl+1 (legacy keycode; document that it overlaps with Ctrl+A)
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

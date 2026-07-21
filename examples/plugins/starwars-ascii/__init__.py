"""Star Wars ASCII plugin for RetroTUI.

Streams the classic ASCII Star Wars animation from telnet-compatible
servers and renders it inside a plugin window.
"""

from __future__ import annotations

import socket
import threading
import time

from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    """Render the classic ASCII movie stream inside RetroTUI."""

    @property
    def wants_periodic_tick(self):
        thread = getattr(self, "_worker_thread", None)
        return thread is not None and thread.is_alive()

    HOSTS = (
        ("starwarstel.net", 23),
        ("towel.blinkenlights.nl", 23),
    )
    CONNECT_TIMEOUT_SECONDS = 6.0
    SOCKET_TIMEOUT_SECONDS = 1.0
    RECONNECT_DELAY_SECONDS = 5.0
    CANVAS_WIDTH = 120
    CANVAS_HEIGHT = 48
    MAX_ANSI_SEQ_LEN = 32

    TELNET_IAC = 255
    TELNET_DONT = 254
    TELNET_DO = 253
    TELNET_WONT = 252
    TELNET_WILL = 251
    TELNET_SB = 250
    TELNET_SE = 240

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.Lock()
        self._canvas = [list(" " * self.CANVAS_WIDTH) for _ in range(self.CANVAS_HEIGHT)]
        self._cursor_x = 0
        self._cursor_y = 0
        self._saved_cursor = (0, 0)
        self._status = "Connecting..."
        self._socket = None
        self._worker_thread = None
        self._worker_stop = threading.Event()

        # Telnet parser state
        self._telnet_in_iac = False
        self._telnet_need_option = False
        self._telnet_in_subnegotiation = False
        self._telnet_subnegotiation_iac = False

        # ANSI parser state
        self._ansi_sequence = None

        self._start_worker()

    def close(self):
        self._stop_worker()

    def _set_status(self, text):
        with self._lock:
            self._status = str(text)

    def _start_worker(self):
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._worker_stop = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._stream_worker,
            name="starwars-ascii-stream",
            daemon=True,
        )
        self._worker_thread.start()

    def _stop_worker(self):
        stop = self._worker_stop
        stop.set()
        sock = self._socket
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        thread = self._worker_thread
        if thread and thread.is_alive():
            thread.join(timeout=1.5)
        self._socket = None
        self._worker_thread = None

    def _restart_worker(self):
        self._stop_worker()
        with self._lock:
            self._clear_canvas_locked()
        self._set_status("Reconnecting...")
        self._start_worker()

    def _sleep_with_stop(self, seconds):
        deadline = time.time() + max(0.0, seconds)
        while time.time() < deadline:
            if self._worker_stop.is_set():
                return
            time.sleep(0.1)

    def _stream_worker(self):
        while not self._worker_stop.is_set():
            last_error = None
            connected = False
            for host, port in self.HOSTS:
                if self._worker_stop.is_set():
                    break
                self._set_status(f"Connecting to {host}:{port} ...")
                sock = None
                try:
                    sock = socket.create_connection(
                        (host, port), timeout=self.CONNECT_TIMEOUT_SECONDS
                    )
                    sock.settimeout(self.SOCKET_TIMEOUT_SECONDS)
                except OSError as exc:
                    last_error = f"{host}:{port} ({exc})"
                    if sock is not None:
                        try:
                            sock.close()
                        except OSError:
                            pass
                    continue

                connected = True
                self._socket = sock
                self._set_status(f"Connected to {host}:{port}  |  R reconnect  C clear")
                try:
                    while not self._worker_stop.is_set():
                        try:
                            data = sock.recv(4096)
                        except socket.timeout:
                            continue
                        except OSError as exc:
                            last_error = f"Read error on {host}:{port} ({exc})"
                            break
                        if not data:
                            last_error = f"Connection closed by {host}:{port}"
                            break
                        self._feed_bytes(data)
                finally:
                    self._socket = None
                    try:
                        sock.close()
                    except OSError:
                        pass

                if self._worker_stop.is_set():
                    break

            if self._worker_stop.is_set():
                break

            if connected:
                self._set_status("Disconnected. Reconnecting in 5s...")
            elif last_error:
                self._set_status(f"No server reachable: {last_error}. Retry in 5s...")
            else:
                self._set_status("No server reachable. Retry in 5s...")
            self._sleep_with_stop(self.RECONNECT_DELAY_SECONDS)

    def _feed_bytes(self, data):
        for value in data:
            if self._consume_telnet_byte(value):
                continue
            self._consume_terminal_byte(value)

    def _consume_telnet_byte(self, value):
        if self._telnet_in_subnegotiation:
            if self._telnet_subnegotiation_iac:
                if value == self.TELNET_SE:
                    self._telnet_in_subnegotiation = False
                self._telnet_subnegotiation_iac = False
                return True
            if value == self.TELNET_IAC:
                self._telnet_subnegotiation_iac = True
            return True

        if self._telnet_need_option:
            self._telnet_need_option = False
            self._telnet_in_iac = False
            return True

        if self._telnet_in_iac:
            if value in (
                self.TELNET_DO,
                self.TELNET_DONT,
                self.TELNET_WILL,
                self.TELNET_WONT,
            ):
                self._telnet_need_option = True
                return True
            if value == self.TELNET_SB:
                self._telnet_in_subnegotiation = True
                self._telnet_subnegotiation_iac = False
                self._telnet_in_iac = False
                return True
            self._telnet_in_iac = False
            return True

        if value == self.TELNET_IAC:
            self._telnet_in_iac = True
            return True
        return False

    def _consume_terminal_byte(self, value):
        if self._ansi_sequence is not None:
            self._ansi_sequence.append(value)
            if self._is_ansi_final_byte(value):
                seq = bytes(self._ansi_sequence).decode("latin-1", errors="ignore")
                self._ansi_sequence = None
                self._handle_ansi_escape(seq)
            elif len(self._ansi_sequence) > self.MAX_ANSI_SEQ_LEN:
                self._ansi_sequence = None
            return

        if value == 0x1B:
            self._ansi_sequence = bytearray([value])
            return

        with self._lock:
            self._write_byte_locked(value)

    @staticmethod
    def _is_ansi_final_byte(value):
        return 0x40 <= value <= 0x7E

    def _parse_csi_numbers(self, raw, default=1):
        if not raw:
            return [default]
        if raw.startswith("?"):
            raw = raw[1:]
        parts = raw.split(";")
        values = []
        for part in parts:
            if not part:
                values.append(default)
                continue
            try:
                values.append(int(part))
            except ValueError:
                values.append(default)
        return values or [default]

    def _handle_ansi_escape(self, seq):
        if not seq.startswith("\x1b["):
            return
        body = seq[2:]
        if not body:
            return

        final = body[-1]
        params = body[:-1]

        with self._lock:
            if final in ("H", "f"):
                values = self._parse_csi_numbers(params, default=1)
                row = max(1, values[0])
                col = max(1, values[1] if len(values) > 1 else 1)
                self._cursor_y = min(self.CANVAS_HEIGHT - 1, row - 1)
                self._cursor_x = min(self.CANVAS_WIDTH - 1, col - 1)
                return

            if final == "J":
                mode = self._parse_csi_numbers(params, default=0)[0]
                if mode in (2, 3):
                    self._clear_canvas_locked()
                    self._cursor_x = 0
                    self._cursor_y = 0
                elif mode == 0:
                    self._clear_to_screen_end_locked()
                elif mode == 1:
                    self._clear_to_screen_start_locked()
                return

            if final == "K":
                mode = self._parse_csi_numbers(params, default=0)[0]
                row = self._canvas[self._cursor_y]
                if mode == 0:
                    start, end = self._cursor_x, self.CANVAS_WIDTH
                elif mode == 1:
                    start, end = 0, self._cursor_x + 1
                else:
                    start, end = 0, self.CANVAS_WIDTH
                for idx in range(start, min(end, self.CANVAS_WIDTH)):
                    row[idx] = " "
                return

            if final == "A":
                step = max(1, self._parse_csi_numbers(params, default=1)[0])
                self._cursor_y = max(0, self._cursor_y - step)
                return
            if final == "B":
                step = max(1, self._parse_csi_numbers(params, default=1)[0])
                self._cursor_y = min(self.CANVAS_HEIGHT - 1, self._cursor_y + step)
                return
            if final == "C":
                step = max(1, self._parse_csi_numbers(params, default=1)[0])
                self._cursor_x = min(self.CANVAS_WIDTH - 1, self._cursor_x + step)
                return
            if final == "D":
                step = max(1, self._parse_csi_numbers(params, default=1)[0])
                self._cursor_x = max(0, self._cursor_x - step)
                return

            if final == "s":
                self._saved_cursor = (self._cursor_x, self._cursor_y)
                return
            if final == "u":
                self._cursor_x, self._cursor_y = self._saved_cursor
                self._cursor_x = max(0, min(self.CANVAS_WIDTH - 1, self._cursor_x))
                self._cursor_y = max(0, min(self.CANVAS_HEIGHT - 1, self._cursor_y))
                return

    def _clear_canvas_locked(self):
        blank = list(" " * self.CANVAS_WIDTH)
        for idx in range(self.CANVAS_HEIGHT):
            self._canvas[idx] = blank.copy()
        self._cursor_x = 0
        self._cursor_y = 0
        self._saved_cursor = (0, 0)

    def _clear_to_screen_end_locked(self):
        row = self._canvas[self._cursor_y]
        for idx in range(self._cursor_x, self.CANVAS_WIDTH):
            row[idx] = " "
        for y in range(self._cursor_y + 1, self.CANVAS_HEIGHT):
            self._canvas[y] = list(" " * self.CANVAS_WIDTH)

    def _clear_to_screen_start_locked(self):
        row = self._canvas[self._cursor_y]
        for idx in range(0, self._cursor_x + 1):
            row[idx] = " "
        for y in range(0, self._cursor_y):
            self._canvas[y] = list(" " * self.CANVAS_WIDTH)

    def _scroll_if_needed_locked(self):
        while self._cursor_y >= self.CANVAS_HEIGHT:
            self._canvas.pop(0)
            self._canvas.append(list(" " * self.CANVAS_WIDTH))
            self._cursor_y -= 1

    def _write_byte_locked(self, value):
        if value == 0x0D:  # \r
            self._cursor_x = 0
            return
        if value == 0x0A:  # \n
            self._cursor_y += 1
            self._scroll_if_needed_locked()
            return
        if value == 0x08:  # \b
            self._cursor_x = max(0, self._cursor_x - 1)
            return
        if value == 0x09:  # \t
            next_tab = ((self._cursor_x // 8) + 1) * 8
            while self._cursor_x < min(next_tab, self.CANVAS_WIDTH):
                self._canvas[self._cursor_y][self._cursor_x] = " "
                self._cursor_x += 1
            if self._cursor_x >= self.CANVAS_WIDTH:
                self._cursor_x = 0
                self._cursor_y += 1
                self._scroll_if_needed_locked()
            return
        if value < 32 or value > 126:
            return

        self._canvas[self._cursor_y][self._cursor_x] = chr(value)
        self._cursor_x += 1
        if self._cursor_x >= self.CANVAS_WIDTH:
            self._cursor_x = 0
            self._cursor_y += 1
            self._scroll_if_needed_locked()

    @staticmethod
    def _normalize_key(key):
        if isinstance(key, int):
            return key
        if isinstance(key, str) and len(key) == 1:
            return ord(key)
        return None

    def handle_key(self, key):
        code = self._normalize_key(key)
        if code is None:
            return None
        if code in (ord("r"), ord("R")):
            self._restart_worker()
            return None
        if code in (ord("c"), ord("C")):
            with self._lock:
                self._clear_canvas_locked()
            self._set_status("Cleared. Streaming...")
            return None
        return None

    def draw_content(self, stdscr, x, y, w, h):
        body_attr = theme_attr("window_body")
        menu_attr = theme_attr("menubar")
        status_attr = theme_attr("status")

        if h <= 0 or w <= 0:
            return

        with self._lock:
            status = self._status
            lines = [
                "".join(row[:w]).ljust(w)[:w]
                for row in self._canvas[: max(0, h - 2)]
            ]

        safe_addstr(
            stdscr,
            y,
            x,
            (" Star Wars ASCII  |  R reconnect  C clear ".ljust(w))[:w],
            menu_attr,
        )
        if h > 1:
            safe_addstr(stdscr, y + 1, x, (f" {status} ".ljust(w))[:w], status_attr)

        movie_y = y + 2
        movie_h = max(0, h - 2)
        for row in range(movie_h):
            text = lines[row] if row < len(lines) else (" " * w)
            safe_addstr(stdscr, movie_y + row, x, text, body_attr)

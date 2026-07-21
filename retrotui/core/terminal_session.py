"""Minimal PTY-backed terminal session helper for v0.4."""

from __future__ import annotations

import codecs
import errno
import importlib
import os
import signal
import struct
import time

from .terminal_cells import (
    CONTINUATION_TEXT,
    codepoint_width,
    display_width,
    is_continuation,
    leading_cell_index,
    sanitize_row,
)

_BACKENDS_UNSET = object()
_BACKENDS_CACHE = {"value": _BACKENDS_UNSET}
_WIN_BACKEND_CACHE = {"value": _BACKENDS_UNSET}
_CLOSE_WAIT_SECONDS = 0.2
_CLOSE_POLL_INTERVAL = 0.01
_DEFAULT_READ_BUDGET = 8192
_DEFAULT_WRITE_BUDGET = 8192


class TerminalScreenBuffer:
    """2D grid of physical terminal cells with Unicode width semantics.

    Cells retain the legacy ``(text, attr)`` tuple contract. A wide glyph is
    stored in its leading cell and reserves the following physical column with
    ``("", attr)``. Combining marks and zero-width joiners are appended to the
    preceding leading cell without advancing the cursor.
    """

    __slots__ = (
        "rows",
        "cols",
        "_grid",
        "_cursor_row",
        "_cursor_col",
        "_default_attr",
        "_scroll_sink",
    )

    def __init__(self, rows, cols, default_attr=0):
        rows = max(1, int(rows))
        cols = max(1, int(cols))
        self.rows = rows
        self.cols = cols
        self._default_attr = int(default_attr)
        self._grid = [self._blank_row() for _ in range(rows)]
        self._cursor_row = 0
        self._cursor_col = 0
        self._scroll_sink = None

    def _blank_cell(self):
        return (" ", self._default_attr)

    def _blank_row(self):
        return [self._blank_cell() for _ in range(self.cols)]

    @property
    def cursor_row(self):
        return self._cursor_row

    @property
    def cursor_col(self):
        return self._cursor_col

    def set_cursor(self, row, col):
        """Move the cursor to a physical column clamped to the grid."""
        self._cursor_row = max(0, min(self.rows - 1, int(row)))
        self._cursor_col = max(0, min(self.cols - 1, int(col)))

    def get_cell(self, row, col):
        """Return the ``(text, attr)`` at ``(row, col)`` or a blank cell."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self._grid[row][col]
        return self._blank_cell()

    def get_row(self, row):
        """Return a copy of one physical row."""
        if 0 <= row < self.rows:
            return list(self._grid[row])
        return []

    def normalize_row(self, row):
        """Repair wide-cell invariants for one row after direct legacy edits."""
        if 0 <= row < self.rows:
            normalized = sanitize_row(self._grid[row], self._default_attr)
            if len(normalized) < self.cols:
                normalized.extend(self._blank_cell() for _ in range(self.cols - len(normalized)))
            self._grid[row] = normalized[:self.cols]

    def _glyph_bounds(self, row, col):
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return None
        line = self._grid[row]
        lead = leading_cell_index(line, col)
        if lead is None:
            return None
        width = display_width(line[lead][0])
        end = lead + (2 if width == 2 else 1)
        return lead, min(self.cols, end)

    def _clear_glyph_at(self, row, col):
        bounds = self._glyph_bounds(row, col)
        if bounds is None:
            return
        start, end = bounds
        for index in range(start, end):
            self._grid[row][index] = self._blank_cell()

    def _previous_leading_cell(self):
        if self._cursor_col > 0:
            col = min(self.cols - 1, self._cursor_col - 1)
            lead = leading_cell_index(self._grid[self._cursor_row], col)
            if lead is not None:
                return self._cursor_row, lead
        return None

    def _merge_with_previous(self, ch):
        previous = self._previous_leading_cell()
        if previous is None:
            return False
        row, lead = previous
        text, attr = self._grid[row][lead]
        if text == " ":
            return False

        old_width = display_width(text)
        merged = text + ch
        new_width = display_width(merged)
        if new_width < 0:
            return False
        if old_width < 1:
            old_width = 1
        if new_width < 1:
            new_width = old_width
        if new_width > 2:
            new_width = 2

        if new_width == 2 and lead + 1 >= self.cols:
            return False

        if old_width == 2 and new_width == 1 and lead + 1 < self.cols:
            self._grid[row][lead + 1] = self._blank_cell()
            if self._cursor_col > lead + 1:
                self._cursor_col -= 1
        elif old_width == 1 and new_width == 2:
            self._clear_glyph_at(row, lead + 1)
            self._grid[row][lead + 1] = (CONTINUATION_TEXT, attr)
            if self._cursor_col == lead + 1:
                self._cursor_col += 1

        self._grid[row][lead] = (merged, attr)
        if new_width == 2:
            self._grid[row][lead + 1] = (CONTINUATION_TEXT, attr)
        return True

    def put_char(self, ch, attr=None, *, autowrap=True):
        """Write one Unicode codepoint and advance by its display width."""
        if not ch:
            return
        attr = self._default_attr if attr is None else attr
        width = codepoint_width(ch)
        if width < 0:
            return

        previous = self._previous_leading_cell()
        previous_text = ""
        if previous is not None:
            previous_text = self._grid[previous[0]][previous[1]][0]
        if width == 0 or previous_text.endswith("\u200d"):
            if self._merge_with_previous(ch):
                return
            if width == 0:
                return

        width = 2 if width >= 2 else 1

        if self._cursor_col >= self.cols:
            if autowrap:
                self.line_feed()
                self._cursor_col = 0
            else:
                self._cursor_col = self.cols - 1

        if width == 2 and self.cols < 2:
            ch = "\ufffd"
            width = 1
        elif width == 2 and self._cursor_col == self.cols - 1:
            if autowrap:
                self.line_feed()
                self._cursor_col = 0
            else:
                ch = "\ufffd"
                width = 1

        row = self._cursor_row
        col = self._cursor_col
        self._clear_glyph_at(row, col)
        if width == 2:
            self._clear_glyph_at(row, col + 1)

        self._grid[row][col] = (ch, attr)
        if width == 2:
            self._grid[row][col + 1] = (CONTINUATION_TEXT, attr)

        if autowrap:
            self._cursor_col += width
        else:
            self._cursor_col = min(self.cols - 1, self._cursor_col + width)

    def carriage_return(self):
        self._cursor_col = 0

    def line_feed(self):
        if self._cursor_row >= self.rows - 1:
            self.scroll_up()
        else:
            self._cursor_row += 1

    def backspace(self):
        if self._cursor_col <= 0:
            return
        target = min(self.cols - 1, self._cursor_col - 1)
        lead = leading_cell_index(self._grid[self._cursor_row], target)
        self._cursor_col = target if lead is None else lead

    def clear_range(self, row, start, end):
        """Clear a half-open physical-column range without splitting glyphs."""
        if not 0 <= row < self.rows:
            return
        start = max(0, min(self.cols, int(start)))
        end = max(start, min(self.cols, int(end)))
        if start >= end:
            return

        line = self._grid[row]
        if start < self.cols and is_continuation(line[start]):
            lead = leading_cell_index(line, start)
            if lead is not None:
                start = lead
        if end > 0:
            bounds = self._glyph_bounds(row, end - 1)
            if bounds is not None:
                end = max(end, bounds[1])

        for col in range(start, min(end, self.cols)):
            self._grid[row][col] = self._blank_cell()

    def clear_line(self, row=None):
        if row is None:
            row = self._cursor_row
        if 0 <= row < self.rows:
            self._grid[row] = self._blank_row()
            if row == self._cursor_row:
                self._cursor_col = 0

    def clear_screen(self, mode="all"):
        if mode == "all":
            self._grid = [self._blank_row() for _ in range(self.rows)]
            self._cursor_row = 0
            self._cursor_col = 0
            return
        if mode == "below":
            self.clear_range(self._cursor_row, self._cursor_col, self.cols)
            for row in range(self._cursor_row + 1, self.rows):
                self._grid[row] = self._blank_row()
            return
        if mode == "above":
            for row in range(0, self._cursor_row):
                self._grid[row] = self._blank_row()
            self.clear_range(self._cursor_row, 0, self._cursor_col + 1)
            return
        raise ValueError(f"unknown clear_screen mode: {mode!r}")

    def scroll_up(self, count=1):
        if count <= 0 or self.rows <= 0:
            return
        for _ in range(min(count, self.rows)):
            scrolled_off = self._grid.pop(0)
            self._grid.append(self._blank_row())
            sink = self._scroll_sink
            if sink is not None:
                try:
                    sink(scrolled_off)
                except Exception:
                    pass

    def set_scroll_sink(self, sink):
        self._scroll_sink = sink

    def scroll_down(self, count=1):
        if count <= 0 or self.rows <= 0:
            return
        for _ in range(min(count, self.rows)):
            self._grid.insert(0, self._blank_row())
            self._grid.pop()

    def insert_line(self, count=1):
        if count <= 0:
            return
        for _ in range(min(count, self.rows)):
            self._grid.insert(self._cursor_row, self._blank_row())
            self._grid.pop()

    def delete_line(self, count=1):
        if count <= 0:
            return
        for _ in range(min(count, self.rows)):
            self._grid.pop(self._cursor_row)
            self._grid.append(self._blank_row())

    def delete_chars(self, count=1):
        """Delete physical columns at the cursor without orphaning wide tails."""
        count = max(1, int(count))
        row = self._cursor_row
        line = self._grid[row]
        if self._cursor_col >= self.cols:
            return
        start = self._cursor_col
        if is_continuation(line[start]):
            lead = leading_cell_index(line, start)
            if lead is not None:
                start = lead
        end = min(self.cols, start + count)
        if end < self.cols and is_continuation(line[end]):
            end += 1
        bounds = self._glyph_bounds(row, end - 1)
        if bounds is not None:
            end = max(end, bounds[1])
        removed = max(0, end - start)
        del line[start:end]
        line.extend(self._blank_cell() for _ in range(removed))
        self._grid[row] = sanitize_row(line[:self.cols], self._default_attr)

    def resize(self, rows, cols):
        rows = max(1, int(rows))
        cols = max(1, int(cols))
        old_cols = self.cols
        new_grid = [
            [(" ", self._default_attr) for _ in range(cols)] for _ in range(rows)
        ]
        common_rows = min(rows, self.rows)
        common_cols = min(cols, old_cols)
        for row in range(common_rows):
            new_grid[row][:common_cols] = self._grid[row][:common_cols]
            new_grid[row] = sanitize_row(new_grid[row], self._default_attr)
        self._grid = new_grid
        self.rows = rows
        self.cols = cols
        self._cursor_row = min(self._cursor_row, rows - 1)
        self._cursor_col = min(self._cursor_col, cols - 1)

class TerminalScreen:
    """Holds the normal-screen and alt-screen buffers for one terminal.

    The alt-screen is used by full-screen apps (vim, htop, less) and
    must be kept separate from the normal-screen grid and the
    scrollback list. Switching modes via :meth:`set_alt_screen` swaps the
    active buffer; the inactive buffer is preserved so toggling back
    to the original mode restores the previous view.

    Introduced for v0.9.5 to keep the alt-screen isolated from the
    normal-screen; the ``TerminalWindow`` will route the CSI ``?1049``
    private mode through this class once the buffer wiring lands.
    """

    __slots__ = ("_normal", "_alt", "_active")

    def __init__(self, rows, cols, default_attr=0, normal_cls=None, alt_cls=None):
        n_cls = normal_cls or TerminalScreenBuffer
        a_cls = alt_cls or n_cls
        self._normal = n_cls(rows, cols, default_attr=default_attr)
        self._alt = a_cls(rows, cols, default_attr=default_attr)
        self._active = self._normal

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    @property
    def alt_screen(self):
        return self._active is self._alt

    def set_alt_screen(self, enabled):
        """Switch to the alt-screen or back to the normal-screen."""
        self._active = self._alt if enabled else self._normal

    # ------------------------------------------------------------------
    # Pass-through to the active buffer
    # ------------------------------------------------------------------

    @property
    def rows(self):
        return self._active.rows

    @property
    def cols(self):
        return self._active.cols

    @property
    def cursor_row(self):
        return self._active.cursor_row

    @property
    def cursor_col(self):
        return self._active.cursor_col

    def set_cursor(self, row, col):
        self._active.set_cursor(row, col)

    def put_char(self, ch, attr=None, *, autowrap=True):
        self._active.put_char(ch, attr=attr, autowrap=autowrap)

    def carriage_return(self):
        self._active.carriage_return()

    def line_feed(self):
        self._active.line_feed()

    def backspace(self):
        self._active.backspace()

    def clear_line(self, row=None):
        self._active.clear_line(row)

    def clear_screen(self, mode="all"):
        self._active.clear_screen(mode)

    def scroll_up(self, count=1):
        self._active.scroll_up(count)

    def scroll_down(self, count=1):
        self._active.scroll_down(count)

    def insert_line(self, count=1):
        self._active.insert_line(count)

    def delete_line(self, count=1):
        self._active.delete_line(count)

    def get_cell(self, row, col):
        return self._active.get_cell(row, col)

    def get_row(self, row):
        return self._active.get_row(row)

    def resize(self, rows, cols):
        """Resize both buffers in lockstep so dimensions stay aligned."""
        self._normal.resize(rows, cols)
        self._alt.resize(rows, cols)


def _resolve_posix_backends():
    """Resolve and cache POSIX modules needed for PTY sessions."""
    cached = _BACKENDS_CACHE["value"]
    if cached is not _BACKENDS_UNSET:
        return cached

    try:
        fcntl_mod = importlib.import_module("fcntl")
        pty_mod = importlib.import_module("pty")
        termios_mod = importlib.import_module("termios")
    except ImportError:
        _BACKENDS_CACHE["value"] = None
        return None

    _BACKENDS_CACHE["value"] = (fcntl_mod, pty_mod, termios_mod)
    return _BACKENDS_CACHE["value"]


def _resolve_windows_backend():
    """Resolve and cache the pywinpty module for Windows PTY sessions."""
    cached = _WIN_BACKEND_CACHE["value"]
    if cached is not _BACKENDS_UNSET:
        return cached

    try:
        winpty_mod = importlib.import_module("winpty")
    except ImportError:
        _WIN_BACKEND_CACHE["value"] = None
        return None

    _WIN_BACKEND_CACHE["value"] = winpty_mod
    return winpty_mod


def _reset_backend_cache():
    """Reset cache for tests."""
    _BACKENDS_CACHE["value"] = _BACKENDS_UNSET


def _reset_win_backend_cache():
    """Reset Windows backend cache for tests."""
    _WIN_BACKEND_CACHE["value"] = _BACKENDS_UNSET


class TerminalSession:
    """Small wrapper around a PTY child process."""

    def __init__(self, shell=None, cwd=None, env=None, cols=80, rows=24):
        self.shell = shell
        self.cwd = cwd
        self.extra_env = dict(env or {})
        self.cols = max(1, int(cols))
        self.rows = max(1, int(rows))
        self.master_fd = None
        self.child_pid = None
        self.running = False
        self._win_pty = None
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._pending_write = bytearray()

    @staticmethod
    def is_supported():
        """Return True when PTY backends are available."""
        return _resolve_posix_backends() is not None or _resolve_windows_backend() is not None

    def _require_backends(self):
        backends = _resolve_posix_backends()
        if backends is None:
            raise RuntimeError("Embedded terminal requires POSIX pty/fcntl/termios support.")
        return backends

    def _set_nonblocking(self, fcntl_mod, master_fd):
        flags = fcntl_mod.fcntl(master_fd, fcntl_mod.F_GETFL)
        nonblock_flag = getattr(os, "O_NONBLOCK", 0)
        fcntl_mod.fcntl(master_fd, fcntl_mod.F_SETFL, flags | nonblock_flag)

    def _start_posix(self, backends):
        """Spawn shell process inside a POSIX PTY."""
        fcntl_mod, pty_mod, _termios_mod = backends
        shell = self.shell or os.environ.get("SHELL") or "/bin/sh"
        child_pid, master_fd = pty_mod.fork()

        if child_pid == 0:
            env = os.environ.copy()
            env.update(self.extra_env)
            if self.cwd:
                os.chdir(self.cwd)
            os.execvpe(shell, [shell], env)

        self.child_pid = child_pid
        self.master_fd = master_fd
        self.running = True
        self._set_nonblocking(fcntl_mod, master_fd)
        self.resize(self.cols, self.rows)

    def _windows_environment_block(self):
        """Build the CreateProcess-style environment block for ConPTY."""
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in self.extra_env.items()})
        return "\0".join(
            f"{key}={value}" for key, value in sorted(env.items())
        ) + "\0"

    def _spawn_windows_process(self, pty, shell):
        """Spawn with cwd/env when supported, retaining legacy fallbacks."""
        env_block = self._windows_environment_block()
        try:
            return pty.spawn(shell, cwd=self.cwd, env=env_block)
        except TypeError:
            pass

        try:
            return pty.spawn(shell, None, self.cwd, env_block)
        except TypeError:
            legacy_shell = shell.encode() if isinstance(shell, str) else shell
            return pty.spawn(legacy_shell)

    def _start_windows(self, winpty_mod):
        """Spawn shell process inside a Windows ConPTY."""
        shell = self.shell or os.environ.get("COMSPEC") or "cmd.exe"
        pty = winpty_mod.PTY(self.cols, self.rows)
        self._spawn_windows_process(pty, shell)
        self._win_pty = pty
        self.running = True

    def start(self):
        """Spawn shell process inside a PTY."""
        if self.running:
            return

        backends = _resolve_posix_backends()
        if backends is not None:
            self._start_posix(backends)
            return

        winpty = _resolve_windows_backend()
        if winpty is not None:
            self._start_windows(winpty)
            return

        raise RuntimeError("No PTY backend available (need POSIX pty or pywinpty).")

    def read(self, max_bytes=4096, max_total_bytes=_DEFAULT_READ_BUDGET):
        """Read available PTY output without exceeding an optional total budget.

        ``max_bytes`` limits each backend read. ``max_total_bytes`` limits the
        aggregate bytes admitted by this call and defaults to 8 KiB; unread
        data remains buffered by the PTY for the next service tick. Pass
        ``None`` only for an explicit unbounded drain.
        """
        max_bytes = max(1, int(max_bytes))
        if max_total_bytes is None:
            remaining = None
        else:
            remaining = max(0, int(max_total_bytes))
            if remaining == 0:
                return ""

        if self._win_pty is not None:
            read_size = max_bytes if remaining is None else min(max_bytes, remaining)
            return self._read_windows(read_size)

        if self.master_fd is None:
            return ""

        chunks = []
        while remaining is None or remaining > 0:
            read_size = max_bytes if remaining is None else min(max_bytes, remaining)
            try:
                chunk = os.read(self.master_fd, read_size)
            except BlockingIOError:
                break
            except OSError as exc:
                if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                if exc.errno == errno.EIO:
                    self.running = False
                    break
                raise

            if not chunk:
                self.running = False
                break

            chunks.append(chunk)
            if remaining is not None:
                remaining -= len(chunk)
            if len(chunk) < read_size:
                break

        if not chunks:
            return ""
        return self._decoder.decode(b"".join(chunks))

    def read_budgeted(self, max_total_bytes, max_bytes=4096):
        """Read at most ``max_total_bytes`` for one main-loop service tick."""
        return self.read(max_bytes=max_bytes, max_total_bytes=max_total_bytes)

    def _read_windows(self, max_bytes=4096):
        """Read available output from Windows ConPTY."""
        try:
            data = self._win_pty.read(max_bytes, blocking=False)
        except Exception:
            data = None
        if not data:
            return ""
        if isinstance(data, bytes):
            return self._decoder.decode(data)
        return data

    @property
    def pending_write_bytes(self):
        """Return the number of queued input bytes awaiting the PTY."""
        return len(self._pending_write)

    def write(self, data):
        """Accept a complete input payload and queue any unsent suffix.

        The return value is the number of bytes accepted by the session,
        not necessarily the number synchronously written to the backend.
        """
        if self._win_pty is None and self.master_fd is None:
            return 0
        if isinstance(data, str):
            payload = data.encode("utf-8", errors="replace")
        else:
            payload = bytes(data)
        if not payload:
            return 0
        self._pending_write.extend(payload)
        flushed = self.flush_pending_writes()
        if self._win_pty is not None and not self.running and flushed == 0:
            return 0
        return len(payload)

    def flush_pending_writes(self, max_total_bytes=_DEFAULT_WRITE_BUDGET):
        """Flush queued input without exceeding one service-tick budget."""
        budget = max(0, int(max_total_bytes))
        if budget == 0 or not self._pending_write:
            return 0
        if self._win_pty is None and self.master_fd is None:
            return 0

        total = 0
        while self._pending_write and total < budget:
            chunk = bytes(self._pending_write[:budget - total])
            try:
                if self._win_pty is not None:
                    written = self._write_windows(chunk)
                else:
                    written = os.write(self.master_fd, chunk)
            except BlockingIOError:
                break
            except OSError as exc:
                if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                if exc.errno in (errno.EIO, errno.EPIPE, errno.EBADF):
                    self.running = False
                raise

            if written is None:
                written = len(chunk)
            written = max(0, min(int(written), len(chunk)))
            if written == 0:
                break
            del self._pending_write[:written]
            total += written
        return total

    def _write_windows(self, data):
        """Write one queued chunk to Windows ConPTY."""
        payload = data.encode("utf-8", errors="replace") if isinstance(data, str) else bytes(data)
        try:
            result = self._win_pty.write(payload)
        except OSError:
            self._pending_write.clear()
            self.running = False
            return 0
        if isinstance(result, int):
            return max(0, min(result, len(payload)))
        return len(payload)

    def send_signal(self, sig):
        """Send signal to foreground process group (or child pid fallback)."""
        if not self.running:
            return False

        if self._win_pty is not None:
            return self._send_signal_windows(sig)

        if self.master_fd is not None and hasattr(os, "tcgetpgrp") and hasattr(os, "killpg"):
            try:
                pgid = os.tcgetpgrp(self.master_fd)
            except OSError:
                pgid = None
            if pgid and pgid > 0:
                try:
                    os.killpg(pgid, sig)
                    return True
                except OSError:
                    pass

        if self.child_pid is None:
            return False

        try:
            os.kill(self.child_pid, sig)
        except OSError:
            return False
        return True

    def _send_signal_windows(self, sig):
        """Send signal via Windows ConPTY (write Ctrl+C byte as fallback)."""
        if sig == signal.SIGINT:
            try:
                self._win_pty.write(b'\x03')
                return True
            except OSError:
                return False
        # For other signals, try os.kill if we can find the pid
        pid = getattr(self._win_pty, 'pid', None)
        if pid is not None:
            try:
                os.kill(pid, sig)
                return True
            except OSError:
                return False
        return False

    def interrupt(self):
        """Send SIGINT to foreground process."""
        return self.send_signal(signal.SIGINT)

    def terminate(self):
        """Send SIGTERM to foreground process."""
        return self.send_signal(signal.SIGTERM)

    def kill(self):
        """Send SIGKILL to foreground process."""
        sig = getattr(signal, "SIGKILL", signal.SIGTERM)
        return self.send_signal(sig)

    def _reap_posix_child(self, nohang=True):
        """Reap the POSIX child if it has exited."""
        if self.child_pid is None:
            return False

        try:
            flags = getattr(os, "WNOHANG", 0) if nohang else 0
            exited_pid, _status = os.waitpid(self.child_pid, flags)
        except ChildProcessError:
            self.running = False
            self.child_pid = None
            return True

        if exited_pid == 0:
            return False

        self.running = False
        self.child_pid = None
        return True

    def _wait_for_posix_exit(self, timeout):
        """Wait briefly for the child to exit without hanging close()."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while True:
            if self._reap_posix_child(nohang=True):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(_CLOSE_POLL_INTERVAL, max(0.0, deadline - time.monotonic())))

    def _windows_is_alive(self):
        """Probe ConPTY liveness without leaking backend exceptions."""
        if self._win_pty is None:
            return False
        probe = getattr(self._win_pty, "isalive", None)
        if not callable(probe):
            return bool(self.running)
        try:
            return bool(probe())
        except Exception:
            return False

    def _wait_for_windows_exit(self, timeout):
        """Wait briefly until the Windows child is observably stopped."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while self._windows_is_alive():
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(_CLOSE_POLL_INTERVAL, max(0.0, deadline - time.monotonic())))
        self.running = False
        return True

    def _close_windows_backend(self):
        """Close ConPTY explicitly and verify that its child exited."""
        backend = self._win_pty
        if backend is None:
            return True

        close_method = getattr(backend, "close", None)
        if callable(close_method):
            try:
                try:
                    close_method(force=True)
                except TypeError:
                    close_method()
            except Exception:
                pass
            if self._wait_for_windows_exit(_CLOSE_WAIT_SECONDS):
                return True

        cancel_io = getattr(backend, "cancel_io", None)
        if callable(cancel_io):
            try:
                cancel_io()
            except Exception:
                pass

        if self._windows_is_alive():
            self.running = True
            self._send_signal_windows(signal.SIGTERM)
            if not self._wait_for_windows_exit(_CLOSE_WAIT_SECONDS):
                force_signal = getattr(signal, "SIGKILL", signal.SIGTERM)
                self._send_signal_windows(force_signal)
                if not self._wait_for_windows_exit(_CLOSE_WAIT_SECONDS):
                    self.running = True
                    return False
        else:
            self.running = False
        return True

    def resize(self, cols, rows):
        """Update terminal window size and notify child PTY."""
        self.cols = max(1, int(cols))
        self.rows = max(1, int(rows))

        if self._win_pty is not None:
            try:
                self._win_pty.set_size(self.cols, self.rows)
            except OSError:
                pass
            return

        if self.master_fd is None:
            return

        backends = _resolve_posix_backends()
        if backends is None:
            return

        fcntl_mod, _pty_mod, termios_mod = backends
        winsize = struct.pack("HHHH", self.rows, self.cols, 0, 0)
        try:
            fcntl_mod.ioctl(self.master_fd, termios_mod.TIOCSWINSZ, winsize)
        except OSError:
            pass

    def poll_exit(self):
        """Check whether child process has exited."""
        if not self.running:
            return False

        if self._win_pty is not None:
            if not self._windows_is_alive():
                self.running = False
                return True
            return False

        if self.child_pid is None:
            return False
        return self._reap_posix_child(nohang=True)

    def close(self):
        """Close the PTY and report whether its backend stopped cleanly."""
        if self._win_pty is not None:
            if not self._close_windows_backend():
                return False
            self._win_pty = None
            self._pending_write.clear()
            self.running = False
            return True

        if self.running:
            self.terminate()
            if not self._wait_for_posix_exit(_CLOSE_WAIT_SECONDS):
                self.kill()
                self._wait_for_posix_exit(_CLOSE_WAIT_SECONDS)
        elif self.child_pid is not None:
            self._wait_for_posix_exit(0.0)

        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        self._pending_write.clear()
        self.running = False
        return True

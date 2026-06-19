"""Minimal PTY-backed terminal session helper for v0.4."""

from __future__ import annotations

import codecs
import errno
import importlib
import os
import signal
import struct

_BACKENDS_UNSET = object()
_BACKENDS_CACHE = {"value": _BACKENDS_UNSET}
_WIN_BACKEND_CACHE = {"value": _BACKENDS_UNSET}


class TerminalScreenBuffer:
    """2D rows x cols grid of (character, attribute) cells with a cursor.

    Introduced for v0.9.5 so the embedded terminal can hold a stable
    grid representation independent of the alt-screen overlay and the
    scrollback list. The class is deliberately framework-free: it does
    not touch curses, the PTY session, or the application event loop.
    The next milestone will route the normal-screen rendering through
    this buffer.
    """

    __slots__ = ("rows", "cols", "_grid", "_cursor_row", "_cursor_col",
                 "_default_attr")

    def __init__(self, rows, cols, default_attr=0):
        rows = max(1, int(rows))
        cols = max(1, int(cols))
        self.rows = rows
        self.cols = cols
        self._default_attr = int(default_attr)
        self._grid = [
            [(" ", self._default_attr) for _ in range(cols)] for _ in range(rows)
        ]
        self._cursor_row = 0
        self._cursor_col = 0

    # ------------------------------------------------------------------
    # Cursor management
    # ------------------------------------------------------------------

    @property
    def cursor_row(self):
        return self._cursor_row

    @property
    def cursor_col(self):
        return self._cursor_col

    def set_cursor(self, row, col):
        """Move the cursor to ``(row, col)`` clamped to the grid."""
        self._cursor_row = max(0, min(self.rows - 1, int(row)))
        self._cursor_col = max(0, min(self.cols - 1, int(col)))

    # ------------------------------------------------------------------
    # Cell access
    # ------------------------------------------------------------------

    def get_cell(self, row, col):
        """Return the ``(char, attr)`` at ``(row, col)`` or a space."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self._grid[row][col]
        return (" ", self._default_attr)

    def get_row(self, row):
        """Return the list of ``(char, attr)`` for ``row``."""
        if 0 <= row < self.rows:
            return list(self._grid[row])
        return []

    def put_char(self, ch, attr=None):
        """Write one character at the cursor and advance the column.

        Wraps to the next line on overflow; the bottom row scrolls up.
        ``\\n`` and ``\\r`` are not interpreted here: callers should use
        :meth:`line_feed` and :meth:`carriage_return` for those.
        """
        attr = self._default_attr if attr is None else attr
        if self._cursor_col >= self.cols:
            # Wrap to the next line: line_feed scrolls if needed, then
            # we reset the column so the cell write below stays in range.
            self.line_feed()
            self._cursor_col = 0
        if 0 <= self._cursor_row < self.rows:
            self._grid[self._cursor_row][self._cursor_col] = (ch, attr)
        self._cursor_col += 1

    def carriage_return(self):
        """Move the cursor to column 0."""
        self._cursor_col = 0

    def line_feed(self):
        """Scroll up if the cursor is on the last line, else advance."""
        if self._cursor_row >= self.rows - 1:
            self.scroll_up()
        else:
            self._cursor_row += 1

    def backspace(self):
        """Move the cursor one column to the left without wrapping."""
        if self._cursor_col > 0:
            self._cursor_col -= 1

    # ------------------------------------------------------------------
    # Line / screen ops
    # ------------------------------------------------------------------

    def clear_line(self, row=None):
        """Reset every cell in ``row`` (defaults to the cursor row)."""
        if row is None:
            row = self._cursor_row
        if 0 <= row < self.rows:
            self._grid[row] = [(" ", self._default_attr) for _ in range(self.cols)]
            if row == self._cursor_row:
                self._cursor_col = 0

    def clear_screen(self, mode="all"):
        """Clear the buffer.

        ``mode`` follows the CSI ``ED`` semantics:
        - ``"all"`` (default): clear the whole grid and home the cursor.
        - ``"below"``: clear from the cursor (inclusive) to the end of
          the screen. The cursor row is only blanked from the cursor
          column onward; columns before the cursor are preserved.
        - ``"above"``: clear from the top of the screen up to the
          cursor (inclusive).
        """
        if mode == "all":
            self._grid = [
                [(" ", self._default_attr) for _ in range(self.cols)]
                for _ in range(self.rows)
            ]
            self._cursor_row = 0
            self._cursor_col = 0
            return
        if mode == "below":
            # Preserve columns before the cursor on the cursor row.
            for c in range(self._cursor_col, self.cols):
                self._grid[self._cursor_row][c] = (" ", self._default_attr)
            for r in range(self._cursor_row + 1, self.rows):
                self._grid[r] = [(" ", self._default_attr) for _ in range(self.cols)]
            return
        if mode == "above":
            for r in range(0, self._cursor_row):
                self._grid[r] = [(" ", self._default_attr) for _ in range(self.cols)]
            # Clear up to and including the cursor column; columns
            # after the cursor are preserved.
            for c in range(0, self._cursor_col + 1):
                self._grid[self._cursor_row][c] = (" ", self._default_attr)
            return
        raise ValueError(f"unknown clear_screen mode: {mode!r}")

    def scroll_up(self, count=1):
        """Scroll the whole buffer up by ``count`` rows."""
        if count <= 0 or self.rows <= 0:
            return
        blank = [(" ", self._default_attr) for _ in range(self.cols)]
        for _ in range(min(count, self.rows)):
            self._grid.pop(0)
            self._grid.append(list(blank))

    def scroll_down(self, count=1):
        """Scroll the whole buffer down by ``count`` rows."""
        if count <= 0 or self.rows <= 0:
            return
        blank = [(" ", self._default_attr) for _ in range(self.cols)]
        for _ in range(min(count, self.rows)):
            self._grid.insert(0, list(blank))

    def insert_line(self, count=1):
        """Insert ``count`` blank rows at the cursor position."""
        if count <= 0:
            return
        blank = [(" ", self._default_attr) for _ in range(self.cols)]
        for _ in range(min(count, self.rows)):
            self._grid.insert(self._cursor_row, list(blank))
            self._grid.pop()

    def delete_line(self, count=1):
        """Delete ``count`` rows at the cursor position; bottom scrolls up."""
        if count <= 0:
            return
        blank = [(" ", self._default_attr) for _ in range(self.cols)]
        for _ in range(min(count, self.rows)):
            self._grid.pop(self._cursor_row)
            self._grid.append(list(blank))

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resize(self, rows, cols):
        """Resize the buffer, preserving cells that stay on screen."""
        rows = max(1, int(rows))
        cols = max(1, int(cols))
        new_grid = [
            [(" ", self._default_attr) for _ in range(cols)] for _ in range(rows)
        ]
        common_rows = min(rows, self.rows)
        common_cols = min(cols, self.cols)
        for r in range(common_rows):
            row_src = self._grid[r][:common_cols]
            new_grid[r][:common_cols] = row_src
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

    def put_char(self, ch, attr=None):
        self._active.put_char(ch, attr=attr)

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

    def _start_windows(self, winpty_mod):
        """Spawn shell process inside a Windows ConPTY."""
        shell = self.shell or os.environ.get("COMSPEC") or "cmd.exe"
        pty = winpty_mod.PTY(self.cols, self.rows)
        pty.spawn(shell.encode() if isinstance(shell, str) else shell)
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

    def read(self, max_bytes=4096):
        """Read available PTY output (non-blocking)."""
        if self._win_pty is not None:
            return self._read_windows(max_bytes)

        if self.master_fd is None:
            return ""

        chunks = []
        while True:
            try:
                chunk = os.read(self.master_fd, max_bytes)
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
            if len(chunk) < max_bytes:
                break

        if not chunks:
            return ""
        return self._decoder.decode(b"".join(chunks))

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

    def write(self, data):
        """Write data to PTY input."""
        if self._win_pty is not None:
            return self._write_windows(data)

        if self.master_fd is None:
            return 0
        if isinstance(data, str):
            payload = data.encode("utf-8", errors="replace")
        else:
            payload = bytes(data)
        return os.write(self.master_fd, payload)

    def _write_windows(self, data):
        """Write data to Windows ConPTY input."""
        if isinstance(data, str):
            payload = data.encode("utf-8", errors="replace")
        else:
            payload = bytes(data)
        try:
            self._win_pty.write(payload)
        except OSError:
            self.running = False
            return 0
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
            if not self._win_pty.isalive():
                self.running = False
                return True
            return False

        if self.child_pid is None:
            return False

        try:
            nohang_flag = getattr(os, "WNOHANG", 0)
            exited_pid, _status = os.waitpid(self.child_pid, nohang_flag)
        except ChildProcessError:
            self.running = False
            return True

        if exited_pid == 0:
            return False

        self.running = False
        return True

    def close(self):
        """Close PTY fd and mark session stopped."""
        if self._win_pty is not None:
            try:
                del self._win_pty
            except Exception:
                pass
            self._win_pty = None
            self.running = False
            return

        if self.master_fd is not None:
            if self.running:
                self.terminate()
                self.poll_exit()
                if self.running:
                    self.kill()

            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        self.running = False

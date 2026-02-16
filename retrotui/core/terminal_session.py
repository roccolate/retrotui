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


def _reset_backend_cache():
    """Reset cache for tests."""
    _BACKENDS_CACHE["value"] = _BACKENDS_UNSET


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
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")

    @staticmethod
    def is_supported():
        """Return True when PTY backends are available."""
        return _resolve_posix_backends() is not None

    def _require_backends(self):
        backends = _resolve_posix_backends()
        if backends is None:
            raise RuntimeError("Embedded terminal requires POSIX pty/fcntl/termios support.")
        return backends

    def _set_nonblocking(self, fcntl_mod, master_fd):
        flags = fcntl_mod.fcntl(master_fd, fcntl_mod.F_GETFL)
        nonblock_flag = getattr(os, "O_NONBLOCK", 0)
        fcntl_mod.fcntl(master_fd, fcntl_mod.F_SETFL, flags | nonblock_flag)

    def start(self):
        """Spawn shell process inside a PTY."""
        if self.running:
            return

        fcntl_mod, pty_mod, _termios_mod = self._require_backends()
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

    def read(self, max_bytes=4096):
        """Read available PTY output (non-blocking)."""
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

    def write(self, data):
        """Write data to PTY input."""
        if self.master_fd is None:
            return 0
        if isinstance(data, str):
            payload = data.encode("utf-8", errors="replace")
        else:
            payload = bytes(data)
        return os.write(self.master_fd, payload)

    def send_signal(self, sig):
        """Send signal to foreground process group (or child pid fallback)."""
        if not self.running:
            return False

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

    def interrupt(self):
        """Send SIGINT to foreground process."""
        return self.send_signal(signal.SIGINT)

    def terminate(self):
        """Send SIGTERM to foreground process."""
        return self.send_signal(signal.SIGTERM)

    def resize(self, cols, rows):
        """Update terminal window size and notify child PTY."""
        self.cols = max(1, int(cols))
        self.rows = max(1, int(rows))

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
        if not self.running or self.child_pid is None:
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
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        self.poll_exit()
        self.running = False

"""Temporary transactional patcher for Windows PTY backend parity."""

from pathlib import Path


SESSION_PATH = Path("retrotui/core/terminal_session.py")
TEST_PATH = Path("tests/test_terminal_windows_parity.py")


def replace_between(text, start_marker, end_marker, replacement, label):
    if text.count(start_marker) != 1 or text.count(end_marker) != 1:
        raise SystemExit(f"{label}: method markers mismatch")
    prefix, remainder = text.split(start_marker, 1)
    _old, suffix = remainder.split(end_marker, 1)
    return prefix + replacement + end_marker + suffix


session_text = SESSION_PATH.read_text(encoding="utf-8")

windows_start_block = '''    def _windows_environment_block(self):
        """Build the CreateProcess-style environment block for ConPTY."""
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in self.extra_env.items()})
        return "\\0".join(
            f"{key}={value}" for key, value in sorted(env.items())
        ) + "\\0"

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

'''
session_text = replace_between(
    session_text,
    "    def _start_windows(self, winpty_mod):\n",
    "    def start(self):\n",
    windows_start_block,
    "terminal_session.py Windows start block",
)

windows_helpers = '''    def _windows_is_alive(self):
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

'''
resize_marker = "    def resize(self, cols, rows):\n"
if session_text.count(resize_marker) != 1:
    raise SystemExit("terminal_session.py: resize marker mismatch")
session_text = session_text.replace(
    resize_marker,
    windows_helpers + resize_marker,
    1,
)

old_poll = '''        if self._win_pty is not None:
            if not self._win_pty.isalive():
                self.running = False
                return True
            return False
'''
new_poll = '''        if self._win_pty is not None:
            if not self._windows_is_alive():
                self.running = False
                return True
            return False
'''
if session_text.count(old_poll) != 1:
    raise SystemExit("terminal_session.py: Windows poll block mismatch")
session_text = session_text.replace(old_poll, new_poll, 1)

close_block = '''    def close(self):
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
'''
close_marker = "    def close(self):\n"
if session_text.count(close_marker) != 1:
    raise SystemExit("terminal_session.py: close marker mismatch")
session_text = session_text.split(close_marker, 1)[0] + close_block

SESSION_PATH.write_text(session_text, encoding="utf-8")

TEST_PATH.write_text('''import os
import signal
import types
import unittest
from unittest import mock

from retrotui.core import terminal_session


class TerminalWindowsParityTests(unittest.TestCase):
    def test_current_spawn_api_receives_cwd_and_merged_environment(self):
        backend = types.SimpleNamespace(spawn=mock.Mock())
        winpty_mod = types.SimpleNamespace(PTY=mock.Mock(return_value=backend))
        session = terminal_session.TerminalSession(
            shell="cmd.exe",
            cwd=r"C:\\workspace",
            env={"EXTRA": "two"},
            cols=100,
            rows=30,
        )

        with mock.patch.dict(terminal_session.os.environ, {"BASE": "one"}, clear=True):
            session._start_windows(winpty_mod)

        winpty_mod.PTY.assert_called_once_with(100, 30)
        args, kwargs = backend.spawn.call_args
        self.assertEqual(args, ("cmd.exe",))
        self.assertEqual(kwargs["cwd"], r"C:\\workspace")
        self.assertTrue(kwargs["env"].endswith("\\0"))
        self.assertEqual(
            set(filter(None, kwargs["env"].split("\\0"))),
            {"BASE=one", "EXTRA=two"},
        )
        self.assertIs(session._win_pty, backend)
        self.assertTrue(session.running)

    def test_positional_spawn_api_receives_context(self):
        calls = []

        def spawn(*args, **kwargs):
            calls.append((args, kwargs))
            if kwargs:
                raise TypeError("keywords unavailable")
            return True

        backend = types.SimpleNamespace(spawn=spawn)
        session = terminal_session.TerminalSession(
            shell="powershell.exe",
            cwd=r"C:\\project",
            env={"FLAG": "yes"},
        )
        with mock.patch.dict(terminal_session.os.environ, {}, clear=True):
            session._spawn_windows_process(backend, session.shell)

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0][0:3], ("powershell.exe", None, r"C:\\project"))
        self.assertEqual(calls[1][0][3], "FLAG=yes\\0")

    def test_legacy_spawn_api_falls_back_to_single_bytes_argument(self):
        calls = []

        def spawn(*args, **kwargs):
            calls.append((args, kwargs))
            if kwargs or len(args) != 1:
                raise TypeError("legacy API")
            return True

        backend = types.SimpleNamespace(spawn=spawn)
        session = terminal_session.TerminalSession(shell="cmd.exe")
        session._spawn_windows_process(backend, session.shell)

        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1], ((b"cmd.exe",), {}))

    def test_explicit_close_force_is_preferred_and_verified(self):
        state = {"alive": True}
        close = mock.Mock(side_effect=lambda force=True: state.update(alive=False))
        backend = types.SimpleNamespace(
            close=close,
            isalive=lambda: state["alive"],
        )
        session = terminal_session.TerminalSession()
        session._win_pty = backend
        session.running = True
        session._pending_write.extend(b"queued")

        self.assertTrue(session.close())

        close.assert_called_once_with(force=True)
        self.assertIsNone(session._win_pty)
        self.assertFalse(session.running)
        self.assertEqual(session.pending_write_bytes, 0)

    def test_explicit_close_without_force_argument_is_supported(self):
        state = {"alive": True}

        def close(*args, **kwargs):
            if kwargs:
                raise TypeError("no force keyword")
            state["alive"] = False

        close_mock = mock.Mock(side_effect=close)
        backend = types.SimpleNamespace(
            close=close_mock,
            isalive=lambda: state["alive"],
        )
        session = terminal_session.TerminalSession()
        session._win_pty = backend
        session.running = True

        self.assertTrue(session.close())
        self.assertEqual(close_mock.call_count, 2)
        self.assertEqual(close_mock.call_args_list[-1], mock.call())

    def test_raw_backend_cancels_io_and_terminates_by_pid(self):
        state = {"alive": True}
        cancel_io = mock.Mock()
        backend = types.SimpleNamespace(
            cancel_io=cancel_io,
            isalive=lambda: state["alive"],
            pid=4321,
        )
        session = terminal_session.TerminalSession()
        session._win_pty = backend
        session.running = True

        def kill(pid, sig):
            self.assertEqual(pid, 4321)
            self.assertEqual(sig, signal.SIGTERM)
            state["alive"] = False

        with mock.patch.object(terminal_session.os, "kill", side_effect=kill) as os_kill:
            self.assertTrue(session.close())

        cancel_io.assert_called_once_with()
        os_kill.assert_called_once_with(4321, signal.SIGTERM)
        self.assertIsNone(session._win_pty)
        self.assertFalse(session.running)

    def test_close_escalates_when_sigterm_does_not_finish(self):
        backend = types.SimpleNamespace(
            cancel_io=mock.Mock(),
            isalive=mock.Mock(return_value=True),
            pid=9876,
        )
        session = terminal_session.TerminalSession()
        session._win_pty = backend
        session.running = True

        with (
            mock.patch.object(terminal_session.os, "kill") as os_kill,
            mock.patch.object(session, "_wait_for_windows_exit", side_effect=[False, True]),
        ):
            self.assertTrue(session.close())

        expected_force = getattr(signal, "SIGKILL", signal.SIGTERM)
        self.assertEqual(
            os_kill.call_args_list,
            [mock.call(9876, signal.SIGTERM), mock.call(9876, expected_force)],
        )

    def test_failed_verified_close_retains_backend_and_pending_input(self):
        backend = types.SimpleNamespace(
            cancel_io=mock.Mock(),
            isalive=mock.Mock(return_value=True),
            pid=2468,
        )
        session = terminal_session.TerminalSession()
        session._win_pty = backend
        session.running = True
        session._pending_write.extend(b"queued")

        with (
            mock.patch.object(terminal_session.os, "kill"),
            mock.patch.object(session, "_wait_for_windows_exit", side_effect=[False, False]),
        ):
            self.assertFalse(session.close())

        self.assertIs(session._win_pty, backend)
        self.assertTrue(session.running)
        self.assertEqual(session.pending_write_bytes, 6)

    def test_poll_exit_treats_backend_probe_failure_as_stopped(self):
        backend = types.SimpleNamespace(isalive=mock.Mock(side_effect=OSError("closed")))
        session = terminal_session.TerminalSession()
        session._win_pty = backend
        session.running = True

        self.assertTrue(session.poll_exit())
        self.assertFalse(session.running)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

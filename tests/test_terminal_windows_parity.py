import os
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
            cwd=r"C:\workspace",
            env={"EXTRA": "two"},
            cols=100,
            rows=30,
        )

        with mock.patch.dict(terminal_session.os.environ, {"BASE": "one"}, clear=True):
            session._start_windows(winpty_mod)

        winpty_mod.PTY.assert_called_once_with(100, 30)
        args, kwargs = backend.spawn.call_args
        self.assertEqual(args, ("cmd.exe",))
        self.assertEqual(kwargs["cwd"], r"C:\workspace")
        self.assertTrue(kwargs["env"].endswith("\0"))
        self.assertEqual(
            set(filter(None, kwargs["env"].split("\0"))),
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
            cwd=r"C:\project",
            env={"FLAG": "yes"},
        )
        with mock.patch.dict(terminal_session.os.environ, {}, clear=True):
            session._spawn_windows_process(backend, session.shell)

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0][0:3], ("powershell.exe", None, r"C:\project"))
        self.assertEqual(calls[1][0][3], "FLAG=yes\0")

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

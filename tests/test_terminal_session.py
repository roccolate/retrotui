import errno
import importlib
import signal
import types
import unittest
from unittest import mock


class _FakeFcntl:
    F_GETFL = 11
    F_SETFL = 12

    def __init__(self):
        self.fcntl_calls = []
        self.ioctl_calls = []

    def fcntl(self, fd, op, arg=None):
        self.fcntl_calls.append((fd, op, arg))
        if op == self.F_GETFL:
            return 0x20
        return 0

    def ioctl(self, fd, request, payload):
        self.ioctl_calls.append((fd, request, payload))


class _FakePty:
    def __init__(self, pid, fd):
        self.pid = pid
        self.fd = fd

    def fork(self):
        return (self.pid, self.fd)


class TerminalSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = importlib.import_module("retrotui.core.terminal_session")

    def setUp(self):
        self.mod._reset_backend_cache()
        self.mod._reset_win_backend_cache()

    def test_resolve_posix_backends_success_and_cache(self):
        fake_fcntl = object()
        fake_pty = object()
        fake_termios = object()

        with mock.patch.object(
            self.mod.importlib,
            "import_module",
            side_effect=[fake_fcntl, fake_pty, fake_termios],
        ) as import_mod:
            first = self.mod._resolve_posix_backends()
            second = self.mod._resolve_posix_backends()

        self.assertEqual(first, (fake_fcntl, fake_pty, fake_termios))
        self.assertEqual(second, first)
        self.assertEqual(import_mod.call_count, 3)

    def test_resolve_posix_backends_import_error_returns_none(self):
        with mock.patch.object(
            self.mod.importlib,
            "import_module",
            side_effect=ImportError("missing"),
        ):
            backends = self.mod._resolve_posix_backends()

        self.assertIsNone(backends)

    def test_is_supported_reflects_backend_availability(self):
        with (
            mock.patch.object(self.mod, "_resolve_posix_backends", return_value=None),
            mock.patch.object(self.mod, "_resolve_windows_backend", return_value=None),
        ):
            self.assertFalse(self.mod.TerminalSession.is_supported())
        with mock.patch.object(
            self.mod,
            "_resolve_posix_backends",
            return_value=(object(), object(), object()),
        ):
            self.assertTrue(self.mod.TerminalSession.is_supported())

    def test_is_supported_true_when_only_windows_backend(self):
        with (
            mock.patch.object(self.mod, "_resolve_posix_backends", return_value=None),
            mock.patch.object(self.mod, "_resolve_windows_backend", return_value=object()),
        ):
            self.assertTrue(self.mod.TerminalSession.is_supported())

    def test_start_raises_when_backends_missing(self):
        session = self.mod.TerminalSession()

        with (
            mock.patch.object(self.mod, "_resolve_posix_backends", return_value=None),
            mock.patch.object(self.mod, "_resolve_windows_backend", return_value=None),
        ):
            with self.assertRaises(RuntimeError):
                session.start()

    def test_start_is_noop_when_already_running(self):
        session = self.mod.TerminalSession()
        session.running = True

        with mock.patch.object(self.mod, "_resolve_posix_backends") as resolver:
            session.start()

        resolver.assert_not_called()

    def test_start_parent_branch_sets_nonblocking_and_resizes(self):
        fake_fcntl = _FakeFcntl()
        fake_pty = _FakePty(4321, 77)
        fake_termios = types.SimpleNamespace(TIOCSWINSZ=222)
        session = self.mod.TerminalSession(cols=120, rows=40)

        with mock.patch.object(
            self.mod,
            "_resolve_posix_backends",
            return_value=(fake_fcntl, fake_pty, fake_termios),
        ):
            session.start()

        self.assertTrue(session.running)
        self.assertEqual(session.child_pid, 4321)
        self.assertEqual(session.master_fd, 77)
        self.assertEqual(fake_fcntl.fcntl_calls[0], (77, fake_fcntl.F_GETFL, None))
        nonblock_flag = getattr(self.mod.os, "O_NONBLOCK", 0)
        self.assertEqual(
            fake_fcntl.fcntl_calls[1],
            (77, fake_fcntl.F_SETFL, 0x20 | nonblock_flag),
        )
        self.assertEqual(len(fake_fcntl.ioctl_calls), 1)

    def test_start_child_branch_execs_shell_with_env_and_cwd(self):
        fake_fcntl = _FakeFcntl()
        fake_pty = _FakePty(0, 55)
        fake_termios = types.SimpleNamespace(TIOCSWINSZ=333)
        session = self.mod.TerminalSession(shell="/bin/testsh", cwd="/tmp/retro", env={"A": "1"})

        with (
            mock.patch.object(
                self.mod,
                "_resolve_posix_backends",
                return_value=(fake_fcntl, fake_pty, fake_termios),
            ),
            mock.patch.object(self.mod.os, "chdir") as chdir,
            mock.patch.object(self.mod.os, "execvpe", side_effect=SystemExit(0)) as execvpe,
        ):
            with self.assertRaises(SystemExit):
                session.start()

        chdir.assert_called_once_with("/tmp/retro")
        exec_args = execvpe.call_args.args
        self.assertEqual(exec_args[0], "/bin/testsh")
        self.assertEqual(exec_args[1], ["/bin/testsh"])
        self.assertEqual(exec_args[2]["A"], "1")

    def test_read_returns_empty_without_fd(self):
        session = self.mod.TerminalSession()
        self.assertEqual(session.read(), "")

    def test_read_handles_blocking_errors(self):
        session = self.mod.TerminalSession()
        session.master_fd = 88
        session.running = True

        with mock.patch.object(self.mod.os, "read", side_effect=BlockingIOError):
            self.assertEqual(session.read(), "")
        self.assertTrue(session.running)

    def test_read_handles_eagain_and_eio(self):
        session = self.mod.TerminalSession()
        session.master_fd = 90
        session.running = True

        err_again = OSError("again")
        err_again.errno = errno.EAGAIN
        with mock.patch.object(self.mod.os, "read", side_effect=err_again):
            self.assertEqual(session.read(), "")
        self.assertTrue(session.running)

        err_io = OSError("eio")
        err_io.errno = errno.EIO
        with mock.patch.object(self.mod.os, "read", side_effect=err_io):
            self.assertEqual(session.read(), "")
        self.assertFalse(session.running)

    def test_read_raises_unexpected_oserror(self):
        session = self.mod.TerminalSession()
        session.master_fd = 91

        err = OSError("boom")
        err.errno = errno.EPERM
        with mock.patch.object(self.mod.os, "read", side_effect=err):
            with self.assertRaises(OSError):
                session.read()

    def test_read_decodes_chunks_and_marks_stop_on_eof(self):
        session = self.mod.TerminalSession()
        session.master_fd = 92
        session.running = True

        with mock.patch.object(self.mod.os, "read", side_effect=[b"hello", b"world", b""]):
            output = session.read(max_bytes=5)

        self.assertEqual(output, "helloworld")
        self.assertFalse(session.running)

    def test_read_stops_after_short_chunk(self):
        session = self.mod.TerminalSession()
        session.master_fd = 923
        session.running = True

        with mock.patch.object(self.mod.os, "read", return_value=b"abc") as os_read:
            output = session.read(max_bytes=5)

        self.assertEqual(output, "abc")
        self.assertTrue(session.running)
        os_read.assert_called_once_with(923, 5)

    def test_write_variants_and_no_fd(self):
        session = self.mod.TerminalSession()
        self.assertEqual(session.write("abc"), 0)

        session.master_fd = 93
        with mock.patch.object(self.mod.os, "write", return_value=3) as os_write:
            count = session.write("abc")
            self.assertEqual(count, 3)
            self.assertEqual(os_write.call_args.args[1], b"abc")

        with mock.patch.object(self.mod.os, "write", return_value=2) as os_write:
            count = session.write(bytearray(b"xy"))
            self.assertEqual(count, 2)
            self.assertEqual(os_write.call_args.args[1], b"xy")

    def test_send_signal_uses_foreground_pgid_then_child_fallback(self):
        session = self.mod.TerminalSession()
        self.assertFalse(session.send_signal(signal.SIGINT))

        session.running = True
        session.master_fd = 123
        session.child_pid = 4321

        with (
            mock.patch.object(self.mod.os, "tcgetpgrp", return_value=987, create=True),
            mock.patch.object(self.mod.os, "killpg", create=True) as killpg,
            mock.patch.object(self.mod.os, "kill") as kill,
        ):
            self.assertTrue(session.send_signal(signal.SIGINT))
        killpg.assert_called_once_with(987, signal.SIGINT)
        kill.assert_not_called()

        with (
            mock.patch.object(self.mod.os, "tcgetpgrp", return_value=987, create=True),
            mock.patch.object(self.mod.os, "killpg", side_effect=OSError("bad"), create=True),
            mock.patch.object(self.mod.os, "kill") as kill,
        ):
            self.assertTrue(session.send_signal(signal.SIGTERM))
        kill.assert_called_once_with(4321, signal.SIGTERM)

        with (
            mock.patch.object(self.mod.os, "tcgetpgrp", side_effect=OSError("bad"), create=True),
            mock.patch.object(self.mod.os, "killpg", side_effect=OSError("bad"), create=True),
            mock.patch.object(self.mod.os, "kill") as kill,
        ):
            self.assertTrue(session.send_signal(signal.SIGTERM))
        kill.assert_called_once_with(4321, signal.SIGTERM)

        session.child_pid = None
        with (
            mock.patch.object(self.mod.os, "tcgetpgrp", side_effect=OSError("bad"), create=True),
            mock.patch.object(self.mod.os, "killpg", side_effect=OSError("bad"), create=True),
        ):
            self.assertFalse(session.send_signal(signal.SIGTERM))

    def test_send_signal_returns_false_when_kill_fails(self):
        session = self.mod.TerminalSession()
        session.running = True
        session.child_pid = 1

        with mock.patch.object(self.mod.os, "kill", side_effect=OSError("denied")):
            self.assertFalse(session.send_signal(signal.SIGTERM))

    def test_interrupt_and_terminate_delegate_to_send_signal(self):
        session = self.mod.TerminalSession()
        with mock.patch.object(session, "send_signal", return_value=True) as send_signal:
            self.assertTrue(session.interrupt())
            self.assertTrue(session.terminate())

        self.assertEqual(send_signal.call_count, 2)
        self.assertEqual(send_signal.call_args_list[0].args[0], signal.SIGINT)
        self.assertEqual(send_signal.call_args_list[1].args[0], signal.SIGTERM)

    def test_resize_updates_dimensions_and_handles_backends(self):
        session = self.mod.TerminalSession(cols=10, rows=5)
        session.resize(0, -1)
        self.assertEqual((session.cols, session.rows), (1, 1))

        session.master_fd = 94
        with mock.patch.object(self.mod, "_resolve_posix_backends", return_value=None):
            session.resize(120, 33)
        self.assertEqual((session.cols, session.rows), (120, 33))

        fake_fcntl = _FakeFcntl()
        fake_termios = types.SimpleNamespace(TIOCSWINSZ=444)
        with mock.patch.object(
            self.mod,
            "_resolve_posix_backends",
            return_value=(fake_fcntl, object(), fake_termios),
        ):
            session.resize(121, 34)
        self.assertEqual(len(fake_fcntl.ioctl_calls), 1)

    def test_resize_swallow_ioctl_oserror(self):
        session = self.mod.TerminalSession()
        session.master_fd = 95
        fake_termios = types.SimpleNamespace(TIOCSWINSZ=445)
        broken_fcntl = types.SimpleNamespace(ioctl=mock.Mock(side_effect=OSError("bad")))

        with mock.patch.object(
            self.mod,
            "_resolve_posix_backends",
            return_value=(broken_fcntl, object(), fake_termios),
        ):
            session.resize(80, 24)

    def test_poll_exit_paths(self):
        session = self.mod.TerminalSession()
        self.assertFalse(session.poll_exit())

        session.running = True
        session.child_pid = 9001
        with mock.patch.object(self.mod.os, "waitpid", return_value=(0, 0)):
            self.assertFalse(session.poll_exit())
        self.assertTrue(session.running)

        with mock.patch.object(self.mod.os, "waitpid", return_value=(9001, 0)):
            self.assertTrue(session.poll_exit())
        self.assertFalse(session.running)

        session.running = True
        session.child_pid = 9002
        with mock.patch.object(self.mod.os, "waitpid", side_effect=ChildProcessError):
            self.assertTrue(session.poll_exit())
        self.assertFalse(session.running)

    def test_close_closes_fd_and_ignores_close_errors(self):
        session = self.mod.TerminalSession()
        session.master_fd = 96
        session.running = True
        session.child_pid = 9003

        with (
            mock.patch.object(self.mod.os, "close", side_effect=OSError("closed")),
            mock.patch.object(self.mod.os, "waitpid", return_value=(9003, 0)) as waitpid,
            mock.patch.object(self.mod.TerminalSession, "terminate", return_value=True) as terminate,
            mock.patch.object(self.mod.TerminalSession, "kill", return_value=True) as kill_process,
        ):
            session.close()

        terminate.assert_called_once_with()
        kill_process.assert_not_called()
        waitpid.assert_called_once_with(9003, getattr(self.mod.os, "WNOHANG", 0))
        self.assertIsNone(session.master_fd)
        self.assertIsNone(session.child_pid)
        self.assertFalse(session.running)

    def test_close_kills_and_reaps_when_child_does_not_exit_after_term(self):
        session = self.mod.TerminalSession()
        session.master_fd = 97
        session.running = True
        session.child_pid = 9004

        with (
            mock.patch.object(self.mod.os, "close"),
            mock.patch.object(
                self.mod.os,
                "waitpid",
                side_effect=[(0, 0), (9004, 0)],
            ) as waitpid,
            mock.patch.object(self.mod.time, "monotonic", side_effect=[0.0, 1.0, 1.0, 1.0]),
            mock.patch.object(self.mod.TerminalSession, "terminate", return_value=True) as terminate,
            mock.patch.object(self.mod.TerminalSession, "kill", return_value=True) as kill_process,
        ):
            session.close()

        terminate.assert_called_once_with()
        kill_process.assert_called_once_with()
        self.assertEqual(waitpid.call_count, 2)
        self.assertIsNone(session.child_pid)
        self.assertFalse(session.running)

    def test_close_reaps_stopped_session_with_child_pid(self):
        session = self.mod.TerminalSession()
        session.master_fd = 98
        session.running = False
        session.child_pid = 9005

        with (
            mock.patch.object(self.mod.os, "close"),
            mock.patch.object(self.mod.os, "waitpid", return_value=(9005, 0)) as waitpid,
            mock.patch.object(self.mod.TerminalSession, "terminate") as terminate,
            mock.patch.object(self.mod.TerminalSession, "kill") as kill_process,
        ):
            session.close()

        terminate.assert_not_called()
        kill_process.assert_not_called()
        waitpid.assert_called_once_with(9005, getattr(self.mod.os, "WNOHANG", 0))
        self.assertIsNone(session.child_pid)
        self.assertFalse(session.running)

    def test_close_returns_false_when_posix_child_cannot_be_reaped(self):
        session = self.mod.TerminalSession()
        session.master_fd = 99
        session.running = True
        session.child_pid = 9006

        with (
            mock.patch.object(self.mod.os, "close"),
            mock.patch.object(
                session,
                "_wait_for_posix_exit",
                side_effect=[False, False],
            ) as wait_for_exit,
            mock.patch.object(session, "terminate", return_value=True) as terminate,
            mock.patch.object(session, "kill", return_value=True) as kill_process,
        ):
            result = session.close()

        self.assertFalse(result)
        terminate.assert_called_once_with()
        kill_process.assert_called_once_with()
        self.assertEqual(wait_for_exit.call_count, 2)
        self.assertEqual(session.child_pid, 9006)
        self.assertIsNone(session.master_fd)
        self.assertTrue(session.running)


    # -- Windows backend tests --------------------------------------------------

    def test_resolve_windows_backend_success_and_cache(self):
        self.mod._reset_win_backend_cache()
        fake_winpty = object()
        with mock.patch.object(
            self.mod.importlib, "import_module", return_value=fake_winpty,
        ) as import_mod:
            first = self.mod._resolve_windows_backend()
            second = self.mod._resolve_windows_backend()
        self.assertIs(first, fake_winpty)
        self.assertIs(second, first)
        import_mod.assert_called_once_with("winpty")

    def test_resolve_windows_backend_import_error_returns_none(self):
        self.mod._reset_win_backend_cache()
        with mock.patch.object(
            self.mod.importlib, "import_module", side_effect=ImportError("no winpty"),
        ):
            self.assertIsNone(self.mod._resolve_windows_backend())

    def test_start_windows_spawns_pty(self):
        fake_pty = mock.MagicMock()
        fake_winpty = mock.MagicMock()
        fake_winpty.PTY.return_value = fake_pty

        session = self.mod.TerminalSession(cols=100, rows=30)
        with (
            mock.patch.object(self.mod, "_resolve_posix_backends", return_value=None),
            mock.patch.object(self.mod, "_resolve_windows_backend", return_value=fake_winpty),
        ):
            session.start()

        self.assertTrue(session.running)
        self.assertIs(session._win_pty, fake_pty)
        fake_winpty.PTY.assert_called_once_with(100, 30)
        fake_pty.spawn.assert_called_once()

    def test_start_prefers_posix_over_windows(self):
        fake_fcntl = _FakeFcntl()
        fake_pty = _FakePty(999, 50)
        fake_termios = types.SimpleNamespace(TIOCSWINSZ=555)
        fake_winpty = mock.MagicMock()

        session = self.mod.TerminalSession()
        with (
            mock.patch.object(
                self.mod, "_resolve_posix_backends",
                return_value=(fake_fcntl, fake_pty, fake_termios),
            ),
            mock.patch.object(self.mod, "_resolve_windows_backend", return_value=fake_winpty),
        ):
            session.start()

        # Should use POSIX, not Windows
        self.assertEqual(session.master_fd, 50)
        self.assertIsNone(session._win_pty)

    def test_read_windows(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.read.return_value = b"hello"
        session.running = True

        result = session.read()
        self.assertEqual(result, "hello")
        session._win_pty.read.assert_called_once_with(blocking=False)

    def test_read_windows_retains_overflow_for_next_tick(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.read.return_value = "abcdef"
        session.running = True

        self.assertEqual(session.read(max_bytes=3, max_total_bytes=3), "abc")
        self.assertEqual(session.read(max_bytes=3, max_total_bytes=3), "def")
        session._win_pty.read.assert_called_once_with(blocking=False)

    def test_read_windows_supports_positional_legacy_flag(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.read.side_effect = [TypeError("keyword"), b"ok"]
        session.running = True

        self.assertEqual(session.read(), "ok")
        self.assertEqual(
            session._win_pty.read.call_args_list,
            [mock.call(blocking=False), mock.call(False)],
        )

    def test_read_windows_empty(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.read.return_value = b""
        session.running = True

        self.assertEqual(session.read(), "")

    def test_read_windows_exception(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.read.side_effect = Exception("timeout")
        session.running = True

        self.assertEqual(session.read(), "")

    def test_write_windows(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session.running = True

        count = session.write("hello")
        self.assertEqual(count, 5)
        session._win_pty.write.assert_called_once_with("hello")

    def test_write_windows_unicode_uses_text_and_byte_count(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.write.return_value = 1
        session.running = True

        count = session.write("é")

        self.assertEqual(count, len("é".encode("utf-8")))
        session._win_pty.write.assert_called_once_with("é")
        self.assertEqual(session.pending_write_bytes, 0)

    def test_write_windows_waits_for_complete_utf8_character(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session.running = True
        session._pending_write.extend("é".encode("utf-8"))

        self.assertEqual(session.flush_pending_writes(max_total_bytes=1), 0)
        session._win_pty.write.assert_not_called()
        self.assertEqual(session.pending_write_bytes, 2)

        self.assertEqual(session.flush_pending_writes(max_total_bytes=2), 2)
        session._win_pty.write.assert_called_once_with("é")
        self.assertEqual(session.pending_write_bytes, 0)

    def test_write_windows_oserror_marks_not_running(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.write.side_effect = OSError("broken")
        session.running = True

        count = session.write("test")
        self.assertEqual(count, 0)
        self.assertFalse(session.running)

    def test_resize_windows(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session.running = True

        session.resize(120, 40)
        session._win_pty.set_size.assert_called_once_with(120, 40)
        self.assertEqual(session.cols, 120)
        self.assertEqual(session.rows, 40)

    def test_resize_windows_oserror_swallowed(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.set_size.side_effect = OSError("bad")
        session.running = True

        session.resize(80, 24)  # Should not raise

    def test_poll_exit_windows(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session.running = True

        session._win_pty.isalive.return_value = True
        self.assertFalse(session.poll_exit())
        self.assertTrue(session.running)

        session._win_pty.isalive.return_value = False
        self.assertTrue(session.poll_exit())
        self.assertFalse(session.running)

    def test_close_windows(self):
        session = self.mod.TerminalSession()
        backend = mock.MagicMock()
        backend.isalive.return_value = False
        session._win_pty = backend
        session._pending_windows_output.extend(b"pending")
        session.running = True

        self.assertTrue(session.close())
        backend.close.assert_called_once_with(force=True)
        backend.isalive.assert_called_once_with()
        self.assertIsNone(session._win_pty)
        self.assertEqual(session._pending_windows_output, bytearray())
        self.assertFalse(session.running)

    def test_send_signal_windows_interrupt(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session.running = True

        self.assertTrue(session.interrupt())
        session._win_pty.write.assert_called_once_with('\x03')

    def test_send_signal_windows_interrupt_oserror(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.write.side_effect = OSError("broken")
        session.running = True

        self.assertFalse(session.interrupt())

    def test_send_signal_windows_terminate_with_pid(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.pid = 12345
        session.running = True

        with mock.patch.object(self.mod.os, "kill") as kill:
            self.assertTrue(session.terminate())
        kill.assert_called_once_with(12345, signal.SIGTERM)

    def test_send_signal_windows_no_pid(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock(spec=[])  # no pid attr
        session.running = True

        self.assertFalse(session.terminate())


if __name__ == "__main__":
    unittest.main()

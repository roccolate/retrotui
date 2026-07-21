import errno
import types
import unittest
from unittest import mock

from retrotui.apps.terminal import TerminalWindow
from retrotui.core import terminal_session


class TerminalPartialWriteTests(unittest.TestCase):
    def test_default_budget_queues_large_suffix(self):
        session = terminal_session.TerminalSession()
        session.master_fd = 7
        payload = b"x" * (terminal_session._DEFAULT_WRITE_BUDGET + 5)

        with mock.patch.object(
            terminal_session.os, "write", side_effect=lambda _fd, data: len(data)
        ) as writer:
            accepted = session.write(payload)
            self.assertEqual(accepted, len(payload))
            self.assertEqual(session.pending_write_bytes, 5)
            self.assertEqual(
                len(writer.call_args_list[0].args[1]),
                terminal_session._DEFAULT_WRITE_BUDGET,
            )
            self.assertEqual(session.flush_pending_writes(), 5)

        self.assertEqual(session.pending_write_bytes, 0)

    def test_partial_write_and_eagain_preserve_unsent_suffix(self):
        session = terminal_session.TerminalSession()
        session.master_fd = 8
        again = BlockingIOError(errno.EAGAIN, "again")

        with mock.patch.object(
            terminal_session.os, "write", side_effect=[2, again, 2]
        ) as writer:
            self.assertEqual(session.write(b"abcd"), 4)
            self.assertEqual(session.pending_write_bytes, 2)
            self.assertEqual(writer.call_args_list[0].args[1], b"abcd")
            self.assertEqual(writer.call_args_list[1].args[1], b"cd")
            self.assertEqual(session.flush_pending_writes(), 2)
            self.assertEqual(writer.call_args_list[2].args[1], b"cd")

        self.assertEqual(session.pending_write_bytes, 0)

    def test_zero_flush_budget_does_not_touch_backend(self):
        session = terminal_session.TerminalSession()
        session.master_fd = 9
        session._pending_write.extend(b"queued")

        with mock.patch.object(terminal_session.os, "write") as writer:
            self.assertEqual(session.flush_pending_writes(0), 0)

        writer.assert_not_called()
        self.assertEqual(session.pending_write_bytes, 6)

    def test_hard_posix_write_error_marks_session_stopped_and_keeps_queue(self):
        session = terminal_session.TerminalSession()
        session.master_fd = 10
        session.running = True
        broken = OSError(errno.EPIPE, "closed")

        with mock.patch.object(terminal_session.os, "write", side_effect=broken):
            with self.assertRaises(OSError):
                session.write(b"data")

        self.assertFalse(session.running)
        self.assertEqual(session.pending_write_bytes, 4)

    def test_windows_partial_result_is_queued(self):
        backend = types.SimpleNamespace(write=mock.Mock(side_effect=[2, 0, None]))
        session = terminal_session.TerminalSession()
        session._win_pty = backend

        self.assertEqual(session.write(b"abcd"), 4)
        self.assertEqual(session.pending_write_bytes, 2)
        self.assertEqual(backend.write.call_args_list[0].args[0], b"abcd")
        self.assertEqual(backend.write.call_args_list[1].args[0], b"cd")
        self.assertEqual(session.flush_pending_writes(), 2)
        self.assertEqual(backend.write.call_args_list[2].args[0], b"cd")
        self.assertEqual(session.pending_write_bytes, 0)

    def test_windows_hard_error_keeps_legacy_zero_result(self):
        backend = types.SimpleNamespace(write=mock.Mock(side_effect=OSError("broken")))
        session = terminal_session.TerminalSession()
        session._win_pty = backend
        session.running = True

        self.assertEqual(session.write(b"data"), 0)
        self.assertFalse(session.running)
        self.assertEqual(session.pending_write_bytes, 0)

    def test_terminal_tick_flushes_pending_input_before_read(self):
        win = TerminalWindow(1, 1, 40, 12)
        win.body_rect = lambda: (2, 2, 30, 8)
        win._ensure_session = lambda: None
        calls = []
        win._session = types.SimpleNamespace(
            resize=mock.Mock(),
            flush_pending_writes=mock.Mock(side_effect=lambda: calls.append("flush")),
            read=mock.Mock(side_effect=lambda: calls.append("read") or ""),
            poll_exit=mock.Mock(return_value=False),
        )

        self.assertFalse(win.tick())
        self.assertEqual(calls, ["flush", "read"])

    def test_close_discards_pending_input(self):
        session = terminal_session.TerminalSession()
        session.master_fd = 11
        session._pending_write.extend(b"queued")

        with mock.patch.object(terminal_session.os, "close"):
            session.close()

        self.assertEqual(session.pending_write_bytes, 0)


if __name__ == "__main__":
    unittest.main()

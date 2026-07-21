import types
import unittest
from unittest import mock

from retrotui.apps.terminal import TerminalWindow
from retrotui.core import terminal_session


class TerminalReadBudgetTests(unittest.TestCase):
    def test_posix_read_obeys_total_budget(self):
        session = terminal_session.TerminalSession()
        session.master_fd = 7
        session.running = True

        with mock.patch.object(
            terminal_session.os,
            "read",
            side_effect=lambda _fd, size: b"x" * size,
        ) as reader:
            output = session.read(max_bytes=4, max_total_bytes=10)

        self.assertEqual(output, "x" * 10)
        self.assertEqual(
            [call.args[1] for call in reader.call_args_list],
            [4, 4, 2],
        )
        self.assertTrue(session.running)

    def test_zero_total_budget_does_not_touch_backend(self):
        session = terminal_session.TerminalSession()
        session.master_fd = 8

        with mock.patch.object(terminal_session.os, "read") as reader:
            output = session.read(max_bytes=4, max_total_bytes=0)

        self.assertEqual(output, "")
        reader.assert_not_called()

    def test_budget_preserves_incremental_utf8_decoder_state(self):
        session = terminal_session.TerminalSession()
        session.master_fd = 9
        payload = bytearray("€".encode("utf-8"))

        def read_chunk(_fd, size):
            chunk = bytes(payload[:size])
            del payload[:size]
            return chunk

        with mock.patch.object(terminal_session.os, "read", side_effect=read_chunk):
            first = session.read(max_bytes=2, max_total_bytes=2)
            second = session.read(max_bytes=2, max_total_bytes=1)

        self.assertEqual(first, "")
        self.assertEqual(second, "€")

    def test_read_budgeted_delegates_to_total_byte_contract(self):
        session = terminal_session.TerminalSession()
        session.master_fd = 10

        with mock.patch.object(
            terminal_session.os,
            "read",
            side_effect=lambda _fd, size: b"y" * size,
        ) as reader:
            output = session.read_budgeted(7, max_bytes=3)

        self.assertEqual(output, "y" * 7)
        self.assertEqual(
            [call.args[1] for call in reader.call_args_list],
            [3, 3, 1],
        )

    def test_terminal_tick_uses_budgeted_reader(self):
        win = TerminalWindow(1, 1, 40, 12)
        win.body_rect = lambda: (2, 2, 30, 8)
        win._ensure_session = lambda: None
        budgeted_read = mock.Mock(
            return_value="z" * win.MAX_PTY_READ_PER_TICK
        )
        win._session = types.SimpleNamespace(
            resize=mock.Mock(),
            read_budgeted=budgeted_read,
            poll_exit=mock.Mock(return_value=False),
        )
        win._consume_output = mock.Mock()

        self.assertTrue(win.tick())

        budgeted_read.assert_called_once_with(win.MAX_PTY_READ_PER_TICK)
        win._consume_output.assert_called_once()
        self.assertEqual(
            len(win._consume_output.call_args.args[0]),
            win.MAX_OUTPUT_PER_FRAME,
        )

    def test_terminal_tick_keeps_legacy_session_fallback(self):
        win = TerminalWindow(1, 1, 40, 12)
        win.body_rect = lambda: (2, 2, 30, 8)
        win._ensure_session = lambda: None
        legacy_read = mock.Mock(return_value="legacy")
        win._session = types.SimpleNamespace(
            resize=mock.Mock(),
            read=legacy_read,
            poll_exit=mock.Mock(return_value=False),
        )
        win._consume_output = mock.Mock()

        self.assertTrue(win.tick())

        legacy_read.assert_called_once_with()
        win._consume_output.assert_called_once_with("legacy")


if __name__ == "__main__":
    unittest.main()

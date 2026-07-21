import unittest
from unittest import mock

from retrotui.core import terminal_session


class TerminalReadBudgetTests(unittest.TestCase):
    def test_default_read_budget_is_eight_kib(self):
        session = terminal_session.TerminalSession()
        session.master_fd = 6
        session.running = True

        with mock.patch.object(
            terminal_session.os,
            "read",
            side_effect=lambda _fd, size: b"d" * size,
        ) as reader:
            output = session.read()

        self.assertEqual(len(output), terminal_session._DEFAULT_READ_BUDGET)
        self.assertEqual(
            [call.args[1] for call in reader.call_args_list],
            [4096, 4096],
        )
        self.assertTrue(session.running)

    def test_posix_read_obeys_explicit_total_budget(self):
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

    def test_none_allows_explicit_unbounded_drain_until_short_read(self):
        session = terminal_session.TerminalSession()
        session.master_fd = 11
        chunks = [b"a" * 4, b"b" * 2]

        with mock.patch.object(
            terminal_session.os,
            "read",
            side_effect=chunks,
        ) as reader:
            output = session.read(max_bytes=4, max_total_bytes=None)

        self.assertEqual(output, "a" * 4 + "b" * 2)
        self.assertEqual(reader.call_count, 2)


if __name__ == "__main__":
    unittest.main()

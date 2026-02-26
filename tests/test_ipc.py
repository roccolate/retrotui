"""Tests for retrotui.core.ipc."""

import unittest

from retrotui.core.event_bus import EventBus
from retrotui.core.ipc import IPCMessage, IPCRouter


class _FakeWindow:
    """Minimal window stub for IPC tests."""

    def __init__(self, win_id):
        self.id = win_id
        self.received = []

    def on_ipc_message(self, msg):
        self.received.append(msg)


class _FakeWindowNoHandler:
    """Window stub without on_ipc_message."""

    def __init__(self, win_id):
        self.id = win_id


class IPCRouterTests(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.win1 = _FakeWindow(1)
        self.win2 = _FakeWindow(2)
        self.win3 = _FakeWindowNoHandler(3)
        self.windows = [self.win1, self.win2, self.win3]
        self.ipc = IPCRouter(self.bus, lambda: self.windows)

    # ------------------------------------------------------------------
    # send
    # ------------------------------------------------------------------

    def test_send_to_existing_window(self):
        result = self.ipc.send(1, 2, "greet", payload="hello")
        self.assertTrue(result)
        self.assertEqual(len(self.win2.received), 1)
        msg = self.win2.received[0]
        self.assertIsInstance(msg, IPCMessage)
        self.assertEqual(msg.sender_id, 1)
        self.assertEqual(msg.target_id, 2)
        self.assertEqual(msg.channel, "greet")
        self.assertEqual(msg.payload, "hello")

    def test_send_to_missing_window(self):
        result = self.ipc.send(1, 99, "test")
        self.assertFalse(result)

    def test_send_to_window_without_handler(self):
        result = self.ipc.send(1, 3, "test")
        self.assertFalse(result)

    def test_send_handler_exception(self):
        def explode(msg):
            raise ValueError("boom")

        self.win2.on_ipc_message = explode
        result = self.ipc.send(1, 2, "test")
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # broadcast
    # ------------------------------------------------------------------

    def test_broadcast_delivers_to_all_except_sender(self):
        count = self.ipc.broadcast(1, "announce", payload="hi")
        self.assertEqual(count, 1)  # win2 has handler, win3 doesn't
        self.assertEqual(len(self.win1.received), 0)  # sender skipped
        self.assertEqual(len(self.win2.received), 1)
        self.assertEqual(self.win2.received[0].payload, "hi")
        self.assertEqual(self.win2.received[0].target_id, -1)

    def test_broadcast_publishes_on_bus(self):
        bus_events = []
        self.bus.subscribe("ipc.message", bus_events.append)
        self.ipc.broadcast(1, "notify")
        self.assertEqual(len(bus_events), 1)
        self.assertEqual(bus_events[0].source, 1)
        self.assertIsInstance(bus_events[0].data, IPCMessage)

    def test_broadcast_handler_exception_isolated(self):
        def explode(msg):
            raise TypeError("bad")

        self.win2.on_ipc_message = explode
        win4 = _FakeWindow(4)
        self.windows.append(win4)
        count = self.ipc.broadcast(1, "test")
        # win2 fails, win4 succeeds
        self.assertEqual(count, 1)
        self.assertEqual(len(win4.received), 1)

    # ------------------------------------------------------------------
    # IPCMessage dataclass
    # ------------------------------------------------------------------

    def test_ipc_message_is_frozen(self):
        msg = IPCMessage(sender_id=1, target_id=2, channel="c")
        with self.assertRaises(AttributeError):
            msg.channel = "other"

    def test_ipc_message_default_payload(self):
        msg = IPCMessage(sender_id=1, target_id=2, channel="c")
        self.assertIsNone(msg.payload)


if __name__ == "__main__":
    unittest.main()

"""Tests for retrotui.core.event_bus."""

import unittest

from retrotui.core.event_bus import Event, EventBus, EventTopic


class EventBusTests(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    # ------------------------------------------------------------------
    # Basic subscribe / publish
    # ------------------------------------------------------------------

    def test_subscribe_and_publish(self):
        received = []
        self.bus.subscribe("test.topic", received.append)
        count = self.bus.publish("test.topic", data={"key": "value"})
        self.assertEqual(count, 1)
        self.assertEqual(len(received), 1)
        evt = received[0]
        self.assertIsInstance(evt, Event)
        self.assertEqual(evt.topic, "test.topic")
        self.assertEqual(evt.data, {"key": "value"})
        self.assertIsNone(evt.source)

    def test_publish_with_source(self):
        received = []
        self.bus.subscribe("t", received.append)
        self.bus.publish("t", data=42, source="win-1")
        self.assertEqual(received[0].source, "win-1")

    def test_publish_no_subscribers_returns_zero(self):
        self.assertEqual(self.bus.publish("nobody.listening"), 0)

    # ------------------------------------------------------------------
    # Multiple subscribers
    # ------------------------------------------------------------------

    def test_multiple_subscribers(self):
        a, b = [], []
        self.bus.subscribe("t", a.append)
        self.bus.subscribe("t", b.append)
        count = self.bus.publish("t", data="hi")
        self.assertEqual(count, 2)
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 1)

    def test_different_topics_are_isolated(self):
        a, b = [], []
        self.bus.subscribe("topic.a", a.append)
        self.bus.subscribe("topic.b", b.append)
        self.bus.publish("topic.a", data=1)
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 0)

    # ------------------------------------------------------------------
    # Unsubscribe via returned callable
    # ------------------------------------------------------------------

    def test_unsubscribe_callable(self):
        received = []
        unsub = self.bus.subscribe("t", received.append)
        self.bus.publish("t")
        self.assertEqual(len(received), 1)
        unsub()
        self.bus.publish("t")
        self.assertEqual(len(received), 1)  # no new events

    def test_unsubscribe_callable_idempotent(self):
        unsub = self.bus.subscribe("t", lambda e: None)
        unsub()
        unsub()  # should not raise

    # ------------------------------------------------------------------
    # Unsubscribe by subscriber_id
    # ------------------------------------------------------------------

    def test_unsubscribe_by_id(self):
        a, b = [], []
        self.bus.subscribe("t", a.append, subscriber_id="win-1")
        self.bus.subscribe("t", b.append, subscriber_id="win-2")
        removed = self.bus.unsubscribe("t", subscriber_id="win-1")
        self.assertEqual(removed, 1)
        self.bus.publish("t")
        self.assertEqual(len(a), 0)
        self.assertEqual(len(b), 1)

    def test_unsubscribe_all_by_id(self):
        received = []
        self.bus.subscribe("t1", received.append, subscriber_id="win-1")
        self.bus.subscribe("t2", received.append, subscriber_id="win-1")
        self.bus.subscribe_all(received.append, subscriber_id="win-1")
        removed = self.bus.unsubscribe_all(subscriber_id="win-1")
        self.assertEqual(removed, 3)
        self.bus.publish("t1")
        self.bus.publish("t2")
        self.assertEqual(len(received), 0)

    # ------------------------------------------------------------------
    # once flag
    # ------------------------------------------------------------------

    def test_once_fires_only_once(self):
        received = []
        self.bus.subscribe("t", received.append, once=True)
        self.bus.publish("t", data=1)
        self.bus.publish("t", data=2)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data, 1)

    # ------------------------------------------------------------------
    # Global (subscribe_all) subscriber
    # ------------------------------------------------------------------

    def test_subscribe_all(self):
        received = []
        self.bus.subscribe_all(received.append)
        self.bus.publish("topic.a", data=1)
        self.bus.publish("topic.b", data=2)
        self.assertEqual(len(received), 2)
        self.assertEqual(received[0].topic, "topic.a")
        self.assertEqual(received[1].topic, "topic.b")

    def test_subscribe_all_unsubscribe(self):
        received = []
        unsub = self.bus.subscribe_all(received.append)
        self.bus.publish("t")
        unsub()
        self.bus.publish("t")
        self.assertEqual(len(received), 1)

    # ------------------------------------------------------------------
    # Exception isolation
    # ------------------------------------------------------------------

    def test_subscriber_exception_does_not_block_others(self):
        results = []

        def bad_handler(event):
            raise RuntimeError("boom")

        self.bus.subscribe("t", bad_handler)
        self.bus.subscribe("t", results.append)
        count = self.bus.publish("t", data="ok")
        self.assertEqual(count, 1)  # bad handler doesn't count
        self.assertEqual(len(results), 1)

    def test_global_subscriber_exception_isolated(self):
        results = []

        def bad_handler(event):
            raise ValueError("oops")

        self.bus.subscribe_all(bad_handler)
        self.bus.subscribe("t", results.append)
        count = self.bus.publish("t", data="ok")
        # topic subscriber succeeds (1), global fails (not counted)
        self.assertEqual(count, 1)
        self.assertEqual(len(results), 1)

    # ------------------------------------------------------------------
    # clear
    # ------------------------------------------------------------------

    def test_clear_removes_all(self):
        received = []
        self.bus.subscribe("t", received.append)
        self.bus.subscribe_all(received.append)
        self.bus.clear()
        self.bus.publish("t")
        self.assertEqual(len(received), 0)

    # ------------------------------------------------------------------
    # EventTopic enum works as string topic
    # ------------------------------------------------------------------

    def test_event_topic_enum_as_topic(self):
        received = []
        self.bus.subscribe(EventTopic.CLIPBOARD_CHANGED, received.append)
        self.bus.publish(EventTopic.CLIPBOARD_CHANGED, data="text")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].topic, "clipboard.changed")

    def test_event_topic_enum_matches_string(self):
        received = []
        self.bus.subscribe("clipboard.changed", received.append)
        self.bus.publish(EventTopic.CLIPBOARD_CHANGED, data="x")
        self.assertEqual(len(received), 1)

    # ------------------------------------------------------------------
    # Event dataclass
    # ------------------------------------------------------------------

    def test_event_is_frozen(self):
        evt = Event(topic="t", data=1, source="s")
        with self.assertRaises(AttributeError):
            evt.topic = "other"


if __name__ == "__main__":
    unittest.main()

"""Lightweight publish/subscribe event bus for RetroTUI."""

import logging
from dataclasses import dataclass, field
from enum import Enum

LOGGER = logging.getLogger(__name__)


class EventTopic(str, Enum):
    """Built-in event topics. Custom string topics are also supported."""

    CLIPBOARD_CHANGED = "clipboard.changed"
    FILE_OP_STARTED = "file_op.started"
    FILE_OP_COMPLETED = "file_op.completed"
    FILE_OP_FAILED = "file_op.failed"
    WINDOW_OPENED = "window.opened"
    WINDOW_CLOSED = "window.closed"
    WINDOW_FOCUSED = "window.focused"
    CONFIG_CHANGED = "config.changed"
    THEME_CHANGED = "theme.changed"
    IPC_MESSAGE = "ipc.message"
    NOTIFICATION = "notification"


@dataclass(frozen=True)
class Event:
    """An event published on the bus."""

    topic: str
    data: object = None
    source: object = None


@dataclass
class _Subscription:
    """Internal record for one subscriber."""

    callback: object
    subscriber_id: object = None
    once: bool = False


class EventBus:
    """Synchronous publish/subscribe event bus.

    All dispatch happens inline on the caller's thread (the main event loop).
    Subscribers must not block.
    """

    def __init__(self):
        self._subscriptions: dict = {}
        self._global_subscriptions: list = []

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    def subscribe(self, topic, callback, *, subscriber_id=None, once=False):
        """Subscribe to *topic*. Returns an unsubscribe callable."""
        sub = _Subscription(callback=callback, subscriber_id=subscriber_id, once=once)
        self._subscriptions.setdefault(topic, []).append(sub)

        def _unsub():
            try:
                self._subscriptions[topic].remove(sub)
            except (KeyError, ValueError):
                pass

        return _unsub

    def subscribe_all(self, callback, *, subscriber_id=None):
        """Subscribe to ALL topics (useful for logging/debugging)."""
        sub = _Subscription(callback=callback, subscriber_id=subscriber_id)
        self._global_subscriptions.append(sub)

        def _unsub():
            try:
                self._global_subscriptions.remove(sub)
            except ValueError:
                pass

        return _unsub

    # ------------------------------------------------------------------
    # Unsubscribe
    # ------------------------------------------------------------------

    def unsubscribe(self, topic, *, subscriber_id):
        """Remove all subscriptions for *subscriber_id* on *topic*. Returns count removed."""
        subs = self._subscriptions.get(topic, [])
        before = len(subs)
        self._subscriptions[topic] = [s for s in subs if s.subscriber_id != subscriber_id]
        return before - len(self._subscriptions[topic])

    def unsubscribe_all(self, *, subscriber_id):
        """Remove *subscriber_id* from every topic."""
        count = 0
        for topic in list(self._subscriptions):
            count += self.unsubscribe(topic, subscriber_id=subscriber_id)
        before = len(self._global_subscriptions)
        self._global_subscriptions = [
            s for s in self._global_subscriptions if s.subscriber_id != subscriber_id
        ]
        count += before - len(self._global_subscriptions)
        return count

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish(self, topic, data=None, *, source=None):
        """Publish an event. Returns number of callbacks invoked."""
        event = Event(topic=topic, data=data, source=source)
        count = 0
        once_remove = []

        for sub in list(self._subscriptions.get(topic, [])):
            try:
                sub.callback(event)
                count += 1
            except Exception:
                LOGGER.debug("event subscriber error on %s", topic, exc_info=True)
            if sub.once:
                once_remove.append((topic, sub))

        for sub in list(self._global_subscriptions):
            try:
                sub.callback(event)
                count += 1
            except Exception:
                LOGGER.debug("global subscriber error on %s", topic, exc_info=True)

        for t, s in once_remove:
            try:
                self._subscriptions[t].remove(s)
            except (KeyError, ValueError):
                pass

        return count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self):
        """Remove all subscriptions."""
        self._subscriptions.clear()
        self._global_subscriptions.clear()

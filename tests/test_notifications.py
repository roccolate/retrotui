"""Tests for retrotui.core.notifications."""

import unittest
from unittest import mock

from retrotui.core.event_bus import EventBus
from retrotui.core.notifications import (
    NotificationManager,
    Toast,
    TOAST_DISPLAY_SECONDS,
    TOAST_MAX_VISIBLE,
    TOAST_MAX_QUEUE,
)


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.mgr = NotificationManager(self.bus)

    # ------------------------------------------------------------------
    # Basic notify
    # ------------------------------------------------------------------

    def test_notify_creates_toast(self):
        self.mgr.notify("hello")
        self.assertEqual(len(self.mgr.visible_toasts), 1)
        toast = self.mgr.visible_toasts[0]
        self.assertEqual(toast.message, "hello")
        self.assertEqual(toast.level, "info")
        self.assertEqual(toast.title, "Info")

    def test_notify_custom_title_and_level(self):
        self.mgr.notify("done", title="Copy", level="success")
        toast = self.mgr.visible_toasts[0]
        self.assertEqual(toast.title, "Copy")
        self.assertEqual(toast.level, "success")

    # ------------------------------------------------------------------
    # Expiry
    # ------------------------------------------------------------------

    def test_tick_removes_expired(self):
        self.mgr.notify("old", duration=0.0)
        self.assertTrue(self.mgr.tick())
        self.assertEqual(len(self.mgr.visible_toasts), 0)

    def test_tick_keeps_active(self):
        self.mgr.notify("fresh", duration=999.0)
        changed = self.mgr.tick()
        self.assertFalse(changed)
        self.assertEqual(len(self.mgr.visible_toasts), 1)

    # ------------------------------------------------------------------
    # Max visible
    # ------------------------------------------------------------------

    def test_max_visible_cap(self):
        for i in range(TOAST_MAX_VISIBLE + 2):
            self.mgr.notify(f"msg-{i}", duration=999.0)
        self.assertEqual(len(self.mgr.visible_toasts), TOAST_MAX_VISIBLE)

    def test_has_visible(self):
        self.assertFalse(self.mgr.has_visible)
        self.mgr.notify("x", duration=999.0)
        self.assertTrue(self.mgr.has_visible)

    # ------------------------------------------------------------------
    # Queue cap
    # ------------------------------------------------------------------

    def test_queue_cap(self):
        for i in range(TOAST_MAX_QUEUE + 5):
            self.mgr.notify(f"msg-{i}", duration=999.0)
        self.assertEqual(len(self.mgr._toasts), TOAST_MAX_QUEUE)

    # ------------------------------------------------------------------
    # EventBus integration
    # ------------------------------------------------------------------

    def test_bus_string_notification(self):
        self.bus.publish("notification", data="bus hello")
        self.assertEqual(len(self.mgr.visible_toasts), 1)
        self.assertEqual(self.mgr.visible_toasts[0].message, "bus hello")

    def test_bus_dict_notification(self):
        self.bus.publish("notification", data={
            "message": "copied",
            "title": "File Op",
            "level": "success",
        })
        toast = self.mgr.visible_toasts[0]
        self.assertEqual(toast.message, "copied")
        self.assertEqual(toast.title, "File Op")
        self.assertEqual(toast.level, "success")

    def test_bus_none_data_ignored(self):
        self.bus.publish("notification", data=None)
        self.assertEqual(len(self.mgr.visible_toasts), 0)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def test_cleanup_unsubscribes(self):
        self.mgr.notify("before")
        self.mgr.cleanup()
        self.assertEqual(len(self.mgr._toasts), 0)
        # Bus notification should no longer reach the manager
        self.bus.publish("notification", data="after")
        self.assertEqual(len(self.mgr._toasts), 0)

    # ------------------------------------------------------------------
    # No bus
    # ------------------------------------------------------------------

    def test_works_without_bus(self):
        mgr = NotificationManager()
        mgr.notify("standalone")
        self.assertEqual(len(mgr.visible_toasts), 1)
        mgr.cleanup()

    # ------------------------------------------------------------------
    # Toast dataclass
    # ------------------------------------------------------------------

    def test_toast_expired_property(self):
        toast = Toast(title="T", message="M", duration=0.0)
        self.assertTrue(toast.expired)

    def test_toast_not_expired(self):
        toast = Toast(title="T", message="M", duration=999.0)
        self.assertFalse(toast.expired)


if __name__ == "__main__":
    unittest.main()

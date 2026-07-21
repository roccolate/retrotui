import unittest
from types import SimpleNamespace

from retrotui.core.event_bus import EventBus
from retrotui.core.window_manager import WindowManager


class WindowLifecycleContractTests(unittest.TestCase):
    def test_window_manager_uses_public_event_bus_contract(self):
        """Lifecycle behavior must not depend on private bus access order."""
        bus = EventBus()
        opened = []
        subscribed = []
        bus.subscribe("window.opened", opened.append)

        class App:
            @property
            def event_bus(self):
                return bus

        win = SimpleNamespace(
            id="window-1",
            title="Lifecycle test",
            active=False,
            visible=True,
            always_on_top=False,
            subscribe_to_bus=subscribed.append,
        )
        manager = WindowManager(App())

        manager._spawn_window(win)

        self.assertEqual(subscribed, [bus])
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].data["window_id"], "window-1")
        self.assertEqual(opened[0].data["title"], "Lifecycle test")
        self.assertIs(manager.get_active_window(), win)


if __name__ == "__main__":
    unittest.main()

import threading
import types
import unittest

from retrotui.core import event_loop
from retrotui.plugins.base import RetroApp


class RedrawContractTests(unittest.TestCase):
    def test_tick_probe_uses_public_periodic_contract(self):
        window = types.SimpleNamespace(
            visible=True,
            tick_when_hidden=False,
            wants_periodic_tick=True,
            needs_redraw=False,
            _animated=False,
            tick=lambda: False,
            _session=None,
        )
        app = types.SimpleNamespace(windows=[window])

        changed, has_live, has_periodic = event_loop._tick_and_probe_windows(app)

        self.assertFalse(changed)
        self.assertFalse(has_live)
        self.assertTrue(has_periodic)

    def test_legacy_redraw_flags_do_not_drive_core(self):
        window = types.SimpleNamespace(
            visible=True,
            tick_when_hidden=False,
            wants_periodic_tick=False,
            needs_redraw=True,
            _animated=True,
            tick=lambda: False,
            _session=None,
        )
        app = types.SimpleNamespace(windows=[window])

        changed, has_live, has_periodic = event_loop._tick_and_probe_windows(app)

        self.assertFalse(changed)
        self.assertFalse(has_live)
        self.assertFalse(has_periodic)

    def test_periodic_contract_selects_periodic_timeout(self):
        window = types.SimpleNamespace(
            visible=True,
            wants_periodic_tick=True,
            tick_when_hidden=False,
            _session=None,
        )
        app = types.SimpleNamespace(
            windows=[window],
            input_timeout_idle_ms=500,
            input_timeout_periodic_ms=40,
            has_background_operation=lambda: False,
        )

        self.assertEqual(event_loop._select_input_timeout_ms(app), 40)

    def test_retro_app_periodic_default_tick_requests_redraw(self):
        class PeriodicPlugin(RetroApp):
            wants_periodic_tick = True

        plugin = PeriodicPlugin.__new__(PeriodicPlugin)
        self.assertTrue(plugin.tick())

    def test_legacy_plugin_redraw_property_is_mapped_at_boundary(self):
        class LegacyPlugin(RetroApp):
            @property
            def needs_redraw(self):
                return True

        plugin = LegacyPlugin.__new__(LegacyPlugin)
        self.assertTrue(plugin.wants_periodic_tick)
        self.assertTrue(plugin.tick())

    def test_file_manager_preview_redraw_is_consumed_once(self):
        from retrotui.apps.filemanager.window import FileManagerWindow

        window = FileManagerWindow.__new__(FileManagerWindow)
        window._preview_lock = threading.Lock()
        window._preview_redraw_pending = True

        self.assertTrue(window.tick())
        self.assertFalse(window.tick())


if __name__ == "__main__":
    unittest.main()

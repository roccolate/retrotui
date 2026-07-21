import unittest
from types import SimpleNamespace
from unittest import mock

from retrotui.core import plugin_manager


class PluginManagerSafetyTests(unittest.TestCase):
    class PluginBoom(Exception):
        pass

    def test_register_manifest_isolates_custom_loader_error_and_preserves_valid_plugins(self):
        app = SimpleNamespace(_plugins={})
        manifest = {"plugin": {"id": "demo"}}

        plugin_manager.register_plugin_manifest(
            app,
            manifest,
            mock.Mock(side_effect=self.PluginBoom("boom")),
        )
        self.assertEqual(app._plugins, {})

        class ValidPlugin:
            pass

        plugin_manager.register_plugin_manifest(app, manifest, lambda _manifest: ValidPlugin)
        self.assertIs(app._plugins["demo"]["class"], ValidPlugin)

    def test_plugin_constructor_custom_error_is_isolated(self):
        class BrokenPlugin:
            def __init__(self, *_args, **_kwargs):
                raise PluginManagerSafetyTests.PluginBoom("constructor failed")

        app = SimpleNamespace(_next_window_offset=lambda *_args: (8, 3))
        info = {
            "class": BrokenPlugin,
            "manifest": {
                "plugin": {
                    "id": "broken",
                    "name": "Broken",
                    "window": {},
                }
            },
        }

        self.assertIsNone(plugin_manager.build_plugin_window(app, info, "broken"))

    def test_discovery_custom_error_does_not_abort_startup(self):
        app = SimpleNamespace(
            _plugins={"stale": object()},
            refresh_icons=mock.Mock(),
            _rebuild_global_menu=mock.Mock(),
        )

        with (
            mock.patch.object(plugin_manager, "plugins_disabled_by_visibility", return_value=False),
            mock.patch(
                "retrotui.plugins.loader.discover_plugins",
                side_effect=self.PluginBoom("discovery failed"),
            ),
        ):
            plugin_manager.load_plugins_runtime(app)

        self.assertEqual(app._plugins, {})
        app.refresh_icons.assert_called_once_with()
        app._rebuild_global_menu.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

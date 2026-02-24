import importlib
import sys
import types
import unittest
from unittest import mock

from retrotui.core.actions import AppAction, ActionType


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_LEFT = 260
    fake.KEY_RIGHT = 261
    fake.KEY_ENTER = 10
    fake.A_REVERSE = 1
    fake.A_BOLD = 2
    fake.BUTTON1_CLICKED = 1
    fake.color_pair = lambda _: 0
    return fake


class AppManagerV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        cls.fake_curses = _install_fake_curses()
        sys.modules["curses"] = cls.fake_curses

        for mod_name in list(sys.modules):
            if mod_name in (
                "retrotui.apps.app_manager",
                "retrotui.utils",
                "retrotui.constants",
                "retrotui.ui.window",
                "retrotui.theme",
            ):
                sys.modules.pop(mod_name, None)

        cls.app_manager_mod = importlib.import_module("retrotui.apps.app_manager")
        cls.DesktopIconManagerWindow = cls.app_manager_mod.DesktopIconManagerWindow
        cls.MenuEditorWindow = cls.app_manager_mod.MenuEditorWindow
        cls.AppManagerWindow = cls.app_manager_mod.AppManagerWindow

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.app_manager",
            "retrotui.utils",
            "retrotui.constants",
            "retrotui.ui.window",
            "retrotui.theme",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def setUp(self):
        self.app = types.SimpleNamespace()
        self.app.use_unicode = True
        self.app.config = types.SimpleNamespace(hidden_icons="plugin:weather,game1", hidden_menu_items="plugin:weather")
        self.app.persist_config = mock.Mock()
        self.app.refresh_icons = mock.Mock()
        self.app._rebuild_global_menu = mock.Mock()

        self.app._build_desktop_icon_catalog = mock.Mock(
            return_value=[
                {"label": "App1", "category": "Apps", "action": AppAction.ABOUT},
                {"label": "Game1", "category": "Games", "action": AppAction.SNAKE},
                {"label": "Weather", "category": "Plugins", "action": "plugin:weather", "hide_key": "plugin:weather"},
            ]
        )
        self.app._build_menu_editor_catalog = mock.Mock(
            return_value=[
                {"category": "Apps", "label": "Calculator", "action": AppAction.CALCULATOR, "key": "calculator"},
                {"category": "Games", "label": "Snake", "action": AppAction.SNAKE, "key": "snake"},
                {"category": "Plugins", "label": "Weather", "action": "plugin:weather", "key": "plugin:weather"},
            ]
        )
        self.app._icon_visibility_key = mock.Mock(side_effect=lambda icon: str(icon.get("hide_key") or icon.get("label", "")).lower())
        self.app._get_hidden_icon_labels = mock.Mock(return_value={"plugin:weather", "game1"})
        self.app._get_hidden_menu_keys = mock.Mock(return_value={"plugin:weather"})

    def test_desktop_icon_manager_groups_apps_games_plugins(self):
        win = self.DesktopIconManagerWindow(0, 0, 80, 24, self.app)
        self.assertIn("Apps", win.categories)
        self.assertIn("Games", win.categories)
        self.assertIn("Plugins", win.categories)
        self.assertEqual(len(win.choices["Apps"]), 1)
        self.assertEqual(len(win.choices["Games"]), 1)
        self.assertEqual(len(win.choices["Plugins"]), 1)

    def test_desktop_icon_manager_honors_hidden_set(self):
        win = self.DesktopIconManagerWindow(0, 0, 80, 24, self.app)
        self.assertTrue(win.choices["Apps"][0][2])      # App1 visible
        self.assertFalse(win.choices["Games"][0][2])    # Game1 hidden
        self.assertFalse(win.choices["Plugins"][0][2])  # Weather plugin hidden

    def test_menu_editor_honors_hidden_set_and_plugins(self):
        win = self.MenuEditorWindow(0, 0, 80, 24, self.app)
        self.assertIn("Plugins", win.categories)
        self.assertTrue(win.choices["Apps"][0][2])
        self.assertTrue(win.choices["Games"][0][2])
        self.assertFalse(win.choices["Plugins"][0][2])

    def test_navigation_between_categories(self):
        win = self.DesktopIconManagerWindow(0, 0, 80, 24, self.app)
        win.active = True
        initial = win.active_cat_idx
        win.handle_key(self.fake_curses.KEY_RIGHT)
        self.assertGreaterEqual(win.active_cat_idx, initial)
        win.handle_key(self.fake_curses.KEY_LEFT)
        self.assertEqual(win.active_cat_idx, 0)

    def test_toggle_checkbox_with_space(self):
        win = self.DesktopIconManagerWindow(0, 0, 80, 24, self.app)
        cat = win.categories[win.active_cat_idx]
        initial_state = win.choices[cat][0][2]
        win.handle_key(32)
        self.assertNotEqual(win.choices[cat][0][2], initial_state)

    def test_save_icons_updates_config_and_refresh(self):
        win = self.DesktopIconManagerWindow(0, 0, 80, 24, self.app)
        win.in_list = False
        win.selected_button = 0
        result = win.handle_key(10)

        self.assertEqual(result.type, ActionType.EXECUTE)
        self.assertEqual(result.payload, AppAction.CLOSE_WINDOW)
        self.app.persist_config.assert_called_once_with()
        self.app.refresh_icons.assert_called_once_with()
        self.assertTrue(hasattr(self.app.config, "hidden_icons"))

    def test_save_menu_updates_config_and_rebuilds_menu(self):
        win = self.MenuEditorWindow(0, 0, 80, 24, self.app)
        win.in_list = False
        win.selected_button = 0
        result = win.handle_key(10)

        self.assertEqual(result.type, ActionType.EXECUTE)
        self.assertEqual(result.payload, AppAction.CLOSE_WINDOW)
        self.app.persist_config.assert_called_once_with()
        self.app._rebuild_global_menu.assert_called_once_with()
        self.assertTrue(hasattr(self.app.config, "hidden_menu_items"))

    def test_app_manager_alias_points_to_desktop_editor(self):
        win = self.AppManagerWindow(0, 0, 80, 24, self.app)
        self.assertIsInstance(win, self.DesktopIconManagerWindow)


if __name__ == "__main__":
    unittest.main()

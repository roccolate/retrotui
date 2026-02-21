import unittest
from unittest import mock
import types
import curses
from retrotui.apps.app_manager import AppManagerWindow
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
    def setUp(self):
        self.curses_mock = _install_fake_curses()
        self.patcher = mock.patch("retrotui.apps.app_manager.curses", self.curses_mock)
        self.patcher.start()
        
        self.app = mock.Mock()
        self.app.use_unicode = True
        self.app.config = mock.Mock()
        self.app.config.hidden_icons = "snake,mines"
        self.app.persist_config = mock.Mock()
        self.app.refresh_icons = mock.Mock()
        
        # Mock ICONS in constants to be predictable
        self.mock_icons = [
            {"label": "App1", "category": "Apps", "action": AppAction.ABOUT},
            {"label": "Game1", "category": "Games", "action": AppAction.SNAKE},
        ]
        self.icon_patcher = mock.patch("retrotui.apps.app_manager.ICONS", self.mock_icons)
        self.icon_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.icon_patcher.stop()

    def test_init_groups_by_category(self):
        win = AppManagerWindow(0, 0, 80, 24, self.app)
        self.assertEqual(len(win.choices["Apps"]), 1)
        self.assertEqual(len(win.choices["Games"]), 1)
        # Game1 is hidden if "snake" is in hidden_icons (SNAKE label is "Snake", wait...)
        # In my mock I used "Game1" label
        self.app.config.hidden_icons = "game1"
        win = AppManagerWindow(0, 0, 80, 24, self.app)
        self.assertTrue(win.choices["Apps"][0][2]) # App1 checked
        self.assertFalse(win.choices["Games"][0][2]) # Game1 unchecked

    def test_navigation_between_columns(self):
        win = AppManagerWindow(0, 0, 80, 24, self.app)
        win.active = True
        self.assertEqual(win.active_cat_idx, 0) # Apps
        
        win.handle_key(self.curses_mock.KEY_RIGHT)
        self.assertEqual(win.active_cat_idx, 1) # Games
        
        win.handle_key(self.curses_mock.KEY_LEFT)
        self.assertEqual(win.active_cat_idx, 0) # Apps

    def test_toggle_checkbox(self):
        win = AppManagerWindow(0, 0, 80, 24, self.app)
        initial_state = win.choices["Apps"][0][2]
        win.handle_key(32) # Space
        self.assertNotEqual(win.choices["Apps"][0][2], initial_state)

    def test_save_persists_config(self):
        win = AppManagerWindow(0, 0, 80, 24, self.app)
        win.in_list = False
        win.selected_button = 0 # Save
        
        with mock.patch("retrotui.apps.app_manager.replace", side_effect=lambda x, **kwargs: x):
            win.handle_key(10) # Enter
            
        self.app.persist_config.assert_called_once()
        self.app.refresh_icons.assert_called_once()

if __name__ == "__main__":
    unittest.main()

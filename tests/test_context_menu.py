
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock curses before importing retrotui.ui.context_menu
mock_curses = MagicMock()
mock_curses.KEY_UP = 259
mock_curses.KEY_DOWN = 258
mock_curses.KEY_ENTER = 10
mock_curses.error = Exception
with patch.dict(sys.modules, {'curses': mock_curses}):
    from retrotui.ui.context_menu import ContextMenu

from retrotui.core.actions import AppAction

class TestContextMenu(unittest.TestCase):
    def setUp(self):
        self.theme = MagicMock()
        self.menu = ContextMenu(self.theme)

    def test_show_sets_active_and_position(self):
        items = [{'label': 'Test', 'action': AppAction.EXIT}]
        self.menu.show(10, 5, items)
        self.assertTrue(self.menu.is_open())
        self.assertEqual(self.menu.x, 10)
        self.assertEqual(self.menu.y, 5)
        self.assertEqual(self.menu.items, items)

    def test_hide_resets_state(self):
        self.menu.show(10, 5, [])
        self.menu.hide()
        self.assertFalse(self.menu.is_open())
        self.assertEqual(self.menu.items, [])

    def test_handle_click_inside_activates_action(self):
        items = [{'label': 'Item 1', 'action': AppAction.EXIT}]
        self.menu.show(10, 5, items)
        
        # Click on Item 1 (y = 5 (border) + 1 (item)) = 6
        action = self.menu.handle_click(11, 6)
        self.assertEqual(action, AppAction.EXIT)
        self.assertFalse(self.menu.is_open())

    def test_handle_click_outside_closes_menu(self):
        self.menu.show(10, 5, [{'label': 'Test'}])
        action = self.menu.handle_click(0, 0)
        self.assertIsNone(action)
        self.assertFalse(self.menu.is_open())

    def test_keyboard_navigation(self):
        items = [
            {'label': '1', 'action': 'ACT1'},
            {'label': '2', 'action': 'ACT2'}
        ]
        self.menu.show(0, 0, items)
        
        # Default select 0
        self.assertEqual(self.menu.selected_index, 0)
        
        # Down -> 1
        self.menu.handle_input(258) # KEY_DOWN
        self.assertEqual(self.menu.selected_index, 1)
        
        # Down -> loop to 0
        self.menu.handle_input(258)
        self.assertEqual(self.menu.selected_index, 0)
        
        # Enter -> return action 0
        action = self.menu.handle_input(10)
        self.assertEqual(action, 'ACT1')
        self.assertFalse(self.menu.is_open())

if __name__ == '__main__':
    unittest.main()

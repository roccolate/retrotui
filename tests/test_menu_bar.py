import importlib
import sys
import types
import unittest


def _install_fake_curses():
    fake = types.ModuleType('curses')
    fake.KEY_LEFT = 260
    fake.KEY_RIGHT = 261
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_ENTER = 343
    fake.A_BOLD = 1
    fake.error = Exception
    fake.color_pair = lambda _: 0
    return fake


class MenuBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get('curses')
        sys.modules['curses'] = _install_fake_curses()
        for mod_name in ('retrotui.constants', 'retrotui.utils', 'retrotui.ui.menu'):
            sys.modules.pop(mod_name, None)
        cls.menu_mod = importlib.import_module('retrotui.ui.menu')
        cls.curses = sys.modules['curses']

    @classmethod
    def tearDownClass(cls):
        for mod_name in ('retrotui.constants', 'retrotui.utils', 'retrotui.ui.menu'):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules['curses'] = cls._prev_curses
        else:
            sys.modules.pop('curses', None)

    def test_down_skips_separator(self):
        menu = self.menu_mod.MenuBar(
            {'File': [('Open', 'open'), ('---', None), ('Save', 'save')]}
        )
        menu.active = True
        menu.selected_item = 0

        menu.handle_key(self.curses.KEY_DOWN)
        self.assertEqual(menu.selected_item, 2)

    def test_up_wraps_and_skips_separator(self):
        menu = self.menu_mod.MenuBar(
            {'File': [('Open', 'open'), ('---', None), ('Save', 'save')]}
        )
        menu.active = True
        menu.selected_item = 0

        menu.handle_key(self.curses.KEY_UP)
        self.assertEqual(menu.selected_item, 2)

    def test_left_right_switch_menu_and_reset_selectable(self):
        menu = self.menu_mod.MenuBar(
            {
                'File': [('Open', 'open')],
                'View': [('---', None), ('Refresh', 'refresh')],
            }
        )
        menu.active = True
        menu.selected_menu = 0
        menu.selected_item = 0

        menu.handle_key(self.curses.KEY_RIGHT)
        self.assertEqual(menu.selected_menu, 1)
        self.assertEqual(menu.selected_item, 1)

        menu.handle_key(self.curses.KEY_LEFT)
        self.assertEqual(menu.selected_menu, 0)
        self.assertEqual(menu.selected_item, 0)

    def test_enter_returns_action_and_closes_menu(self):
        menu = self.menu_mod.MenuBar({'File': [('Open', 'open')]})
        menu.active = True
        menu.selected_item = 0

        action = menu.handle_key(10)
        self.assertEqual(action, 'open')
        self.assertFalse(menu.active)

    def test_escape_closes_menu(self):
        menu = self.menu_mod.MenuBar({'File': [('Open', 'open')]})
        menu.active = True

        action = menu.handle_key(27)
        self.assertEqual(action, 'close_menu')
        self.assertFalse(menu.active)

    def test_global_menu_click_flow_returns_app_action(self):
        menu = self.menu_mod.Menu()
        file_x = menu.get_menu_x_positions()[0]

        # Open File dropdown from menu bar click.
        action = menu.handle_click(file_x, 0)
        self.assertIsNone(action)
        self.assertTrue(menu.active)

        # Click first dropdown row (File -> New Window).
        action = menu.handle_click(file_x, 2)
        self.assertEqual(action, self.menu_mod.AppAction.NEW_WINDOW)
        self.assertFalse(menu.active)

    def test_window_menu_click_flow_returns_item_action(self):
        win_x, win_y, win_w = 10, 5, 40
        menu = self.menu_mod.WindowMenu({
            'File': [('Open', 'open'), ('Close', 'close')],
        })
        file_x = menu.get_menu_x_positions(win_x)[0]

        # Open menu from window menu bar.
        action = menu.handle_click(file_x, win_y + 1, win_x, win_y, win_w)
        self.assertIsNone(action)
        self.assertTrue(menu.active)

        # Click first dropdown option.
        action = menu.handle_click(file_x, win_y + 3, win_x, win_y, win_w)
        self.assertEqual(action, 'open')
        self.assertFalse(menu.active)


if __name__ == '__main__':
    unittest.main()

import importlib
import sys
import types
import unittest
from unittest import mock


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
        self.assertIsNone(action)
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

    def test_draw_bar_global_renders_logo_and_clock(self):
        menu = self.menu_mod.MenuBar({'File': [('Open', 'open')]}, mode='global', show_clock=True, show_logo=True)
        menu.active = True
        stdscr = types.SimpleNamespace(getmaxyx=lambda: (24, 80))

        with (
            mock.patch.object(self.menu_mod, 'safe_addstr') as safe_addstr,
            mock.patch.object(self.menu_mod.time, 'strftime', return_value=' 12:34:56 '),
        ):
            menu.draw_bar(stdscr, width=80)

        rendered = [call.args[3] for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertIn(' =', rendered)
        self.assertIn(' 12:34:56 ', rendered)
        self.assertTrue(any(' File ' in text for text in rendered))

    def test_draw_bar_window_mode_returns_when_width_missing(self):
        menu = self.menu_mod.MenuBar({'File': [('Open', 'open')]}, mode='window')
        stdscr = types.SimpleNamespace()

        with mock.patch.object(self.menu_mod, 'safe_addstr') as safe_addstr:
            menu.draw_bar(stdscr, win_x=4, win_y=2, win_w=None, is_active=True)

        safe_addstr.assert_not_called()

    def test_draw_dropdown_inactive_is_noop(self):
        menu = self.menu_mod.MenuBar({'File': [('Open', 'open')]})
        menu.active = False

        with (
            mock.patch.object(self.menu_mod, 'draw_box') as draw_box,
            mock.patch.object(self.menu_mod, 'safe_addstr') as safe_addstr,
        ):
            menu.draw_dropdown(types.SimpleNamespace(), win_x=0, win_y=0, win_w=30)

        draw_box.assert_not_called()
        safe_addstr.assert_not_called()

    def test_dropdown_layout_clamps_inside_window_bounds(self):
        menu = self.menu_mod.WindowMenu({'File': [('Very very long item', 'open')]})
        menu.active = True
        layout = menu._dropdown_layout(win_x=10, win_y=5, win_w=16)

        self.assertIsNotNone(layout)
        x, _, dropdown_w, _ = layout
        window_left = 10 + 2
        right_edge = 10 + 16
        self.assertGreaterEqual(x, 12)
        if dropdown_w + 2 <= (right_edge - window_left):
            self.assertLessEqual(x - 1 + dropdown_w + 2, right_edge)
        else:
            self.assertEqual(x, window_left)

    def test_get_dropdown_rect_and_hit_test(self):
        menu = self.menu_mod.MenuBar({'File': [('Open', 'open')]})
        menu.active = True

        rect = menu.get_dropdown_rect()
        self.assertIsNotNone(rect)
        rx, ry, _, _ = rect
        self.assertTrue(menu.hit_test_dropdown(rx, ry))
        self.assertFalse(menu.hit_test_dropdown(999, 999))

    def test_handle_hover_switches_selected_menu(self):
        menu = self.menu_mod.MenuBar(
            {
                'File': [('Open', 'open')],
                'View': [('---', None), ('Refresh', 'refresh')],
            }
        )
        menu.active = True
        menu.selected_menu = 0
        menu.selected_item = 0
        view_x = menu.get_menu_x_positions()[1]

        handled = menu.handle_hover(view_x, 0)

        self.assertTrue(handled)
        self.assertEqual(menu.selected_menu, 1)
        self.assertEqual(menu.selected_item, 1)

    def test_handle_hover_over_dropdown_updates_item(self):
        menu = self.menu_mod.MenuBar({'File': [('---', None), ('Save', 'save')]})
        menu.active = True
        menu.selected_item = 0
        layout = menu._dropdown_layout()
        self.assertIsNotNone(layout)
        x, y, _, _ = layout

        handled = menu.handle_hover(x, y + 2)

        self.assertTrue(handled)
        self.assertEqual(menu.selected_item, 1)

    def test_handle_hover_outside_returns_false(self):
        menu = self.menu_mod.MenuBar({'File': [('Open', 'open')]})
        menu.active = True

        self.assertFalse(menu.handle_hover(200, 200))

    def test_handle_click_same_menu_toggles_inactive(self):
        menu = self.menu_mod.MenuBar({'File': [('Open', 'open')]})
        menu.active = True
        menu.selected_menu = 0
        file_x = menu.get_menu_x_positions()[0]

        action = menu.handle_click(file_x, 0)

        self.assertIsNone(action)
        self.assertFalse(menu.active)

    def test_handle_click_outside_dropdown_closes_menu(self):
        menu = self.menu_mod.MenuBar({'File': [('Open', 'open')]})
        menu.active = True

        action = menu.handle_click(999, 999)

        self.assertIsNone(action)
        self.assertFalse(menu.active)

    def test_handle_key_returns_none_when_inactive(self):
        menu = self.menu_mod.MenuBar({'File': [('Open', 'open')]})
        menu.active = False
        menu.selected_item = 0

        result = menu.handle_key(10)

        self.assertIsNone(result)
        self.assertFalse(menu.active)

    def test_enter_on_separator_keeps_menu_open(self):
        menu = self.menu_mod.MenuBar({'File': [('---', None), ('Save', 'save')]})
        menu.active = True
        menu.selected_item = 0

        result = menu.handle_key(10)

        self.assertIsNone(result)
        self.assertTrue(menu.active)

    def test_current_items_empty_when_no_menu_names(self):
        menu = self.menu_mod.MenuBar({})
        self.assertEqual(menu._current_items(), [])

    def test_first_selectable_returns_zero_when_no_actions(self):
        idx = self.menu_mod.MenuBar._first_selectable([("---", None), ("___", None)])
        self.assertEqual(idx, 0)

    def test_dropdown_layout_none_when_no_menus(self):
        menu = self.menu_mod.MenuBar({})
        self.assertIsNone(menu._dropdown_layout())

    def test_move_selected_item_no_items_is_noop(self):
        menu = self.menu_mod.MenuBar({"File": []})
        menu.selected_item = 3
        menu._move_selected_item(1)
        self.assertEqual(menu.selected_item, 3)

    def test_draw_bar_global_uses_stdscr_width_when_not_provided(self):
        menu = self.menu_mod.MenuBar({"File": [("Open", "open")]}, mode="global")
        stdscr = types.SimpleNamespace(getmaxyx=lambda: (24, 50))
        with mock.patch.object(self.menu_mod, "safe_addstr") as safe_addstr:
            menu.draw_bar(stdscr, width=None)

        self.assertTrue(safe_addstr.called)

    def test_draw_bar_window_mode_renders_inner_strip(self):
        menu = self.menu_mod.MenuBar({"File": [("Open", "open")]}, mode="window")
        stdscr = types.SimpleNamespace()
        with mock.patch.object(self.menu_mod, "safe_addstr") as safe_addstr:
            menu.draw_bar(stdscr, win_x=4, win_y=2, win_w=20, is_active=True)

        self.assertTrue(safe_addstr.called)

    def test_draw_dropdown_active_renders_separator_and_action_rows(self):
        menu = self.menu_mod.MenuBar({"File": [("---", None), ("Save", "save")]})
        menu.active = True
        menu.selected_item = 1
        with (
            mock.patch.object(self.menu_mod, "draw_box") as draw_box,
            mock.patch.object(self.menu_mod, "safe_addstr") as safe_addstr,
        ):
            menu.draw_dropdown(types.SimpleNamespace())

        draw_box.assert_called_once()
        rendered = [call.args[3] for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any(isinstance(text, str) and "Save" in text for text in rendered))

    def test_draw_dropdown_active_with_no_menus_is_noop(self):
        menu = self.menu_mod.MenuBar({})
        menu.active = True
        with (
            mock.patch.object(self.menu_mod, "draw_box") as draw_box,
            mock.patch.object(self.menu_mod, "safe_addstr") as safe_addstr,
        ):
            menu.draw_dropdown(types.SimpleNamespace())
        draw_box.assert_not_called()
        safe_addstr.assert_not_called()

    def test_get_dropdown_rect_returns_none_with_active_empty_menu(self):
        menu = self.menu_mod.MenuBar({})
        menu.active = True
        self.assertIsNone(menu.get_dropdown_rect())

    def test_get_dropdown_rect_returns_none_when_inactive(self):
        menu = self.menu_mod.MenuBar({"File": [("Open", "open")]})
        menu.active = False
        self.assertIsNone(menu.get_dropdown_rect())

    def test_hit_test_dropdown_returns_false_when_rect_missing(self):
        menu = self.menu_mod.MenuBar({})
        menu.active = True
        self.assertFalse(menu.hit_test_dropdown(0, 0))

    def test_handle_hover_inactive_returns_false(self):
        menu = self.menu_mod.MenuBar({"File": [("Open", "open")]})
        menu.active = False
        self.assertFalse(menu.handle_hover(2, 0))

    def test_handle_hover_on_bar_without_item_match_uses_bar_hit_test(self):
        menu = self.menu_mod.WindowMenu({"File": [("Open", "open")]})
        menu.active = True
        handled = menu.handle_hover(mx=27, my=6, win_x=10, win_y=5, win_w=20)
        self.assertTrue(handled)

    def test_handle_click_on_bar_without_item_closes_menu(self):
        menu = self.menu_mod.WindowMenu({"File": [("Open", "open")]})
        menu.active = True
        action = menu.handle_click(mx=27, my=6, win_x=10, win_y=5, win_w=20)
        self.assertIsNone(action)
        self.assertFalse(menu.active)

    def test_handle_click_active_with_missing_layout_closes_menu(self):
        menu = self.menu_mod.MenuBar({})
        menu.active = True
        action = menu.handle_click(5, 3)
        self.assertIsNone(action)
        self.assertFalse(menu.active)

    def test_handle_key_enter_with_empty_items_returns_none(self):
        menu = self.menu_mod.MenuBar({"File": []})
        menu.active = True
        result = menu.handle_key(10)
        self.assertIsNone(result)
        self.assertTrue(menu.active)

    def test_handle_key_unknown_returns_none(self):
        menu = self.menu_mod.MenuBar({"File": [("Open", "open")]})
        menu.active = True
        self.assertIsNone(menu.handle_key(999))

    def test_menu_wrapper_methods_delegate_to_base_class(self):
        menu = self.menu_mod.Menu()
        stdscr = types.SimpleNamespace()
        with (
            mock.patch.object(self.menu_mod.MenuBar, "draw_bar", return_value=None) as draw_bar,
            mock.patch.object(self.menu_mod.MenuBar, "draw_dropdown", return_value=None) as draw_dropdown,
            mock.patch.object(self.menu_mod.MenuBar, "get_dropdown_rect", return_value=(1, 2, 3, 4)) as get_rect,
            mock.patch.object(self.menu_mod.MenuBar, "hit_test_dropdown", return_value=True) as hit_test,
            mock.patch.object(self.menu_mod.MenuBar, "handle_hover", return_value=True) as hover,
        ):
            menu.draw_bar(stdscr, 80)
            menu.draw_dropdown(stdscr)
            rect = menu.get_dropdown_rect()
            inside = menu.hit_test_dropdown(1, 2)
            handled = menu.handle_hover(1, 0)

        draw_bar.assert_called_once()
        draw_dropdown.assert_called_once()
        get_rect.assert_called_once()
        hit_test.assert_called_once()
        hover.assert_called_once()
        self.assertEqual(rect, (1, 2, 3, 4))
        self.assertTrue(inside)
        self.assertTrue(handled)

    def test_menu_wrapper_accepts_optional_window_kwargs(self):
        menu = self.menu_mod.Menu()
        menu.active = False
        self.assertIsNone(menu.get_dropdown_rect(win_x=0, win_y=0, win_w=80))
        self.assertFalse(menu.hit_test_dropdown(1, 1, win_x=0, win_y=0, win_w=80))
        self.assertFalse(menu.handle_hover(1, 1, win_x=0, win_y=0, win_w=80))
        self.assertIsNone(menu.handle_click(1, 1, win_x=0, win_y=0, win_w=80))

    def test_window_menu_wrapper_methods_delegate_to_base_class(self):
        menu = self.menu_mod.WindowMenu({"File": [("Open", "open")]})
        stdscr = types.SimpleNamespace()

        self.assertEqual(menu.menu_bar_row(5), 6)

        with (
            mock.patch.object(self.menu_mod.MenuBar, "draw_bar", return_value=None) as draw_bar,
            mock.patch.object(self.menu_mod.MenuBar, "handle_hover", return_value=True) as hover,
        ):
            menu.draw_bar(stdscr, 10, 5, 40, True)
            handled = menu.handle_hover(12, 6, 10, 5, 40)

        draw_bar.assert_called_once()
        hover.assert_called_once()
        self.assertTrue(handled)


if __name__ == '__main__':
    unittest.main()

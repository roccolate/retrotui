import types
import unittest
from unittest import mock

from retrotui.constants import BOTTOM_BARS_HEIGHT, MENU_BAR_HEIGHT
from retrotui.core import rendering
from retrotui.core.shell_geometry import (
    global_bar_row,
    workspace_bottom_exclusive,
    workspace_top_row,
)
from retrotui.ui.menu import Menu
from retrotui.ui.window import Window


class ClassicBottomTaskbarTests(unittest.TestCase):
    def test_workspace_reserves_one_bottom_row(self):
        self.assertEqual(MENU_BAR_HEIGHT, 0)
        self.assertEqual(BOTTOM_BARS_HEIGHT, 1)
        self.assertEqual(workspace_top_row(), 0)
        self.assertEqual(global_bar_row(24), 23)
        self.assertEqual(workspace_bottom_exclusive(24), 23)

    def test_global_menu_draws_on_bottom_and_opens_upward(self):
        menu = Menu({"File": [("Open", "open"), ("Exit", "exit")]})
        menu.active = True
        stdscr = types.SimpleNamespace(
            getmaxyx=lambda: (24, 80),
            addnstr=mock.Mock(),
        )

        with mock.patch("retrotui.ui.menu.draw_box"):
            menu.draw_bar(stdscr, 80, frame_size=(24, 80))
            menu.draw_dropdown(stdscr, frame_size=(24, 80))

        self.assertEqual(menu.bar_row(), 23)
        self.assertTrue(
            any(call.args[0] == 23 for call in stdscr.addnstr.call_args_list)
        )
        rect = menu.get_dropdown_rect()
        self.assertIsNotNone(rect)
        _x, y, _w, h = rect
        self.assertEqual(y + h, 23)

    def test_start_button_click_uses_bottom_row(self):
        menu = Menu({"File": [("Open", "open")]})
        stdscr = types.SimpleNamespace(
            getmaxyx=lambda: (24, 80),
            addnstr=mock.Mock(),
        )
        menu.draw_bar(stdscr, 80, frame_size=(24, 80))

        result = menu.handle_click(1, 23)

        self.assertIsNone(result)
        self.assertTrue(menu.active)
        self.assertEqual(menu.selected_menu, 0)
        self.assertFalse(menu.hit_test_menu_item(1, 0))

    def test_taskbar_buttons_render_on_bottom_row(self):
        stdscr = types.SimpleNamespace(getmaxyx=lambda: (20, 80))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=[types.SimpleNamespace(minimized=True, title="Notes")],
            menu=types.SimpleNamespace(
                menu_items_right_x=lambda: 20,
                right_reserved_start_x=lambda width: 70,
            ),
        )

        with mock.patch.object(rendering, "safe_addstr") as safe_addstr:
            rendering.draw_taskbar(app)

        self.assertTrue(
            any(
                call.args[1] == 19 and call.args[3] == "[Notes]"
                for call in safe_addstr.call_args_list
            )
        )

    def test_maximized_window_uses_workspace_above_taskbar(self):
        window = Window("Test", 5, 4, 30, 10)

        window.toggle_maximize(80, 24)

        self.assertEqual(window.y, 0)
        self.assertEqual(window.h, 23)
        self.assertEqual(window.y + window.h, global_bar_row(24))


if __name__ == "__main__":
    unittest.main()

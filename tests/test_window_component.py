import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_PPAGE = 339
    fake.KEY_NPAGE = 338
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.color_pair = lambda value: value * 10
    fake.error = Exception
    return fake


class WindowComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
        ):
            sys.modules.pop(mod_name, None)

        cls.window_mod = importlib.import_module("retrotui.ui.window")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_body_rect_with_and_without_window_menu(self):
        win = self.window_mod.Window("Test", 5, 4, 30, 12)
        self.assertEqual(win.body_rect(), (6, 5, 28, 10))

        win.window_menu = mock.Mock()
        self.assertEqual(win.body_rect(), (6, 7, 28, 8))
        self.assertEqual(win.close_button_pos(), (31, 4))

    def test_contains_and_hit_regions(self):
        win = self.window_mod.Window("Test", 10, 3, 20, 10)

        self.assertTrue(win.contains(10, 3))
        self.assertTrue(win.contains(29, 12))
        self.assertFalse(win.contains(30, 12))
        self.assertTrue(win.on_close_button(27, 3))
        self.assertTrue(win.on_minimize_button(21, 3))
        self.assertTrue(win.on_maximize_button(24, 3))
        self.assertFalse(win.on_title_bar(27, 3))  # close button area excluded
        self.assertFalse(win.on_title_bar(25, 3))  # min/max area excluded
        self.assertTrue(win.on_title_bar(18, 3))
        self.assertFalse(win.on_title_bar(18, 4))
        self.assertFalse(win.on_title_bar(9, 3))   # outside title horizontal range

    def test_toggle_maximize_and_restore_with_clamp(self):
        win = self.window_mod.Window("Test", 12, 8, 40, 14)
        win.window_menu = types.SimpleNamespace(active=True)

        win.toggle_maximize(120, 40)
        self.assertTrue(win.maximized)
        self.assertEqual((win.x, win.y, win.w, win.h), (0, 1, 120, 38))
        self.assertFalse(win.window_menu.active)

        win.restore_rect = (200, 100, 50, 20)
        win.toggle_maximize(100, 40)
        self.assertFalse(win.maximized)
        self.assertEqual((win.x, win.y), (50, 19))

    def test_toggle_minimize_updates_visibility_and_active(self):
        win = self.window_mod.Window("Test", 0, 0, 20, 10)
        win.active = True
        win.window_menu = types.SimpleNamespace(active=True)

        win.toggle_minimize()
        self.assertTrue(win.minimized)
        self.assertFalse(win.visible)
        self.assertFalse(win.active)
        self.assertFalse(win.window_menu.active)

        win.toggle_minimize()
        self.assertFalse(win.minimized)
        self.assertTrue(win.visible)
        self.assertTrue(win.active)

    def test_border_detection_and_resize_application(self):
        win = self.window_mod.Window("Test", 10, 5, 20, 10)
        self.assertEqual(win.on_border(29, 14), "corner")
        self.assertEqual(win.on_border(29, 8), "right")
        self.assertEqual(win.on_border(12, 14), "bottom")
        self.assertIsNone(win.on_border(12, 8))

        win.resizable = False
        self.assertIsNone(win.on_border(29, 14))
        win.resizable = True
        win.maximized = True
        self.assertIsNone(win.on_border(29, 14))
        win.maximized = False

        win.window_menu = types.SimpleNamespace(active=True)
        win.resize_edge = "right"
        win.apply_resize(mx=200, my=10, term_w=100, term_h=40)
        self.assertEqual(win.w, 90)  # clamped by term_w - x

        win.resize_edge = "bottom"
        win.apply_resize(mx=12, my=200, term_w=100, term_h=40)
        self.assertEqual(win.h, 34)  # clamped by term_h - y - 1
        self.assertFalse(win.window_menu.active)

    def test_draw_frame_and_draw_body_render_expected_paths(self):
        win = self.window_mod.Window("Demo", 2, 1, 24, 8, content=["a", "b", "c", "d", "e"])
        win.active = True
        win.window_menu = types.SimpleNamespace(
            active=True,
            draw_bar=mock.Mock(),
            draw_dropdown=mock.Mock(),
        )
        stdscr = types.SimpleNamespace()

        with (
            mock.patch.object(self.window_mod, "draw_box") as draw_box,
            mock.patch.object(self.window_mod, "safe_addstr") as safe_addstr,
        ):
            body_attr = win.draw_frame(stdscr)
            win.scroll_offset = 1
            win.draw_body(stdscr, body_attr)
            win.draw(stdscr)

        self.assertEqual(body_attr, self.curses.color_pair(self.window_mod.C_WIN_BODY))
        draw_box.assert_called()
        self.assertTrue(any("[[" not in str(call.args[3]) for call in safe_addstr.call_args_list))
        self.assertTrue(
            any(call.args[1] == win.y + 2 and call.args[2] == win.x for call in safe_addstr.call_args_list)
        )
        win.window_menu.draw_bar.assert_called()
        win.window_menu.draw_dropdown.assert_called()

    def test_draw_returns_early_when_window_is_hidden(self):
        win = self.window_mod.Window("Hidden", 1, 1, 20, 8)
        win.visible = False
        stdscr = types.SimpleNamespace()
        win.draw_frame = mock.Mock()
        win.draw_body = mock.Mock()

        win.draw(stdscr)

        win.draw_frame.assert_not_called()
        win.draw_body.assert_not_called()

    def test_draw_frame_returns_zero_when_hidden(self):
        win = self.window_mod.Window("Hidden", 1, 1, 20, 8)
        win.visible = False
        self.assertEqual(win.draw_frame(types.SimpleNamespace()), 0)

    def test_draw_frame_inactive_uses_inactive_body_attr(self):
        win = self.window_mod.Window("Inactive", 1, 1, 20, 8)
        win.active = False
        with (
            mock.patch.object(self.window_mod, "draw_box"),
            mock.patch.object(self.window_mod, "safe_addstr"),
        ):
            body_attr = win.draw_frame(types.SimpleNamespace())
        self.assertEqual(body_attr, self.curses.color_pair(self.window_mod.C_WIN_INACTIVE))

    def test_default_key_and_scroll_handlers(self):
        win = self.window_mod.Window("Scroll", 0, 0, 20, 8, content=[str(i) for i in range(30)])
        win.scroll_offset = 5

        win.handle_key(self.curses.KEY_UP)
        self.assertEqual(win.scroll_offset, 4)
        win.handle_key(self.curses.KEY_NPAGE)
        self.assertEqual(win.scroll_offset, 5)

        win.handle_scroll("down", steps=3)
        self.assertEqual(win.scroll_offset, 8)
        win.handle_scroll("up", steps=2)
        self.assertEqual(win.scroll_offset, 6)

        self.assertIsNone(win.handle_click(1, 1))


if __name__ == "__main__":
    unittest.main()

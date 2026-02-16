import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.REPORT_MOUSE_POSITION = 0x200000
    fake.BUTTON1_CLICKED = 0x0004
    fake.BUTTON1_PRESSED = 0x0002
    fake.BUTTON1_DOUBLE_CLICKED = 0x0008
    fake.BUTTON4_PRESSED = 0x100000
    return fake


class MouseRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        sys.modules.pop("retrotui.core.mouse_router", None)
        cls.mouse_router = importlib.import_module("retrotui.core.mouse_router")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("retrotui.core.mouse_router", None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_app(self):
        click_flags = (
            self.curses.BUTTON1_CLICKED
            | self.curses.BUTTON1_PRESSED
            | self.curses.BUTTON1_DOUBLE_CLICKED
        )
        return types.SimpleNamespace(
            windows=[],
            stdscr=types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(25, 80))),
            stop_drag_flags=0xFFFF,
            click_flags=click_flags,
            scroll_down_mask=0x200000,
            menu=types.SimpleNamespace(
                active=False,
                handle_hover=mock.Mock(),
                handle_click=mock.Mock(return_value=None),
                hit_test_dropdown=mock.Mock(return_value=False),
            ),
            execute_action=mock.Mock(),
            set_active_window=mock.Mock(),
            close_window=mock.Mock(),
            handle_taskbar_click=mock.Mock(return_value=False),
            _dispatch_window_result=mock.Mock(),
            get_icon_at=mock.Mock(return_value=-1),
            icons=[{"action": "about"}],
            selected_icon=-1,
            _handle_dialog_mouse=mock.Mock(return_value=False),
            _handle_drag_resize_mouse=mock.Mock(return_value=False),
            _handle_global_menu_mouse=mock.Mock(return_value=False),
            _handle_window_mouse=mock.Mock(return_value=False),
            _handle_desktop_mouse=mock.Mock(),
        )

    def _make_window(self, **overrides):
        base = dict(
            visible=True,
            active=False,
            minimized=False,
            maximized=False,
            x=4,
            y=4,
            w=20,
            h=10,
            dragging=False,
            drag_offset_x=0,
            drag_offset_y=0,
            resizing=False,
            resize_edge=None,
            on_close_button=mock.Mock(return_value=False),
            on_minimize_button=mock.Mock(return_value=False),
            on_maximize_button=mock.Mock(return_value=False),
            on_border=mock.Mock(return_value=None),
            on_title_bar=mock.Mock(return_value=False),
            contains=mock.Mock(return_value=False),
            toggle_minimize=mock.Mock(),
            toggle_maximize=mock.Mock(),
            handle_click=mock.Mock(return_value=None),
            handle_scroll=mock.Mock(),
            window_menu=None,
        )
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def test_handle_drag_resize_mouse_moves_dragging_window(self):
        app = self._make_app()
        win = types.SimpleNamespace(
            dragging=True,
            drag_offset_x=2,
            drag_offset_y=1,
            resizing=False,
            resize_edge=None,
            w=10,
            h=5,
            x=0,
            y=0,
            apply_resize=mock.Mock(),
        )
        app.windows = [win]

        handled = self.mouse_router.handle_drag_resize_mouse(app, 20, 10, 0)

        self.assertTrue(handled)
        self.assertEqual(win.x, 18)
        self.assertEqual(win.y, 9)

    def test_handle_drag_resize_mouse_stops_dragging(self):
        app = self._make_app()
        win = types.SimpleNamespace(
            dragging=True,
            drag_offset_x=0,
            drag_offset_y=0,
            resizing=False,
            resize_edge=None,
            w=10,
            h=5,
            x=3,
            y=3,
            apply_resize=mock.Mock(),
        )
        app.windows = [win]

        handled = self.mouse_router.handle_drag_resize_mouse(app, 0, 0, app.stop_drag_flags)

        self.assertTrue(handled)
        self.assertFalse(win.dragging)

    def test_handle_drag_resize_mouse_drag_state_changes_mid_pass(self):
        app = self._make_app()

        class FlakyDragWindow:
            def __init__(self):
                self._reads = 0
                self.drag_offset_x = 0
                self.drag_offset_y = 0
                self.resizing = False
                self.resize_edge = None
                self.w = 10
                self.h = 5
                self.x = 0
                self.y = 0
                self.apply_resize = mock.Mock()

            @property
            def dragging(self):
                self._reads += 1
                return self._reads == 1

            @dragging.setter
            def dragging(self, value):
                self._reads = 99 if value else 0

        app.windows = [FlakyDragWindow()]
        handled = self.mouse_router.handle_drag_resize_mouse(app, 5, 5, 0)
        self.assertTrue(handled)

    def test_handle_drag_resize_mouse_stops_resizing(self):
        app = self._make_app()
        win = types.SimpleNamespace(
            dragging=False,
            resizing=True,
            resize_edge="right",
            apply_resize=mock.Mock(),
        )
        app.windows = [win]

        handled = self.mouse_router.handle_drag_resize_mouse(app, 0, 0, app.stop_drag_flags)

        self.assertTrue(handled)
        self.assertFalse(win.resizing)
        self.assertIsNone(win.resize_edge)

    def test_handle_drag_resize_mouse_resizes_active_window(self):
        app = self._make_app()
        win = types.SimpleNamespace(
            dragging=False,
            resizing=True,
            resize_edge="right",
            apply_resize=mock.Mock(),
        )
        app.windows = [win]

        handled = self.mouse_router.handle_drag_resize_mouse(app, 15, 9, 0)

        self.assertTrue(handled)
        win.apply_resize.assert_called_once_with(15, 9, 80, 25)

    def test_handle_drag_resize_mouse_resize_state_changes_mid_pass(self):
        app = self._make_app()

        class FlakyResizeWindow:
            def __init__(self):
                self.dragging = False
                self._reads = 0
                self.resize_edge = "right"
                self.apply_resize = mock.Mock()

            @property
            def resizing(self):
                self._reads += 1
                return self._reads == 1

            @resizing.setter
            def resizing(self, value):
                self._reads = 99 if value else 0

        app.windows = [FlakyResizeWindow()]
        handled = self.mouse_router.handle_drag_resize_mouse(app, 8, 8, 0)
        self.assertTrue(handled)

    def test_handle_global_menu_mouse_hover_calls_menu_hover(self):
        app = self._make_app()
        app.menu.active = True

        handled = self.mouse_router.handle_global_menu_mouse(
            app, 8, 2, self.curses.REPORT_MOUSE_POSITION
        )

        self.assertTrue(handled)
        app.menu.handle_hover.assert_called_once_with(8, 2)

    def test_handle_global_menu_mouse_click_executes_action(self):
        app = self._make_app()
        app.menu.active = True
        app.menu.handle_click.return_value = "settings"

        handled = self.mouse_router.handle_global_menu_mouse(
            app, 3, 0, self.curses.BUTTON1_CLICKED
        )

        self.assertTrue(handled)
        app.execute_action.assert_called_once_with("settings")

    def test_handle_global_menu_mouse_hit_test_without_click_returns_true(self):
        app = self._make_app()
        app.menu.active = True
        app.menu.hit_test_dropdown.return_value = True

        handled = self.mouse_router.handle_global_menu_mouse(app, 5, 7, 0)

        self.assertTrue(handled)
        app.menu.handle_click.assert_not_called()

    def test_handle_global_menu_mouse_returns_false_when_no_hit(self):
        app = self._make_app()
        app.menu.active = True

        handled = self.mouse_router.handle_global_menu_mouse(app, 40, 12, 0)

        self.assertFalse(handled)

    def test_handle_window_mouse_close_button_closes_window(self):
        app = self._make_app()
        win = types.SimpleNamespace(
            visible=True,
            on_close_button=mock.Mock(return_value=True),
            on_minimize_button=mock.Mock(return_value=False),
            on_maximize_button=mock.Mock(return_value=False),
            on_border=mock.Mock(return_value=None),
            on_title_bar=mock.Mock(return_value=False),
            window_menu=None,
            contains=mock.Mock(return_value=False),
        )
        app.windows = [win]

        handled = self.mouse_router.handle_window_mouse(app, 5, 5, app.click_flags)

        self.assertTrue(handled)
        app.close_window.assert_called_once_with(win)

    def test_handle_window_mouse_minimize_activates_last_visible(self):
        app = self._make_app()
        win1 = self._make_window(on_minimize_button=mock.Mock(return_value=True))
        win2 = self._make_window(visible=True)
        app.windows = [win2, win1]

        handled = self.mouse_router.handle_window_mouse(app, 5, 5, app.click_flags)

        self.assertTrue(handled)
        win1.toggle_minimize.assert_called_once()
        self.assertGreaterEqual(app.set_active_window.call_count, 2)

    def test_handle_window_mouse_maximize_calls_toggle(self):
        app = self._make_app()
        win = self._make_window(on_maximize_button=mock.Mock(return_value=True))
        app.windows = [win]

        handled = self.mouse_router.handle_window_mouse(app, 5, 5, app.click_flags)

        self.assertTrue(handled)
        win.toggle_maximize.assert_called_once_with(80, 25)

    def test_handle_window_mouse_skips_invisible_windows(self):
        app = self._make_app()
        hidden = self._make_window(visible=False, on_close_button=mock.Mock(return_value=True))
        visible = self._make_window(on_close_button=mock.Mock(return_value=True))
        app.windows = [hidden, visible]

        handled = self.mouse_router.handle_window_mouse(app, 5, 5, app.click_flags)

        self.assertTrue(handled)
        hidden.on_close_button.assert_not_called()
        app.close_window.assert_called_once_with(visible)

    def test_handle_window_mouse_all_invisible_windows_returns_false(self):
        app = self._make_app()
        app.windows = [self._make_window(visible=False)]

        handled = self.mouse_router.handle_window_mouse(app, 5, 5, app.click_flags)

        self.assertFalse(handled)

    def test_handle_window_mouse_border_starts_resize(self):
        app = self._make_app()
        win = self._make_window(on_border=mock.Mock(return_value="right"))
        app.windows = [win]

        handled = self.mouse_router.handle_window_mouse(app, 10, 10, self.curses.BUTTON1_PRESSED)

        self.assertTrue(handled)
        self.assertTrue(win.resizing)
        self.assertEqual(win.resize_edge, "right")

    def test_handle_window_mouse_title_double_click_toggles_maximize(self):
        app = self._make_app()
        win = self._make_window(on_title_bar=mock.Mock(return_value=True))
        app.windows = [win]

        handled = self.mouse_router.handle_window_mouse(app, 10, 10, self.curses.BUTTON1_DOUBLE_CLICKED)

        self.assertTrue(handled)
        win.toggle_maximize.assert_called_once_with(80, 25)

    def test_handle_window_mouse_title_press_starts_drag_when_not_maximized(self):
        app = self._make_app()
        win = self._make_window(on_title_bar=mock.Mock(return_value=True), maximized=False, x=6, y=2)
        app.windows = [win]

        handled = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.BUTTON1_PRESSED)

        self.assertTrue(handled)
        self.assertTrue(win.dragging)
        self.assertEqual(win.drag_offset_x, 5)
        self.assertEqual(win.drag_offset_y, 5)

    def test_handle_window_mouse_title_press_does_not_drag_when_maximized(self):
        app = self._make_app()
        win = self._make_window(on_title_bar=mock.Mock(return_value=True), maximized=True)
        app.windows = [win]

        handled = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.BUTTON1_PRESSED)

        self.assertTrue(handled)
        self.assertFalse(win.dragging)

    def test_handle_window_mouse_title_single_click_activates_only(self):
        app = self._make_app()
        win = self._make_window(on_title_bar=mock.Mock(return_value=True))
        app.windows = [win]

        handled = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.BUTTON1_CLICKED)

        self.assertTrue(handled)
        self.assertFalse(win.dragging)
        app.set_active_window.assert_called_once_with(win)

    def test_handle_window_mouse_menu_hover_path(self):
        app = self._make_app()
        menu = types.SimpleNamespace(active=True, handle_hover=mock.Mock(return_value=True))
        win = self._make_window(window_menu=menu)
        app.windows = [win]

        handled = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.REPORT_MOUSE_POSITION)

        self.assertTrue(handled)
        menu.handle_hover.assert_called_once_with(11, 7, win.x, win.y, win.w)

    def test_handle_window_mouse_click_outside_closes_active_window_menu(self):
        app = self._make_app()
        menu = types.SimpleNamespace(active=True, handle_hover=mock.Mock(return_value=False))
        win = self._make_window(window_menu=menu, contains=mock.Mock(return_value=False))
        app.windows = [win]

        handled = self.mouse_router.handle_window_mouse(app, 1, 1, self.curses.BUTTON1_CLICKED)

        self.assertFalse(handled)
        self.assertFalse(menu.active)

    def test_handle_window_mouse_contains_click_evaluates_other_window_condition(self):
        app = self._make_app()
        win = self._make_window(
            contains=mock.Mock(return_value=True),
            handle_click=mock.Mock(return_value=None),
            window_menu=types.SimpleNamespace(active=False, handle_hover=mock.Mock(return_value=False)),
        )
        other = self._make_window(window_menu=types.SimpleNamespace(active=True))
        app.windows = [other, win]

        handled = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.BUTTON1_CLICKED)

        self.assertTrue(handled)
        self.assertFalse(other.window_menu.active)

    def test_handle_window_mouse_contains_click_checks_multiple_other_windows(self):
        app = self._make_app()
        win = self._make_window(
            contains=mock.Mock(return_value=True),
            handle_click=mock.Mock(return_value=None),
            window_menu=types.SimpleNamespace(active=False, handle_hover=mock.Mock(return_value=False)),
        )
        other_active = self._make_window(window_menu=types.SimpleNamespace(active=True))
        other_inactive = self._make_window(window_menu=types.SimpleNamespace(active=False))
        app.windows = [other_inactive, other_active, win]

        handled = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.BUTTON1_CLICKED)

        self.assertTrue(handled)
        self.assertFalse(other_active.window_menu.active)

    def test_handle_window_mouse_click_inside_dispatches_result_and_closes_other_menus(self):
        app = self._make_app()
        active_menu = types.SimpleNamespace(active=True)
        win = self._make_window(
            contains=mock.Mock(return_value=True),
            handle_click=mock.Mock(return_value="result"),
            window_menu=types.SimpleNamespace(active=True, handle_hover=mock.Mock(return_value=False)),
        )
        other = self._make_window(window_menu=active_menu)
        app.windows = [other, win]

        handled = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.BUTTON1_CLICKED)

        self.assertTrue(handled)
        self.assertFalse(active_menu.active)
        app._dispatch_window_result.assert_called_once_with("result", win)

    def test_handle_window_mouse_scroll_paths(self):
        app = self._make_app()
        win = self._make_window(contains=mock.Mock(return_value=True))
        app.windows = [win]

        handled_up = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.BUTTON4_PRESSED)
        handled_down = self.mouse_router.handle_window_mouse(app, 11, 7, app.scroll_down_mask)

        self.assertTrue(handled_up)
        self.assertTrue(handled_down)
        self.assertEqual(win.handle_scroll.call_args_list[0].args, ("up", 3))
        self.assertEqual(win.handle_scroll.call_args_list[1].args, ("down", 3))

    def test_handle_desktop_mouse_double_click_executes_icon_action(self):
        app = self._make_app()
        app.get_icon_at.return_value = 0

        handled = self.mouse_router.handle_desktop_mouse(
            app, 9, 9, self.curses.BUTTON1_DOUBLE_CLICKED
        )

        self.assertTrue(handled)
        app.execute_action.assert_called_once_with("about")

    def test_handle_desktop_mouse_deselects_when_no_icon_hit(self):
        app = self._make_app()

        handled = self.mouse_router.handle_desktop_mouse(app, 30, 10, 0)

        self.assertTrue(handled)
        self.assertEqual(app.selected_icon, -1)
        self.assertFalse(app.menu.active)

    def test_handle_mouse_event_top_bar_click_executes_action(self):
        app = self._make_app()
        app.menu.handle_click.return_value = "about"

        self.mouse_router.handle_mouse_event(
            app, (0, 12, 0, 0, self.curses.BUTTON1_CLICKED)
        )

        app.execute_action.assert_called_once_with("about")
        app._handle_drag_resize_mouse.assert_not_called()
        app._handle_window_mouse.assert_not_called()
        app._handle_desktop_mouse.assert_not_called()

    def test_handle_mouse_event_falls_back_to_desktop(self):
        app = self._make_app()

        self.mouse_router.handle_mouse_event(
            app, (0, 12, 5, 0, self.curses.BUTTON1_CLICKED)
        )

        app._handle_desktop_mouse.assert_called_once_with(12, 5, self.curses.BUTTON1_CLICKED)

    def test_handle_mouse_event_dialog_has_priority(self):
        app = self._make_app()
        app._handle_dialog_mouse.return_value = True

        self.mouse_router.handle_mouse_event(app, (0, 3, 3, 0, self.curses.BUTTON1_CLICKED))

        app._handle_drag_resize_mouse.assert_not_called()
        app._handle_window_mouse.assert_not_called()
        app._handle_desktop_mouse.assert_not_called()

    def test_handle_mouse_event_taskbar_short_circuit(self):
        app = self._make_app()
        app.handle_taskbar_click.return_value = True

        self.mouse_router.handle_mouse_event(app, (0, 3, 3, 0, self.curses.BUTTON1_CLICKED))

        app._handle_window_mouse.assert_not_called()
        app._handle_desktop_mouse.assert_not_called()

    def test_handle_mouse_event_stops_after_drag_resize_handler(self):
        app = self._make_app()
        app._handle_drag_resize_mouse.return_value = True

        self.mouse_router.handle_mouse_event(app, (0, 3, 3, 0, self.curses.BUTTON1_CLICKED))

        app._handle_global_menu_mouse.assert_not_called()
        app._handle_window_mouse.assert_not_called()
        app._handle_desktop_mouse.assert_not_called()

    def test_handle_mouse_event_stops_after_global_menu_handler(self):
        app = self._make_app()
        app._handle_global_menu_mouse.return_value = True

        self.mouse_router.handle_mouse_event(app, (0, 3, 3, 0, self.curses.BUTTON1_CLICKED))

        app._handle_window_mouse.assert_not_called()
        app._handle_desktop_mouse.assert_not_called()

    def test_handle_mouse_event_stops_after_window_handler(self):
        app = self._make_app()
        app._handle_window_mouse.return_value = True

        self.mouse_router.handle_mouse_event(app, (0, 3, 3, 0, self.curses.BUTTON1_CLICKED))

        app._handle_desktop_mouse.assert_not_called()


if __name__ == "__main__":
    unittest.main()

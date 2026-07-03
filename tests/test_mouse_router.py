import importlib
import inspect as py_inspect
import os
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
    fake.BUTTON1_RELEASED = 0x0001
    fake.BUTTON3_CLICKED = 0x0010
    fake.BUTTON3_PRESSED = 0x0020
    fake.BUTTON3_RELEASED = 0x0040
    fake.BUTTON4_PRESSED = 0x100000
    return fake


class MouseRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        sys.modules.pop("retrotui.core.platform.mouse_backend", None)
        sys.modules.pop("retrotui.core.mouse_router", None)
        sys.modules.pop("retrotui.core.drag_drop", None)
        cls.mouse_router = importlib.import_module("retrotui.core.mouse_router")
        cls.drag_drop_mod = importlib.import_module("retrotui.core.drag_drop")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("retrotui.core.platform.mouse_backend", None)
        sys.modules.pop("retrotui.core.mouse_router", None)
        sys.modules.pop("retrotui.core.drag_drop", None)
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
        app = types.SimpleNamespace(
            windows=[],
            button1_pressed=False,
            stdscr=types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(25, 80))),
            stop_drag_flags=0xFFFF,
            click_flags=click_flags,
            scroll_down_mask=0x200000,
            menu=types.SimpleNamespace(
                active=False,
                handle_hover=mock.Mock(),
                handle_click=mock.Mock(return_value=None),
                hit_test_dropdown=mock.Mock(return_value=False),
                hit_test_menu_item=mock.Mock(return_value=True),
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
            _dragging_win=None,
            _resizing_win=None,
            _active_window_menu_owner=None,
            _last_icon_click_idx=None,
            _last_icon_click_ts=0.0,
            double_click_interval=0.4,
        )
        app.drag_drop = self.drag_drop_mod.DragDropManager(app)
        return app

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

    def test_invoke_mouse_handler_signature_error_falls_back_to_two_args(self):
        handler = mock.Mock(return_value="ok")
        with mock.patch.object(self.mouse_router.inspect, "signature", side_effect=TypeError("no sig")):
            out = self.mouse_router._invoke_mouse_handler(handler, 1, 2, 3)
        self.assertEqual(out, "ok")
        handler.assert_called_once_with(1, 2)

    def test_handler_accepts_bstate_uses_stable_cache_key_for_bound_methods(self):
        class Owner:
            def handle_click(self, mx, my, bstate):
                return (mx, my, bstate)

        owner = Owner()
        self.mouse_router._HANDLER_ARITY_CACHE.clear()

        with mock.patch.object(
            self.mouse_router.inspect,
            "signature",
            side_effect=py_inspect.signature,
        ) as signature:
            first = self.mouse_router._handler_accepts_bstate(owner.handle_click)
            second = self.mouse_router._handler_accepts_bstate(owner.handle_click)

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(signature.call_count, 1)
        self.assertEqual(len(self.mouse_router._HANDLER_ARITY_CACHE), 1)

    def test_import_uses_default_for_invalid_trace_interval(self):
        original = sys.modules.pop("retrotui.core.mouse_router", None)
        try:
            with mock.patch.dict(os.environ, {"RETROTUI_MOUSE_TRACE_MIN_INTERVAL": "bad"}):
                module = importlib.import_module("retrotui.core.mouse_router")

            self.assertEqual(module._TRACE_MOUSE_MIN_INTERVAL, 0.05)
        finally:
            sys.modules.pop("retrotui.core.mouse_router", None)
            if original is not None:
                sys.modules["retrotui.core.mouse_router"] = original

    def test_find_drop_target_window_and_dispatch_drop_edge_cases(self):
        app = self._make_app()
        mgr = app.drag_drop

        invisible = self._make_window(visible=False, contains=mock.Mock(return_value=True))
        app.windows = [invisible]
        self.assertIsNone(mgr.find_drop_target_window(1, 1))

        miss = self._make_window(visible=True, contains=mock.Mock(return_value=False))
        app.windows = [miss]
        self.assertIsNone(mgr.find_drop_target_window(1, 1))

        source = self._make_window(visible=True, contains=mock.Mock(return_value=True), open_path=mock.Mock())
        app.windows = [source]
        mgr.source_window = source
        self.assertIsNone(mgr.find_drop_target_window(1, 1))

        unsupported = self._make_window(visible=True, contains=mock.Mock(return_value=True))
        app.windows = [unsupported]
        mgr.source_window = None
        self.assertIsNone(mgr.find_drop_target_window(1, 1))

        target = self._make_window(open_path=mock.Mock(return_value=None))
        mgr.dispatch_drop(None, {})
        mgr.dispatch_drop(target, {"type": "other"})
        mgr.dispatch_drop(target, {"type": "file_path"})

    def test_handle_file_drag_drop_mouse_move_and_consumer_none_paths(self):
        app = self._make_app()
        payload = {"type": "file_path", "path": "/tmp/demo.txt"}

        source = self._make_window()
        target = self._make_window(contains=mock.Mock(return_value=True), open_path=mock.Mock(return_value=None))
        app.windows = [source, target]
        app.drag_drop.payload = payload
        app.drag_drop.source_window = source

        # move_drag updates drag target highlighting
        handled = self.mouse_router.handle_file_drag_drop_mouse(
            app, 10, 7, self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_PRESSED
        )
        self.assertTrue(handled)
        self.assertIs(app.drag_drop.target_window, target)

        # Existing drag payload but not moving or stopping still consumes the event.
        handled = self.mouse_router.handle_file_drag_drop_mouse(app, 10, 7, self.curses.REPORT_MOUSE_POSITION)
        self.assertTrue(handled)

        # No drag payload and not moving returns False.
        app.drag_drop.payload = None
        app.drag_drop.source_window = None
        handled = self.mouse_router.handle_file_drag_drop_mouse(app, 10, 7, 0)
        self.assertFalse(handled)

        # Consumer returns None -> continue -> end returns False.
        consumer = self._make_window(consume_pending_drag=mock.Mock(return_value=None))
        app.windows = [consumer]
        handled = self.mouse_router.handle_file_drag_drop_mouse(
            app, 10, 7, self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_PRESSED
        )
        self.assertFalse(handled)

    def test_handle_file_drag_drop_mouse_uses_normalized_motion_without_raw_flags(self):
        app = self._make_app()
        payload = {"type": "file_path", "path": "/tmp/demo.txt"}
        source = self._make_window()
        target = self._make_window(
            contains=mock.Mock(return_value=True),
            open_path=mock.Mock(return_value=None),
        )
        app.windows = [source, target]
        app.drag_drop.payload = payload
        app.drag_drop.source_window = source

        norm = {
            "is_motion": True,
            "button1_down": True,
            "button1_released": False,
            "button1_clicked": False,
            "button1_double": False,
        }
        handled = self.mouse_router.handle_file_drag_drop_mouse(app, 9, 6, 0, norm=norm)

        self.assertTrue(handled)
        self.assertIs(app.drag_drop.target_window, target)

    def test_handle_file_drag_drop_mouse_ignores_click_stop_while_motion_is_active(self):
        app = self._make_app()
        payload = {"type": "file_path", "path": "/tmp/demo.txt"}
        source = self._make_window()
        target = self._make_window(
            contains=mock.Mock(return_value=True),
            open_path=mock.Mock(return_value=None),
        )
        app.windows = [source, target]
        app.drag_drop.payload = payload
        app.drag_drop.source_window = source

        norm = {
            "is_motion": True,
            "button1_down": True,
            "button1_released": False,
            "button1_clicked": True,
            "button1_double": False,
        }
        handled = self.mouse_router.handle_file_drag_drop_mouse(
            app,
            9,
            6,
            self.curses.BUTTON1_CLICKED,
            norm=norm,
        )

        self.assertTrue(handled)
        self.assertIsNotNone(app.drag_drop.payload)
        target.open_path.assert_not_called()

    def test_handle_mouse_event_returns_after_file_drag_drop(self):
        app = self._make_app()

        with mock.patch.object(self.mouse_router, "handle_file_drag_drop_mouse", return_value=True):
            self.mouse_router.handle_mouse_event(app, (0, 3, 3, 0, self.curses.BUTTON1_CLICKED))

        app._handle_drag_resize_mouse.assert_not_called()
        app._handle_global_menu_mouse.assert_not_called()
        app._handle_window_mouse.assert_not_called()

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
        app._dragging_win = win

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
        app._dragging_win = win

        handled = self.mouse_router.handle_drag_resize_mouse(app, 0, 0, app.stop_drag_flags)

        self.assertTrue(handled)
        self.assertFalse(win.dragging)

    def test_handle_drag_resize_mouse_keeps_dragging_on_pressed_event(self):
        app = self._make_app()
        app.stop_drag_flags = self.curses.BUTTON1_RELEASED
        win = types.SimpleNamespace(
            dragging=True,
            drag_offset_x=1,
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
        app._dragging_win = win

        handled = self.mouse_router.handle_drag_resize_mouse(
            app,
            9,
            7,
            self.curses.BUTTON1_PRESSED,
        )

        self.assertTrue(handled)
        self.assertTrue(win.dragging)
        self.assertEqual(win.x, 8)
        self.assertEqual(win.y, 6)

    def test_handle_drag_resize_mouse_ignores_click_stop_while_motion_norm_active(self):
        app = self._make_app()
        win = types.SimpleNamespace(
            dragging=True,
            drag_offset_x=1,
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
        app._dragging_win = win
        app._mouse_norm = {
            "is_motion": True,
            "button1_released": False,
            "button1_clicked": True,
            "button1_double": False,
        }

        handled = self.mouse_router.handle_drag_resize_mouse(
            app,
            9,
            7,
            self.curses.BUTTON1_CLICKED,
        )

        self.assertTrue(handled)
        self.assertTrue(win.dragging)
        self.assertEqual(win.x, 8)
        self.assertEqual(win.y, 6)

    def test_handle_drag_resize_mouse_no_tracked_window(self):
        """When no window is tracked as dragging/resizing, return False."""
        app = self._make_app()
        app._dragging_win = None
        app._resizing_win = None
        handled = self.mouse_router.handle_drag_resize_mouse(app, 5, 5, 0)
        self.assertFalse(handled)

    def test_handle_drag_resize_mouse_stops_resizing(self):
        app = self._make_app()
        win = types.SimpleNamespace(
            dragging=False,
            resizing=True,
            resize_edge="right",
            apply_resize=mock.Mock(),
        )
        app.windows = [win]
        app._resizing_win = win

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
        app._resizing_win = win

        handled = self.mouse_router.handle_drag_resize_mouse(app, 15, 9, 0)

        self.assertTrue(handled)
        win.apply_resize.assert_called_once_with(15, 9, 80, 25)

    def test_handle_drag_resize_mouse_clears_pointer_on_stop(self):
        """Stopping a resize clears the _resizing_win pointer."""
        app = self._make_app()
        win = types.SimpleNamespace(
            dragging=False,
            resizing=True,
            resize_edge="right",
            apply_resize=mock.Mock(),
        )
        app._resizing_win = win
        handled = self.mouse_router.handle_drag_resize_mouse(app, 0, 0, app.stop_drag_flags)
        self.assertTrue(handled)
        self.assertIsNone(app._resizing_win)

    def test_handle_file_drag_drop_mouse_starts_drag_and_highlights_target(self):
        app = self._make_app()
        payload = {"type": "file_path", "path": "/tmp/demo.txt"}
        source = self._make_window(consume_pending_drag=mock.Mock(return_value=payload))
        target = self._make_window(
            contains=mock.Mock(return_value=True),
            open_path=mock.Mock(return_value=None),
        )
        app.windows = [source, target]

        handled = self.mouse_router.handle_file_drag_drop_mouse(
            app,
            10,
            7,
            self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_PRESSED,
        )

        self.assertTrue(handled)
        self.assertEqual(app.drag_drop.payload, payload)
        self.assertIs(app.drag_drop.source_window, source)
        self.assertIs(app.drag_drop.target_window, target)
        self.assertTrue(target.drop_target_highlight)

    def test_handle_file_drag_drop_mouse_drop_opens_notepad_target(self):
        app = self._make_app()
        payload = {"type": "file_path", "path": "/tmp/demo.txt"}
        source = self._make_window()
        target = self._make_window(
            contains=mock.Mock(return_value=True),
            open_path=mock.Mock(return_value="opened"),
        )
        app.windows = [source, target]
        app.drag_drop.payload = payload
        app.drag_drop.source_window = source
        app.drag_drop.target_window = target
        target.drop_target_highlight = True

        handled = self.mouse_router.handle_file_drag_drop_mouse(app, 12, 8, app.stop_drag_flags)

        self.assertTrue(handled)
        target.open_path.assert_called_once_with("/tmp/demo.txt")
        app._dispatch_window_result.assert_called_once_with("opened", target)
        self.assertIsNone(app.drag_drop.payload)
        self.assertIsNone(app.drag_drop.source_window)
        self.assertIsNone(app.drag_drop.target_window)
        self.assertFalse(target.drop_target_highlight)

    def test_handle_file_drag_drop_mouse_drop_forwards_terminal_target(self):
        app = self._make_app()
        payload = {"type": "file_path", "path": "/tmp/demo.txt"}
        source = self._make_window()
        target = self._make_window(
            contains=mock.Mock(return_value=True),
            accept_dropped_path=mock.Mock(return_value=None),
        )
        app.windows = [source, target]
        app.drag_drop.payload = payload
        app.drag_drop.source_window = source

        handled = self.mouse_router.handle_file_drag_drop_mouse(app, 12, 8, app.stop_drag_flags)

        self.assertTrue(handled)
        target.accept_dropped_path.assert_called_once_with("/tmp/demo.txt")
        app._dispatch_window_result.assert_not_called()
        self.assertIsNone(app.drag_drop.payload)

    def test_handle_file_drag_drop_mouse_stop_without_active_drag_clears_candidates(self):
        app = self._make_app()
        source = self._make_window(clear_pending_drag=mock.Mock())
        app.windows = [source]

        handled = self.mouse_router.handle_file_drag_drop_mouse(app, 0, 0, app.stop_drag_flags)

        self.assertFalse(handled)
        source.clear_pending_drag.assert_called_once_with()

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

    def test_handle_window_mouse_title_press_gpm_tolerates_one_row_below(self):
        app = self._make_app()
        win = self._make_window(
            x=10,
            y=5,
            w=24,
            on_title_bar=mock.Mock(return_value=False),
            window_menu=None,
        )
        app.windows = [win]
        norm = {
            "backend": "gpm",
            "is_click_like": True,
            "button1_pressed": True,
            "button1_clicked": False,
            "button1_double": False,
            "is_motion": False,
            "scroll_up": False,
            "scroll_down": False,
        }

        handled = self.mouse_router.handle_window_mouse(
            app,
            12,
            6,  # one row below title (y+1)
            self.curses.BUTTON1_PRESSED,
            norm=norm,
        )

        self.assertTrue(handled)
        self.assertTrue(win.dragging)
        self.assertEqual(win.drag_offset_x, 2)
        self.assertEqual(win.drag_offset_y, 1)

    def test_handle_window_mouse_title_press_gpm_tolerance_respects_control_zone(self):
        app = self._make_app()
        win = self._make_window(
            x=10,
            y=5,
            w=24,
            on_title_bar=mock.Mock(return_value=False),
            window_menu=None,
            on_minimize_button=mock.Mock(return_value=False),
        )
        app.windows = [win]
        norm = {
            "backend": "gpm",
            "is_click_like": True,
            "button1_pressed": True,
            "button1_clicked": False,
            "button1_double": False,
            "is_motion": False,
            "scroll_up": False,
            "scroll_down": False,
        }
        # Inside right-side title controls reserved zone.
        mx_controls = win.x + win.w - 9

        handled = self.mouse_router.handle_window_mouse(
            app,
            mx_controls,
            6,
            self.curses.BUTTON1_PRESSED,
            norm=norm,
        )

        self.assertFalse(getattr(win, "dragging"))
        self.assertFalse(handled)

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
        app._active_window_menu_owner = win

        handled = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.REPORT_MOUSE_POSITION)

        self.assertTrue(handled)
        menu.handle_hover.assert_called_once_with(11, 7, win.x, win.y, win.w)

    def test_handle_window_mouse_click_outside_closes_active_window_menu(self):
        app = self._make_app()
        menu = types.SimpleNamespace(active=True, handle_hover=mock.Mock(return_value=False))
        win = self._make_window(window_menu=menu, contains=mock.Mock(return_value=False))
        app.windows = [win]
        app._active_window_menu_owner = win

        handled = self.mouse_router.handle_window_mouse(app, 1, 1, self.curses.BUTTON1_CLICKED)

        self.assertFalse(handled)
        self.assertFalse(menu.active)
        self.assertIsNone(app._active_window_menu_owner)

    def test_handle_window_mouse_contains_click_evaluates_other_window_condition(self):
        app = self._make_app()
        win = self._make_window(
            contains=mock.Mock(return_value=True),
            handle_click=mock.Mock(return_value=None),
            window_menu=types.SimpleNamespace(active=False, handle_hover=mock.Mock(return_value=False)),
        )
        other = self._make_window(window_menu=types.SimpleNamespace(active=True))
        app.windows = [other, win]
        app._active_window_menu_owner = other

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
        app._active_window_menu_owner = other_active

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
        app._active_window_menu_owner = other

        handled = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.BUTTON1_CLICKED)

        self.assertTrue(handled)
        self.assertFalse(active_menu.active)
        self.assertIs(app._active_window_menu_owner, win)
        app._dispatch_window_result.assert_called_once_with("result", win)
        win.handle_click.assert_called_once_with(11, 7, self.curses.BUTTON1_CLICKED)

    def test_handle_window_mouse_click_inside_closes_tracked_menu_without_full_scan(self):
        app = self._make_app()
        tracked_menu = types.SimpleNamespace(active=True)
        tracked = self._make_window(window_menu=tracked_menu)
        clicked = self._make_window(
            contains=mock.Mock(return_value=True),
            handle_click=mock.Mock(return_value=None),
            window_menu=types.SimpleNamespace(active=False, handle_hover=mock.Mock(return_value=False)),
        )

        class PoisonWindow:
            visible = True
            active = False
            minimized = False
            maximized = False
            x = 1
            y = 1
            w = 2
            h = 2
            dragging = False
            drag_offset_x = 0
            drag_offset_y = 0
            resizing = False
            resize_edge = None

            def on_close_button(self, *_):
                return False

            def on_minimize_button(self, *_):
                return False

            def on_maximize_button(self, *_):
                return False

            def on_border(self, *_):
                return None

            def on_title_bar(self, *_):
                return False

            def contains(self, *_):
                return False

            @property
            def window_menu(self):
                raise AssertionError("window_menu scan should not occur")

        app.windows = [PoisonWindow(), tracked, clicked]
        app._active_window_menu_owner = tracked

        handled = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.BUTTON1_CLICKED)

        self.assertTrue(handled)
        self.assertFalse(tracked_menu.active)

    def test_handle_window_mouse_click_inside_supports_legacy_two_arg_handler(self):
        app = self._make_app()

        class LegacyWin:
            visible = True
            active = False
            minimized = False
            maximized = False
            x = 4
            y = 4
            w = 20
            h = 10
            dragging = False
            drag_offset_x = 0
            drag_offset_y = 0
            resizing = False
            resize_edge = None
            window_menu = None

            def on_close_button(self, *_):
                return False

            def on_minimize_button(self, *_):
                return False

            def on_maximize_button(self, *_):
                return False

            def on_border(self, *_):
                return None

            def on_title_bar(self, *_):
                return False

            def contains(self, *_):
                return True

            def handle_click(self, mx, my):
                return ("legacy", mx, my)

            def handle_scroll(self, *_):
                return None

        win = LegacyWin()
        app.windows = [win]

        handled = self.mouse_router.handle_window_mouse(app, 11, 7, self.curses.BUTTON1_CLICKED)

        self.assertTrue(handled)
        app._dispatch_window_result.assert_called_once_with(("legacy", 11, 7), win)

    def test_handle_window_mouse_drag_routes_to_handler(self):
        app = self._make_app()
        win = self._make_window(
            contains=mock.Mock(return_value=True),
            handle_mouse_drag=mock.Mock(return_value="drag-result"),
            window_menu=types.SimpleNamespace(active=False, handle_hover=mock.Mock(return_value=False)),
        )
        app.windows = [win]

        handled = self.mouse_router.handle_window_mouse(
            app,
            11,
            7,
            self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_PRESSED,
        )

        self.assertTrue(handled)
        win.handle_mouse_drag.assert_called_once_with(
            11,
            7,
            self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_PRESSED,
        )
        app._dispatch_window_result.assert_called_once_with("drag-result", win)

    def test_handle_window_mouse_drag_with_active_selection_is_captured_outside_window(self):
        app = self._make_app()
        win = self._make_window(
            contains=mock.Mock(return_value=False),
            handle_mouse_drag=mock.Mock(return_value="drag-selection"),
            window_menu=types.SimpleNamespace(active=False, handle_hover=mock.Mock(return_value=False)),
        )
        setattr(win, "_mouse_selecting", True)
        app.windows = [win]
        norm = {
            "is_click_like": False,
            "button1_pressed": True,
            "button1_pressed_raw": True,
            "button1_clicked": False,
            "button1_double": False,
            "is_motion": True,
            "scroll_up": False,
            "scroll_down": False,
        }

        handled = self.mouse_router.handle_window_mouse(
            app,
            99,
            99,
            self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_PRESSED,
            norm=norm,
        )

        self.assertTrue(handled)
        win.handle_mouse_drag.assert_called_once()
        app._dispatch_window_result.assert_called_once_with("drag-selection", win)

    def test_handle_window_mouse_drag_with_inferred_press_releases_capture_outside_window(self):
        app = self._make_app()
        win = self._make_window(
            contains=mock.Mock(return_value=False),
            handle_mouse_drag=mock.Mock(return_value="drag-selection"),
            window_menu=types.SimpleNamespace(active=False, handle_hover=mock.Mock(return_value=False)),
        )
        setattr(win, "_mouse_selecting", True)
        app.windows = [win]
        norm = {
            "is_click_like": False,
            "button1_pressed": True,
            "button1_pressed_raw": False,
            "button1_clicked": False,
            "button1_double": False,
            "is_motion": True,
            "scroll_up": False,
            "scroll_down": False,
        }

        handled = self.mouse_router.handle_window_mouse(
            app,
            99,
            99,
            self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_PRESSED,
            norm=norm,
        )

        self.assertFalse(handled)
        self.assertFalse(getattr(win, "_mouse_selecting"))
        win.handle_mouse_drag.assert_not_called()

    def test_handle_mouse_event_inferred_drag_sets_pressed_for_drag_handler(self):
        app = self._make_app()
        app.button1_pressed = True
        win = self._make_window(
            contains=mock.Mock(return_value=True),
            handle_mouse_drag=mock.Mock(return_value="drag-result"),
            window_menu=types.SimpleNamespace(active=False, handle_hover=mock.Mock(return_value=False)),
        )
        app.windows = [win]
        app._handle_window_mouse = mock.Mock(
            side_effect=lambda mx, my, bstate: self.mouse_router.handle_window_mouse(
                app,
                mx,
                my,
                bstate,
                norm=getattr(app, "_mouse_norm", None),
            )
        )

        # No REPORT_MOUSE_POSITION / BUTTON1_PRESSED bits in bstate; movement infers drag.
        self.mouse_router.handle_mouse_event(app, (0, 5, 5, 0, 0))
        self.mouse_router.handle_mouse_event(app, (0, 6, 6, 0, 0))

        self.assertTrue(win.handle_mouse_drag.called)

    def test_handle_mouse_event_motion_click_like_does_not_clear_button1_pressed(self):
        app = self._make_app()
        app.button1_pressed = True
        norm = {
            "mx": 6,
            "my": 6,
            "bstate": self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_CLICKED,
            "backend": "gpm",
            "has_motion": True,
            "inferred_motion": False,
            "right_click": False,
            "inferred_right_click": False,
            "button1_pressed": False,
            "button1_pressed_raw": False,
            "button1_released": False,
            "button1_clicked": True,
            "button1_double": False,
            "button1_down": True,
            "is_drag": True,
            "is_motion": True,
            "is_click_like": True,
            "scroll_up": False,
            "scroll_down": False,
            "is_passive_noop": False,
        }

        with mock.patch.object(self.mouse_router, "normalize_mouse_payload", return_value=norm):
            self.mouse_router.handle_mouse_event(
                app,
                (0, 6, 6, 0, self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_CLICKED),
            )

        self.assertTrue(app.button1_pressed)

    def test_handle_mouse_event_release_clears_selection_capture_state(self):
        app = self._make_app()
        selecting = self._make_window(contains=mock.Mock(return_value=False))
        setattr(selecting, "_mouse_selecting", True)
        app.windows = [selecting]
        norm = {
            "mx": 4,
            "my": 5,
            "bstate": self.curses.BUTTON1_RELEASED,
            "backend": "gpm",
            "has_motion": False,
            "inferred_motion": False,
            "right_click": False,
            "inferred_right_click": False,
            "button1_pressed": False,
            "button1_pressed_raw": False,
            "button1_released": True,
            "button1_clicked": False,
            "button1_double": False,
            "button1_down": False,
            "is_drag": False,
            "is_motion": False,
            "is_click_like": False,
            "scroll_up": False,
            "scroll_down": False,
            "is_passive_noop": False,
        }

        with mock.patch.object(self.mouse_router, "normalize_mouse_payload", return_value=norm):
            self.mouse_router.handle_mouse_event(
                app,
                (0, 4, 5, 0, self.curses.BUTTON1_RELEASED),
            )

        self.assertFalse(getattr(selecting, "_mouse_selecting"))

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

    def test_handle_desktop_mouse_fallback_double_click_executes_icon_action(self):
        app = self._make_app()
        app.get_icon_at.return_value = 0

        with mock.patch.object(self.mouse_router.time, "monotonic", side_effect=[10.0, 10.2]):
            first = self.mouse_router.handle_desktop_mouse(app, 9, 9, self.curses.BUTTON1_CLICKED)
            second = self.mouse_router.handle_desktop_mouse(app, 9, 9, self.curses.BUTTON1_CLICKED)

        self.assertTrue(first)
        self.assertTrue(second)
        app.execute_action.assert_called_once_with("about")

    def test_handle_desktop_mouse_fallback_double_click_times_out(self):
        app = self._make_app()
        app.get_icon_at.return_value = 0

        with mock.patch.object(self.mouse_router.time, "monotonic", side_effect=[1.0, 2.0]):
            self.mouse_router.handle_desktop_mouse(app, 9, 9, self.curses.BUTTON1_CLICKED)
            self.mouse_router.handle_desktop_mouse(app, 9, 9, self.curses.BUTTON1_CLICKED)

        app.execute_action.assert_not_called()
        self.assertEqual(app.selected_icon, 0)

    def test_handle_desktop_mouse_motion_event_does_not_trigger_fallback_double_click(self):
        app = self._make_app()
        app.get_icon_at.return_value = 0
        moving_click = self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_PRESSED

        with mock.patch.object(self.mouse_router.time, "monotonic", side_effect=[5.0, 5.1]):
            self.mouse_router.handle_desktop_mouse(app, 9, 9, self.curses.BUTTON1_CLICKED)
            self.mouse_router.handle_desktop_mouse(app, 9, 9, moving_click)

        app.execute_action.assert_not_called()
        self.assertEqual(app.selected_icon, 0)

    def test_handle_desktop_mouse_release_does_not_trigger_fallback_double_click(self):
        app = self._make_app()
        app.get_icon_at.return_value = 0

        with mock.patch.object(self.mouse_router.time, "monotonic", side_effect=[3.0, 3.1]):
            self.mouse_router.handle_desktop_mouse(app, 9, 9, self.curses.BUTTON1_RELEASED)
            self.mouse_router.handle_desktop_mouse(app, 9, 9, self.curses.BUTTON1_RELEASED)

        app.execute_action.assert_not_called()
        self.assertEqual(app.selected_icon, -1)

    def test_handle_desktop_mouse_deselects_when_no_icon_hit(self):
        app = self._make_app()

        handled = self.mouse_router.handle_desktop_mouse(app, 30, 10, 0)

        self.assertTrue(handled)
        self.assertEqual(app.selected_icon, -1)
        self.assertFalse(app.menu.active)

    def test_handle_desktop_mouse_starts_drag_with_button1_down_without_pressed_flag(self):
        app = self._make_app()
        app.get_icon_at.return_value = 0
        icon_mgr = types.SimpleNamespace(
            is_dragging=False,
            start_drag=mock.Mock(),
            update_drag=mock.Mock(),
            end_drag=mock.Mock(),
        )
        app._icon_mgr = icon_mgr

        norm = {
            "button1_released": False,
            "button1_pressed": False,
            "button1_down": True,
            "is_drag": True,
            "is_motion": True,
        }

        handled = self.mouse_router.handle_desktop_mouse(app, 9, 9, 0, norm=norm)

        self.assertTrue(handled)
        self.assertEqual(app.selected_icon, 0)
        icon_mgr.start_drag.assert_called_once_with(0, 9, 9)

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

    def test_handle_mouse_event_window_drag_capture_preempts_top_bar_click(self):
        app = self._make_app()
        app._dragging_win = self._make_window(dragging=True, drag_offset_x=0, drag_offset_y=0)
        app._handle_drag_resize_mouse.return_value = True
        app.menu.handle_click.return_value = "about"

        self.mouse_router.handle_mouse_event(
            app, (0, 3, 0, 0, self.curses.BUTTON1_PRESSED)
        )

        app._handle_drag_resize_mouse.assert_called_once_with(3, 0, self.curses.BUTTON1_PRESSED)
        app.menu.handle_click.assert_not_called()
        app.execute_action.assert_not_called()

    def test_handle_mouse_event_icon_drag_capture_routes_directly_to_desktop(self):
        app = self._make_app()
        app._icon_mgr = types.SimpleNamespace(is_dragging=True)
        app._handle_desktop_mouse.return_value = True

        self.mouse_router.handle_mouse_event(
            app, (0, 15, 8, 0, self.curses.BUTTON1_PRESSED)
        )

        app._handle_desktop_mouse.assert_called_once_with(15, 8, self.curses.BUTTON1_PRESSED)
        app._handle_window_mouse.assert_not_called()

    def test_handle_mouse_event_selection_capture_routes_to_window_before_desktop(self):
        app = self._make_app()
        selecting = self._make_window(contains=mock.Mock(return_value=False))
        setattr(selecting, "_mouse_selecting", True)
        app.windows = [selecting]
        app._handle_window_mouse.return_value = True
        app._handle_desktop_mouse.return_value = False

        self.mouse_router.handle_mouse_event(
            app,
            (0, 40, 20, 0, self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_PRESSED),
        )

        app._handle_window_mouse.assert_called_once_with(
            40, 20, self.curses.REPORT_MOUSE_POSITION | self.curses.BUTTON1_PRESSED
        )
        app._handle_desktop_mouse.assert_not_called()

    def test_handle_mouse_event_click_outside_windows_clears_text_selection(self):
        app = self._make_app()
        selection_win = self._make_window(
            contains=mock.Mock(return_value=False),
            clear_selection=mock.Mock(),
            has_selection=mock.Mock(return_value=True),
            selection_anchor=(0, 0),
            selection_cursor=(0, 2),
            _mouse_selecting=True,
        )
        app.windows = [selection_win]
        app._handle_window_mouse = mock.Mock(
            side_effect=lambda mx, my, bstate: self.mouse_router.handle_window_mouse(
                app,
                mx,
                my,
                bstate,
                norm=getattr(app, "_mouse_norm", None),
            )
        )
        app._handle_desktop_mouse = mock.Mock(return_value=False)

        self.mouse_router.handle_mouse_event(
            app, (0, 40, 20, 0, self.curses.BUTTON1_CLICKED)
        )

        selection_win.clear_selection.assert_called_once_with()
        app._handle_desktop_mouse.assert_called_once_with(40, 20, self.curses.BUTTON1_CLICKED)

    def test_handle_mouse_event_dialog_has_priority(self):
        app = self._make_app()
        app._handle_dialog_mouse.return_value = True

        self.mouse_router.handle_mouse_event(app, (0, 3, 3, 0, self.curses.BUTTON1_CLICKED))

        app._handle_drag_resize_mouse.assert_not_called()
        app._handle_window_mouse.assert_not_called()
        app._handle_desktop_mouse.assert_not_called()

    def test_handle_mouse_event_right_click_respects_dialog_priority(self):
        app = self._make_app()
        app._handle_dialog_mouse.return_value = True
        app.handle_right_click = mock.Mock(return_value=True)

        self.mouse_router.handle_mouse_event(app, (0, 3, 3, 0, self.curses.BUTTON3_CLICKED))

        app.handle_right_click.assert_not_called()
        app._handle_drag_resize_mouse.assert_not_called()
        app._handle_window_mouse.assert_not_called()
        app._handle_desktop_mouse.assert_not_called()

    def test_handle_mouse_event_right_click_route_error_falls_back_to_desktop(self):
        app = self._make_app()
        app.handle_right_click = mock.Mock(side_effect=ValueError("bad handler"))

        self.mouse_router.handle_mouse_event(app, (0, 3, 3, 0, self.curses.BUTTON3_CLICKED))

        app.handle_right_click.assert_called_once_with(3, 3, self.curses.BUTTON3_CLICKED)
        app._handle_desktop_mouse.assert_called_once_with(3, 3, self.curses.BUTTON3_CLICKED)

    def test_handle_mouse_event_taskbar_short_circuit(self):
        app = self._make_app()
        app.handle_taskbar_click.return_value = True

        self.mouse_router.handle_mouse_event(app, (0, 3, 3, 0, self.curses.BUTTON1_CLICKED))

        app._handle_window_mouse.assert_not_called()
        app._handle_desktop_mouse.assert_not_called()

    def test_handle_mouse_event_taskbar_priority_over_clock_region(self):
        app = self._make_app()
        app.handle_taskbar_click.return_value = True
        app.menu.hit_test_menu_item.return_value = False

        # Right side of unified top bar overlaps clock hotspot; taskbar must win.
        self.mouse_router.handle_mouse_event(app, (0, 79, 0, 0, self.curses.BUTTON1_CLICKED))

        app.handle_taskbar_click.assert_called_once_with(79, 0)
        app.execute_action.assert_not_called()

    def test_handle_mouse_event_clock_region_runs_when_taskbar_not_handled(self):
        app = self._make_app()
        app.handle_taskbar_click.return_value = False
        app.menu.hit_test_menu_item.return_value = False

        self.mouse_router.handle_mouse_event(app, (0, 79, 0, 0, self.curses.BUTTON1_CLICKED))

        app.execute_action.assert_called_once_with("plugin:clock")
        app._handle_window_mouse.assert_not_called()

    def test_handle_mouse_event_top_bar_free_space_can_route_taskbar(self):
        app = self._make_app()
        app.menu.hit_test_menu_item.return_value = False
        app.handle_taskbar_click.return_value = True

        self.mouse_router.handle_mouse_event(app, (0, 40, 0, 0, self.curses.BUTTON1_CLICKED))

        app.menu.handle_click.assert_not_called()
        app.handle_taskbar_click.assert_called_once_with(40, 0)
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

    def test_trace_mouse_normalization_is_rate_limited(self):
        raw = (0, 1, 2, 0, self.curses.BUTTON1_CLICKED)
        norm = {
            "backend": "gpm",
            "mx": 1,
            "my": 2,
            "bstate": self.curses.BUTTON1_CLICKED,
            "is_click_like": True,
            "right_click": False,
            "is_drag": False,
            "is_motion": False,
            "is_passive_noop": False,
            "inferred_motion": False,
            "inferred_right_click": False,
        }
        original_trace = self.mouse_router._TRACE_MOUSE
        original_interval = self.mouse_router._TRACE_MOUSE_MIN_INTERVAL
        original_ts = self.mouse_router._TRACE_MOUSE_LAST_TS["value"]
        self.mouse_router._TRACE_MOUSE = True
        self.mouse_router._TRACE_MOUSE_MIN_INTERVAL = 0.5
        self.mouse_router._TRACE_MOUSE_LAST_TS["value"] = 0.0
        try:
            with mock.patch.object(self.mouse_router.LOGGER, "isEnabledFor", return_value=True):
                with mock.patch.object(self.mouse_router.LOGGER, "debug") as log_debug:
                    with mock.patch.object(self.mouse_router.time, "monotonic", side_effect=[1.0, 1.1, 1.7]):
                        self.mouse_router._trace_mouse_normalization(raw, norm, norm["bstate"])
                        self.mouse_router._trace_mouse_normalization(raw, norm, norm["bstate"])
                        self.mouse_router._trace_mouse_normalization(raw, norm, norm["bstate"])
            self.assertEqual(log_debug.call_count, 2)
        finally:
            self.mouse_router._TRACE_MOUSE = original_trace
            self.mouse_router._TRACE_MOUSE_MIN_INTERVAL = original_interval
            self.mouse_router._TRACE_MOUSE_LAST_TS["value"] = original_ts


if __name__ == "__main__":
    unittest.main()

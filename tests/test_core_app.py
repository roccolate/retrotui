import importlib
import sys
import time
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_LEFT = 260
    fake.KEY_RIGHT = 261
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_ENTER = 343
    fake.KEY_HOME = 262
    fake.KEY_END = 360
    fake.KEY_PPAGE = 339
    fake.KEY_NPAGE = 338
    fake.KEY_BACKSPACE = 263
    fake.KEY_DC = 330
    fake.KEY_MOUSE = 409
    fake.KEY_RESIZE = 410
    fake.KEY_F10 = 266
    fake.ALL_MOUSE_EVENTS = 0xFFFFFFFF
    fake.REPORT_MOUSE_POSITION = 0x200000
    fake.BUTTON1_CLICKED = 0x0004
    fake.BUTTON1_PRESSED = 0x0002
    fake.BUTTON1_DOUBLE_CLICKED = 0x0008
    fake.BUTTON1_RELEASED = 0x0001
    fake.BUTTON4_PRESSED = 0x100000
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.A_DIM = 4
    fake.COLOR_WHITE = 7
    fake.COLOR_BLUE = 4
    fake.COLOR_BLACK = 0
    fake.COLOR_CYAN = 6
    fake.COLOR_YELLOW = 3
    fake.COLORS = 256
    fake.error = Exception
    fake.color_pair = lambda _: 0
    fake.can_change_color = lambda: False
    fake.start_color = lambda: None
    fake.use_default_colors = lambda: None
    fake.init_color = lambda *_: None
    fake.init_pair = lambda *_: None
    fake.curs_set = lambda *_: None
    fake.noecho = lambda: None
    fake.cbreak = lambda: None
    fake.mousemask = lambda *_: None
    fake.update_lines_cols = lambda: None
    fake.doupdate = lambda: None
    fake.getmouse = lambda: (0, 0, 0, 0, 0)
    return fake


class CoreAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        cls._prev_termios = sys.modules.get("termios")
        sys.modules["curses"] = _install_fake_curses()

        fake_termios = types.ModuleType("termios")
        fake_termios.error = OSError
        fake_termios.IXON = 0x0200
        fake_termios.IXOFF = 0x0400
        fake_termios.TCSANOW = 0
        fake_termios.tcgetattr = lambda *_: [0, 0, 0, 0, 0, 0, 0]
        fake_termios.tcsetattr = lambda *_: None
        sys.modules["termios"] = fake_termios

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
            "retrotui.ui.window",
            "retrotui.apps.notepad",
            "retrotui.apps.filemanager",
            "retrotui.apps.logviewer",
            "retrotui.apps.process_manager",
            "retrotui.apps.clock",
            "retrotui.core.actions",
            "retrotui.core.action_runner",
            "retrotui.core.key_router",
            "retrotui.core.mouse_router",
            "retrotui.core.rendering",
            "retrotui.core.event_loop",
            "retrotui.core.bootstrap",
            "retrotui.core.app",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.app_mod = importlib.import_module("retrotui.core.app")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
            "retrotui.ui.window",
            "retrotui.apps.notepad",
            "retrotui.apps.filemanager",
            "retrotui.apps.logviewer",
            "retrotui.apps.process_manager",
            "retrotui.apps.clock",
            "retrotui.core.actions",
            "retrotui.core.action_runner",
            "retrotui.core.key_router",
            "retrotui.core.mouse_router",
            "retrotui.core.rendering",
            "retrotui.core.event_loop",
            "retrotui.core.bootstrap",
            "retrotui.core.app",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

        if cls._prev_termios is not None:
            sys.modules["termios"] = cls._prev_termios
        else:
            sys.modules.pop("termios", None)

    def _make_app(self):
        app = self.app_mod.RetroTUI.__new__(self.app_mod.RetroTUI)
        app.running = True
        app.dialog = None
        app._background_operation = None
        app.windows = []
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        app.menu = types.SimpleNamespace(
            active=False,
            selected_menu=3,
            selected_item=3,
            handle_key=mock.Mock(return_value=None),
            handle_click=mock.Mock(return_value=None),
            handle_hover=mock.Mock(return_value=None),
            hit_test_dropdown=mock.Mock(return_value=False),
        )
        app.click_flags = (
            self.curses.BUTTON1_CLICKED
            | self.curses.BUTTON1_PRESSED
            | self.curses.BUTTON1_DOUBLE_CLICKED
        )
        app.stop_drag_flags = app.click_flags | self.curses.BUTTON1_RELEASED
        app.scroll_down_mask = getattr(self.curses, "BUTTON5_PRESSED", 0x200000)
        app.selected_icon = -1
        app.icons = [{"action": self.actions_mod.AppAction.ABOUT, "art": ["[]"], "label": "About"}]
        return app

    def test_init_configures_terminal_and_creates_welcome_window(self):
        stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        fake_menu = types.SimpleNamespace(
            active=False,
            selected_menu=0,
            selected_item=0,
            handle_key=mock.Mock(return_value=None),
            handle_click=mock.Mock(return_value=None),
            handle_hover=mock.Mock(return_value=None),
            hit_test_dropdown=mock.Mock(return_value=False),
        )
        fake_window = types.SimpleNamespace(active=False)

        with (
            mock.patch.object(self.app_mod, "check_unicode_support", return_value=True),
            mock.patch.object(self.app_mod, "configure_terminal") as configure_terminal,
            mock.patch.object(self.app_mod, "disable_flow_control") as disable_flow_control,
            mock.patch.object(self.app_mod, "enable_mouse_support", return_value=(11, 22, 33)),
            mock.patch.object(self.app_mod, "init_colors") as init_colors,
            mock.patch.object(self.app_mod, "Menu", return_value=fake_menu),
            mock.patch.object(self.app_mod, "build_welcome_content", return_value=["welcome"]) as welcome_builder,
            mock.patch.object(self.app_mod, "Window", return_value=fake_window) as window_cls,
        ):
            app = self.app_mod.RetroTUI(stdscr)

        configure_terminal.assert_called_once_with(stdscr, timeout_ms=500)
        disable_flow_control.assert_called_once_with()
        init_colors.assert_called_once_with(app.theme)
        self.assertEqual(app.theme.key, "win31")
        welcome_builder.assert_called_once_with(self.app_mod.APP_VERSION)
        window_cls.assert_called_once()
        self.assertEqual(app.click_flags, 11)
        self.assertEqual(app.stop_drag_flags, 22)
        self.assertEqual(app.scroll_down_mask, 33)
        self.assertIsNone(app.drag_payload)
        self.assertIsNone(app.drag_source_window)
        self.assertIsNone(app.drag_target_window)
        self.assertEqual(app.menu, fake_menu)
        self.assertEqual(app.windows, [fake_window])
        self.assertTrue(fake_window.active)
        self.assertEqual(app.icons, self.app_mod.ICONS)

    def test_init_uses_ascii_icons_when_unicode_not_supported(self):
        stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        fake_menu = types.SimpleNamespace(
            active=False,
            selected_menu=0,
            selected_item=0,
            handle_key=mock.Mock(return_value=None),
            handle_click=mock.Mock(return_value=None),
            handle_hover=mock.Mock(return_value=None),
            hit_test_dropdown=mock.Mock(return_value=False),
        )

        with (
            mock.patch.object(self.app_mod, "check_unicode_support", return_value=False),
            mock.patch.object(self.app_mod, "configure_terminal"),
            mock.patch.object(self.app_mod, "disable_flow_control"),
            mock.patch.object(self.app_mod, "enable_mouse_support", return_value=(1, 2, 3)),
            mock.patch.object(self.app_mod, "init_colors"),
            mock.patch.object(self.app_mod, "Menu", return_value=fake_menu),
            mock.patch.object(self.app_mod, "build_welcome_content", return_value=["welcome"]),
            mock.patch.object(self.app_mod, "Window", return_value=types.SimpleNamespace(active=False)),
        ):
            app = self.app_mod.RetroTUI(stdscr)

        self.assertEqual(app.icons, self.app_mod.ICONS_ASCII)

    def test_cleanup_delegates_to_bootstrap_helper(self):
        app = self._make_app()

        with mock.patch.object(self.app_mod, "disable_mouse_support") as disable_mouse_support:
            app.cleanup()

        disable_mouse_support.assert_called_once_with()

    def test_cleanup_calls_window_close_hooks_and_handles_errors(self):
        app = self._make_app()
        good = types.SimpleNamespace(close=mock.Mock())
        bad = types.SimpleNamespace(close=mock.Mock(side_effect=RuntimeError("close failed")))
        app.windows = [good, bad]

        with (
            mock.patch.object(self.app_mod, "disable_mouse_support") as disable_mouse_support,
            mock.patch.object(self.app_mod.LOGGER, "debug") as log_debug,
        ):
            app.cleanup()

        good.close.assert_called_once_with()
        bad.close.assert_called_once_with()
        log_debug.assert_called_once()
        disable_mouse_support.assert_called_once_with()

    def test_draw_wrappers_delegate_to_rendering_helpers(self):
        app = self._make_app()

        with (
            mock.patch.object(self.app_mod, "draw_desktop", return_value="desktop") as draw_desktop,
            mock.patch.object(self.app_mod, "draw_icons", return_value="icons") as draw_icons,
            mock.patch.object(self.app_mod, "draw_taskbar", return_value="taskbar") as draw_taskbar,
            mock.patch.object(self.app_mod, "draw_statusbar", return_value="status") as draw_statusbar,
        ):
            self.assertEqual(app.draw_desktop(), "desktop")
            self.assertEqual(app.draw_icons(), "icons")
            self.assertEqual(app.draw_taskbar(), "taskbar")
            self.assertEqual(app.draw_statusbar(), "status")

        draw_desktop.assert_called_once_with(app)
        draw_icons.assert_called_once_with(app)
        draw_taskbar.assert_called_once_with(app)
        draw_statusbar.assert_called_once_with(app, self.app_mod.APP_VERSION)

    def test_mouse_and_key_wrappers_delegate_to_router_helpers(self):
        app = self._make_app()

        with (
            mock.patch.object(self.app_mod, "handle_drag_resize_mouse", return_value="drag"),
            mock.patch.object(self.app_mod, "handle_global_menu_mouse", return_value="menu"),
            mock.patch.object(self.app_mod, "handle_window_mouse", return_value="window"),
            mock.patch.object(self.app_mod, "handle_desktop_mouse", return_value="desktop"),
            mock.patch.object(self.app_mod, "handle_mouse_event", return_value="mouse"),
            mock.patch.object(self.app_mod, "normalize_app_key", return_value=99),
            mock.patch.object(self.app_mod, "handle_menu_hotkeys", return_value=True),
            mock.patch.object(self.app_mod, "handle_global_menu_key", return_value=True),
            mock.patch.object(self.app_mod, "cycle_focus", return_value=None),
            mock.patch.object(self.app_mod, "handle_active_window_key", return_value=None),
            mock.patch.object(self.app_mod, "handle_key_event", return_value="key"),
        ):
            self.assertEqual(app._handle_drag_resize_mouse(1, 2, 3), "drag")
            self.assertEqual(app._handle_global_menu_mouse(1, 2, 3), "menu")
            self.assertEqual(app._handle_window_mouse(1, 2, 3), "window")
            self.assertEqual(app._handle_desktop_mouse(1, 2, 3), "desktop")
            self.assertEqual(app.handle_mouse((1, 2, 3, 4, 5)), "mouse")
            self.assertEqual(app._key_code("k"), 99)
            self.assertTrue(app._handle_menu_hotkeys(10))
            self.assertTrue(app._handle_global_menu_key(10))
            self.assertIsNone(app._cycle_focus())
            self.assertIsNone(app._handle_active_window_key("x"))
            self.assertEqual(app.handle_key("x"), "key")

    def test_normalize_action_maps_legacy_string(self):
        app = self._make_app()

        self.assertEqual(
            app._normalize_action("filemanager"),
            self.actions_mod.AppAction.FILE_MANAGER,
        )
        self.assertEqual(app._normalize_action("unknown_action"), "unknown_action")
        self.assertEqual(app._normalize_action(123), 123)

    def test_execute_action_delegates_to_action_runner(self):
        app = self._make_app()

        with mock.patch.object(self.app_mod, "execute_app_action") as runner:
            app.execute_action("about")

        runner.assert_called_once_with(
            app,
            self.actions_mod.AppAction.ABOUT,
            self.app_mod.LOGGER,
            version=self.app_mod.APP_VERSION,
        )

    def test_dispatch_open_file_calls_file_viewer(self):
        app = self._make_app()
        app.open_file_viewer = mock.Mock()
        result = self.actions_mod.ActionResult(
            self.actions_mod.ActionType.OPEN_FILE, "/tmp/demo.txt"
        )

        app._dispatch_window_result(result, source_win=None)

        app.open_file_viewer.assert_called_once_with("/tmp/demo.txt")

    def test_dispatch_execute_close_window_prefers_close(self):
        app = self._make_app()
        source = object()
        app.close_window = mock.Mock()
        app.execute_action = mock.Mock()
        result = self.actions_mod.ActionResult(
            self.actions_mod.ActionType.EXECUTE, self.actions_mod.AppAction.CLOSE_WINDOW
        )

        app._dispatch_window_result(result, source)

        app.close_window.assert_called_once_with(source)
        app.execute_action.assert_not_called()

    def test_dispatch_request_save_as_calls_dialog_builder(self):
        app = self._make_app()
        source = object()
        app.show_save_as_dialog = mock.Mock()
        result = self.actions_mod.ActionResult(self.actions_mod.ActionType.REQUEST_SAVE_AS)

        app._dispatch_window_result(result, source)

        app.show_save_as_dialog.assert_called_once_with(source)

    def test_dispatch_request_open_path_calls_dialog_builder(self):
        app = self._make_app()
        source = object()
        app.show_open_dialog = mock.Mock()
        result = self.actions_mod.ActionResult(self.actions_mod.ActionType.REQUEST_OPEN_PATH)

        app._dispatch_window_result(result, source)

        app.show_open_dialog.assert_called_once_with(source)

    def test_dispatch_request_rename_entry_calls_dialog_builder(self):
        app = self._make_app()
        source = object()
        app.show_rename_dialog = mock.Mock()
        result = self.actions_mod.ActionResult(self.actions_mod.ActionType.REQUEST_RENAME_ENTRY)

        app._dispatch_window_result(result, source)

        app.show_rename_dialog.assert_called_once_with(source)

    def test_dispatch_request_delete_confirm_calls_dialog_builder(self):
        app = self._make_app()
        source = object()
        app.show_delete_confirm_dialog = mock.Mock()
        result = self.actions_mod.ActionResult(self.actions_mod.ActionType.REQUEST_DELETE_CONFIRM)

        app._dispatch_window_result(result, source)

        app.show_delete_confirm_dialog.assert_called_once_with(source)

    def test_dispatch_request_copy_move_new_entry_dialogs(self):
        app = self._make_app()
        source = object()
        app.show_copy_dialog = mock.Mock()
        app.show_move_dialog = mock.Mock()
        app.show_new_dir_dialog = mock.Mock()
        app.show_new_file_dialog = mock.Mock()

        app._dispatch_window_result(
            self.actions_mod.ActionResult(self.actions_mod.ActionType.REQUEST_COPY_ENTRY),
            source,
        )
        app._dispatch_window_result(
            self.actions_mod.ActionResult(self.actions_mod.ActionType.REQUEST_MOVE_ENTRY),
            source,
        )
        app._dispatch_window_result(
            self.actions_mod.ActionResult(self.actions_mod.ActionType.REQUEST_NEW_DIR),
            source,
        )
        app._dispatch_window_result(
            self.actions_mod.ActionResult(self.actions_mod.ActionType.REQUEST_NEW_FILE),
            source,
        )

        app.show_copy_dialog.assert_called_once_with(source)
        app.show_move_dialog.assert_called_once_with(source)
        app.show_new_dir_dialog.assert_called_once_with(source)
        app.show_new_file_dialog.assert_called_once_with(source)

    def test_dispatch_request_kill_confirm_calls_dialog_builder(self):
        app = self._make_app()
        source = object()
        payload = {"pid": 123, "command": "bash", "signal": 15}
        app.show_kill_confirm_dialog = mock.Mock()

        app._dispatch_window_result(
            self.actions_mod.ActionResult(
                self.actions_mod.ActionType.REQUEST_KILL_CONFIRM,
                payload,
            ),
            source,
        )

        app.show_kill_confirm_dialog.assert_called_once_with(source, payload)

    def test_dispatch_execute_non_close_routes_to_execute_action(self):
        app = self._make_app()
        app.execute_action = mock.Mock()
        result = self.actions_mod.ActionResult(
            self.actions_mod.ActionType.EXECUTE,
            self.actions_mod.AppAction.ABOUT,
        )

        app._dispatch_window_result(result, source_win=None)

        app.execute_action.assert_called_once_with(self.actions_mod.AppAction.ABOUT)

    def test_dispatch_save_error_creates_dialog(self):
        app = self._make_app()
        result = self.actions_mod.ActionResult(
            self.actions_mod.ActionType.SAVE_ERROR, "disk full"
        )

        app._dispatch_window_result(result, source_win=None)

        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "Save Error")
        self.assertIn("disk full", app.dialog.message)

    def test_dispatch_generic_error_creates_error_dialog(self):
        app = self._make_app()
        result = self.actions_mod.ActionResult(
            self.actions_mod.ActionType.ERROR, "boom"
        )

        app._dispatch_window_result(result, source_win=None)

        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "Error")
        self.assertIn("boom", app.dialog.message)

    def test_handle_global_menu_key_executes_selected_action(self):
        app = self._make_app()
        app.menu.active = True
        app.menu.handle_key = mock.Mock(return_value=self.actions_mod.AppAction.ABOUT)
        app.execute_action = mock.Mock()

        handled = app._handle_global_menu_key(10)

        self.assertTrue(handled)
        app.menu.handle_key.assert_called_once_with(10)
        app.execute_action.assert_called_once_with(self.actions_mod.AppAction.ABOUT)

    def test_handle_menu_hotkeys_f10_toggles_global_menu(self):
        app = self._make_app()
        app.menu.active = False

        handled = app._handle_menu_hotkeys(self.curses.KEY_F10)

        self.assertTrue(handled)
        self.assertTrue(app.menu.active)
        self.assertEqual(app.menu.selected_menu, 0)
        self.assertEqual(app.menu.selected_item, 0)

    def test_handle_menu_hotkeys_escape_closes_window_menu_first(self):
        app = self._make_app()
        window_menu = types.SimpleNamespace(active=True, selected_menu=2, selected_item=4)
        active_win = types.SimpleNamespace(window_menu=window_menu)
        app.get_active_window = mock.Mock(return_value=active_win)
        app.menu.active = True

        handled = app._handle_menu_hotkeys(27)

        self.assertTrue(handled)
        self.assertFalse(window_menu.active)
        self.assertTrue(app.menu.active)

    def test_resolve_dialog_result_exit_yes_stops_app(self):
        app = self._make_app()
        app.dialog = types.SimpleNamespace(title="Exit RetroTUI", buttons=["Yes", "No"])
        app.running = True

        app._resolve_dialog_result(0)

        self.assertFalse(app.running)
        self.assertIsNone(app.dialog)

    def test_resolve_dialog_result_dispatches_input_callback_result(self):
        app = self._make_app()
        dialog = self.app_mod.InputDialog("Save As", "Enter filename:")
        dialog.value = "note.txt"
        callback_result = self.actions_mod.ActionResult(
            self.actions_mod.ActionType.REQUEST_SAVE_AS
        )
        dialog.callback = mock.Mock(return_value=callback_result)
        app.dialog = dialog
        app._dispatch_window_result = mock.Mock()
        app.get_active_window = mock.Mock(return_value="active-window")

        app._resolve_dialog_result(0)

        dialog.callback.assert_called_once_with("note.txt")
        app._dispatch_window_result.assert_called_once_with(
            callback_result, "active-window"
        )

    def test_resolve_dialog_result_dispatches_dialog_callback_result(self):
        app = self._make_app()
        dialog = self.app_mod.Dialog("Confirm", "Delete?", ["Delete", "Cancel"])
        callback_result = self.actions_mod.ActionResult(
            self.actions_mod.ActionType.ERROR, "x"
        )
        dialog.callback = mock.Mock(return_value=callback_result)
        app.dialog = dialog
        app._dispatch_window_result = mock.Mock()
        app.get_active_window = mock.Mock(return_value="active-window")

        app._resolve_dialog_result(0)

        dialog.callback.assert_called_once_with()
        app._dispatch_window_result.assert_called_once_with(
            callback_result, "active-window"
        )

    def test_handle_key_ctrl_q_executes_exit_action(self):
        app = self._make_app()
        app.execute_action = mock.Mock()

        app.handle_key(17)

        app.execute_action.assert_called_once_with(self.actions_mod.AppAction.EXIT)

    def test_handle_key_tab_cycles_focus_between_visible_windows(self):
        app = self._make_app()
        win_a = types.SimpleNamespace(visible=True, active=True)
        win_b = types.SimpleNamespace(visible=True, active=False)
        app.windows = [win_a, win_b]

        app.handle_key(9)

        self.assertFalse(win_a.active)
        self.assertTrue(win_b.active)

    def test_handle_mouse_invalid_payload_is_ignored(self):
        app = self._make_app()
        app.selected_icon = 7

        app.handle_mouse((1, 2, 3))

        self.assertEqual(app.selected_icon, 7)

    def test_handle_mouse_desktop_click_selects_icon(self):
        app = self._make_app()
        app.handle_taskbar_click = mock.Mock(return_value=False)
        app.get_icon_at = mock.Mock(return_value=0)
        app.execute_action = mock.Mock()

        app.handle_mouse((0, 10, 6, 0, self.curses.BUTTON1_CLICKED))

        self.assertEqual(app.selected_icon, 0)
        app.execute_action.assert_not_called()

    def test_handle_mouse_desktop_double_click_executes_icon_action(self):
        app = self._make_app()
        app.handle_taskbar_click = mock.Mock(return_value=False)
        app.get_icon_at = mock.Mock(return_value=0)
        app.execute_action = mock.Mock()

        app.handle_mouse((0, 10, 6, 0, self.curses.BUTTON1_DOUBLE_CLICKED))

        app.execute_action.assert_called_once_with(self.actions_mod.AppAction.ABOUT)

    def test_handle_mouse_desktop_fallback_double_click_executes_icon_action(self):
        app = self._make_app()
        app.handle_taskbar_click = mock.Mock(return_value=False)
        app.get_icon_at = mock.Mock(return_value=0)
        app.execute_action = mock.Mock()

        with mock.patch.object(self.app_mod.time, "monotonic", side_effect=[10.0, 10.2]):
            app.handle_mouse((0, 10, 6, 0, self.curses.BUTTON1_CLICKED))
            app.handle_mouse((0, 10, 6, 0, self.curses.BUTTON1_CLICKED))

        app.execute_action.assert_called_once_with(self.actions_mod.AppAction.ABOUT)

    def test_run_delegates_to_event_loop(self):
        app = self._make_app()

        with mock.patch.object(self.app_mod, "run_app_loop") as runner:
            app.run()

        runner.assert_called_once_with(app)

    def test_validate_terminal_size_raises_for_small_terminal(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (10, 40))

        with self.assertRaises(ValueError):
            app._validate_terminal_size()

    def test_get_icon_at_returns_matching_index(self):
        app = self._make_app()
        app.icons = [
            {"art": ["1234"], "label": "A", "action": self.actions_mod.AppAction.ABOUT},
            {"art": ["1234"], "label": "B", "action": self.actions_mod.AppAction.ABOUT},
        ]

        self.assertEqual(app.get_icon_at(3, 3), 0)
        self.assertEqual(app.get_icon_at(3, 8), 1)
        self.assertEqual(app.get_icon_at(100, 100), -1)

    def test_set_active_window_reorders_z_order(self):
        app = self._make_app()
        a = types.SimpleNamespace(active=True, always_on_top=False)
        b = types.SimpleNamespace(active=False, always_on_top=False)
        c = types.SimpleNamespace(active=False, always_on_top=False)
        app.windows = [a, b, c]

        app.set_active_window(b)

        self.assertFalse(a.active)
        self.assertFalse(c.active)
        self.assertTrue(b.active)
        self.assertEqual(app.windows[-1], b)

    def test_set_active_window_keeps_regular_below_topmost(self):
        app = self._make_app()
        regular_a = types.SimpleNamespace(active=False, always_on_top=False)
        topmost = types.SimpleNamespace(active=False, always_on_top=True)
        regular_b = types.SimpleNamespace(active=False, always_on_top=False)
        app.windows = [regular_a, topmost, regular_b]

        app.set_active_window(regular_a)

        self.assertTrue(regular_a.active)
        self.assertEqual(app.windows, [regular_b, regular_a, topmost])

    def test_normalize_window_layers_moves_topmost_to_end(self):
        app = self._make_app()
        regular_a = types.SimpleNamespace(active=False, always_on_top=False)
        topmost_a = types.SimpleNamespace(active=False, always_on_top=True)
        regular_b = types.SimpleNamespace(active=False, always_on_top=False)
        topmost_b = types.SimpleNamespace(active=False, always_on_top=True)
        app.windows = [topmost_a, regular_a, topmost_b, regular_b]

        app.normalize_window_layers()

        self.assertEqual(app.windows, [regular_a, regular_b, topmost_a, topmost_b])

    def test_close_window_activates_last_remaining_window(self):
        app = self._make_app()
        a = types.SimpleNamespace(active=False)
        b = types.SimpleNamespace(active=False)
        app.windows = [a, b]

        app.close_window(a)

        self.assertEqual(app.windows, [b])
        self.assertTrue(b.active)

    def test_close_window_calls_close_hook_and_logs_failures(self):
        app = self._make_app()
        good = types.SimpleNamespace(active=False, close=mock.Mock())
        bad = types.SimpleNamespace(active=False, close=mock.Mock(side_effect=RuntimeError("boom")))
        app.windows = [good, bad]

        app.close_window(good)
        self.assertEqual(app.windows, [bad])
        good.close.assert_called_once_with()

        with mock.patch.object(self.app_mod.LOGGER, "debug") as log_debug:
            app.close_window(bad)
        bad.close.assert_called_once_with()
        log_debug.assert_called_once()

    def test_spawn_window_and_offset_helpers(self):
        app = self._make_app()
        app.windows = [types.SimpleNamespace(active=False), types.SimpleNamespace(active=False)]
        win = types.SimpleNamespace(active=False)
        app.set_active_window = mock.Mock()

        self.assertEqual(app._next_window_offset(10, 5), (14, 7))
        app._spawn_window(win)
        self.assertIn(win, app.windows)
        app.set_active_window.assert_called_once_with(win)

    def test_apply_theme_updates_state_and_calls_init_colors(self):
        app = self._make_app()

        with (
            mock.patch.object(self.app_mod, "get_theme", return_value=types.SimpleNamespace(key="hacker")) as get_theme,
            mock.patch.object(self.app_mod, "init_colors") as init_colors,
        ):
            app.apply_theme("hacker")

        get_theme.assert_called_once_with("hacker")
        init_colors.assert_called_once_with(app.theme)
        self.assertEqual(app.theme_name, "hacker")

    def test_apply_preferences_updates_defaults_and_open_windows(self):
        app = self._make_app()
        app.default_show_hidden = False
        app.default_word_wrap = False

        file_win = types.SimpleNamespace(
            show_hidden=False,
            _rebuild_content=mock.Mock(),
        )
        notepad_win = types.SimpleNamespace(
            wrap_mode=False,
            view_left=9,
            _invalidate_wrap=mock.Mock(),
            _ensure_cursor_visible=mock.Mock(),
        )
        app.windows = [file_win, notepad_win]

        app.apply_preferences(
            show_hidden=True,
            word_wrap_default=True,
            apply_to_open_windows=True,
        )

        self.assertTrue(app.default_show_hidden)
        self.assertTrue(app.default_word_wrap)
        self.assertTrue(file_win.show_hidden)
        self.assertTrue(notepad_win.wrap_mode)
        self.assertEqual(notepad_win.view_left, 0)
        file_win._rebuild_content.assert_called_once_with()
        notepad_win._invalidate_wrap.assert_called_once_with()
        notepad_win._ensure_cursor_visible.assert_called_once_with()

    def test_apply_preferences_early_return_and_no_op_when_same_values(self):
        app = self._make_app()
        app.default_show_hidden = True
        app.default_word_wrap = True
        file_win = types.SimpleNamespace(show_hidden=False, _rebuild_content=mock.Mock())
        notepad_win = types.SimpleNamespace(
            wrap_mode=True,
            view_left=2,
            _invalidate_wrap=mock.Mock(),
            _ensure_cursor_visible=mock.Mock(),
        )
        app.windows = [file_win, notepad_win]

        app.apply_preferences(show_hidden=False, apply_to_open_windows=False)
        self.assertFalse(app.default_show_hidden)
        file_win._rebuild_content.assert_not_called()

        app.apply_preferences(show_hidden=False, word_wrap_default=True, apply_to_open_windows=True)
        file_win._rebuild_content.assert_not_called()
        notepad_win._invalidate_wrap.assert_not_called()

    def test_persist_config_builds_dataclass_and_calls_save(self):
        app = self._make_app()
        app.theme_name = "amiga"
        app.default_show_hidden = True
        app.default_word_wrap = False

        with mock.patch.object(self.app_mod, "save_config", return_value="/tmp/config.toml") as save_config:
            result = app.persist_config()

        self.assertEqual(result, "/tmp/config.toml")
        save_config.assert_called_once_with(app.config)
        self.assertEqual(app.config.theme, "amiga")
        self.assertTrue(app.config.show_hidden)
        self.assertFalse(app.config.word_wrap_default)

    def test_open_file_viewer_video_error_opens_dialog(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))

        with (
            mock.patch.object(self.app_mod, "is_video_file", return_value=True),
            mock.patch.object(self.app_mod, "play_ascii_video", return_value=(False, "mpv missing")),
        ):
            app.open_file_viewer("/tmp/demo.mp4")

        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "ASCII Video Error")
        self.assertIn("mpv missing", app.dialog.message)

    def test_open_file_viewer_binary_file_opens_warning_dialog(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))

        with (
            mock.patch.object(self.app_mod, "is_video_file", return_value=False),
            mock.patch("builtins.open", mock.mock_open(read_data=b"\x00\x01binary")),
        ):
            app.open_file_viewer("/tmp/bin.dat")

        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "Binary File")
        self.assertIn("binary file", app.dialog.message)

    def test_open_file_viewer_binary_probe_oserror_still_opens_notepad(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        app.windows = []
        app._spawn_window = mock.Mock()

        with (
            mock.patch.object(self.app_mod, "is_video_file", return_value=False),
            mock.patch("builtins.open", side_effect=OSError("cannot read")),
            mock.patch.object(self.app_mod, "NotepadWindow") as notepad_cls,
        ):
            app.open_file_viewer("/tmp/readme.txt")

        app._spawn_window.assert_called_once_with(notepad_cls.return_value)

    def test_open_file_viewer_text_spawns_notepad_window(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        app.windows = [types.SimpleNamespace(active=False), types.SimpleNamespace(active=True)]
        app._spawn_window = mock.Mock()

        with (
            mock.patch.object(self.app_mod, "is_video_file", return_value=False),
            mock.patch("builtins.open", mock.mock_open(read_data=b"plain text")),
            mock.patch.object(self.app_mod, "NotepadWindow") as notepad_cls,
        ):
            app.open_file_viewer("/tmp/readme.txt")

        notepad_cls.assert_called_once()
        app._spawn_window.assert_called_once_with(notepad_cls.return_value)

    def test_open_file_viewer_log_extension_spawns_log_viewer(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        app.windows = []
        app._spawn_window = mock.Mock()

        with (
            mock.patch.object(self.app_mod, "is_video_file", return_value=False),
            mock.patch.object(self.app_mod, "LogViewerWindow") as log_cls,
        ):
            app.open_file_viewer("/var/log/syslog.log")

        log_cls.assert_called_once()
        app._spawn_window.assert_called_once_with(log_cls.return_value)

    def test_show_save_as_dialog_sets_callback(self):
        app = self._make_app()
        target = types.SimpleNamespace(save_as=mock.Mock(return_value=True))

        app.show_save_as_dialog(target)

        self.assertIsInstance(app.dialog, self.app_mod.InputDialog)
        result = app.dialog.callback("demo.txt")
        target.save_as.assert_called_once_with("demo.txt")
        self.assertTrue(result)

    def test_show_open_dialog_sets_callback(self):
        app = self._make_app()
        target = types.SimpleNamespace(open_path=mock.Mock(return_value=None))

        app.show_open_dialog(target)

        self.assertIsInstance(app.dialog, self.app_mod.InputDialog)
        result = app.dialog.callback("demo.txt")
        target.open_path.assert_called_once_with("demo.txt")
        self.assertIsNone(result)

    def test_show_rename_dialog_sets_callback(self):
        app = self._make_app()
        entry = types.SimpleNamespace(name="a.txt")
        target = types.SimpleNamespace(
            _selected_entry=mock.Mock(return_value=entry),
            rename_selected=mock.Mock(return_value=None),
        )

        app.show_rename_dialog(target)

        self.assertIsInstance(app.dialog, self.app_mod.InputDialog)
        result = app.dialog.callback("b.txt")
        target.rename_selected.assert_called_once_with("b.txt")
        self.assertIsNone(result)

    def test_show_delete_confirm_dialog_sets_callback(self):
        app = self._make_app()
        entry = types.SimpleNamespace(name="a.txt", is_dir=False)
        target = types.SimpleNamespace(
            _selected_entry=mock.Mock(return_value=entry),
            delete_selected=mock.Mock(return_value=None),
        )

        app.show_delete_confirm_dialog(target)

        self.assertIsInstance(app.dialog, self.app_mod.Dialog)
        result = app.dialog.callback()
        target.delete_selected.assert_called_once_with()
        self.assertIsNone(result)

    def test_show_copy_and_move_dialogs_set_callbacks(self):
        app = self._make_app()
        entry = types.SimpleNamespace(name="a.txt", is_dir=False)
        target = types.SimpleNamespace(
            current_path="/tmp",
            _selected_entry=mock.Mock(return_value=entry),
            copy_selected=mock.Mock(return_value=None),
            move_selected=mock.Mock(return_value=None),
        )

        app.show_copy_dialog(target)
        self.assertIsInstance(app.dialog, self.app_mod.InputDialog)
        result_copy = app.dialog.callback("/tmp/dst")
        target.copy_selected.assert_called_once_with("/tmp/dst")
        self.assertIsNone(result_copy)

        app.show_move_dialog(target)
        self.assertIsInstance(app.dialog, self.app_mod.InputDialog)
        result_move = app.dialog.callback("/tmp/dst2")
        target.move_selected.assert_called_once_with("/tmp/dst2")
        self.assertIsNone(result_move)

    def test_run_file_operation_with_progress_runs_sync_for_small_file(self):
        app = self._make_app()
        entry = types.SimpleNamespace(name="tiny.txt", is_dir=False, size=128, full_path="/tmp/tiny.txt")
        target = types.SimpleNamespace(
            selected_entry_for_operation=mock.Mock(return_value=entry),
            copy_selected=mock.Mock(return_value=None),
        )

        result = app._run_file_operation_with_progress(target, operation="copy", destination="/tmp/out")

        self.assertIsNone(result)
        target.copy_selected.assert_called_once_with("/tmp/out")

    def test_run_file_operation_with_progress_starts_background_for_large_file(self):
        app = self._make_app()
        entry = types.SimpleNamespace(name="big.iso", is_dir=False, size=16 * 1024 * 1024, full_path="/tmp/big.iso")
        target = types.SimpleNamespace(
            selected_entry_for_operation=mock.Mock(return_value=entry),
            move_selected=mock.Mock(return_value=None),
        )

        with mock.patch.object(app, "_start_background_operation", return_value=None) as start_bg:
            result = app._run_file_operation_with_progress(
                target,
                operation="move",
                destination="/tmp/out",
            )

        self.assertIsNone(result)
        start_bg.assert_called_once()
        self.assertEqual(start_bg.call_args.kwargs["title"], "Moving")
        self.assertIs(start_bg.call_args.kwargs["source_win"], target)
        target.move_selected.assert_not_called()

        worker = start_bg.call_args.kwargs["worker"]
        worker()
        target.move_selected.assert_called_once_with("/tmp/out")

    def test_run_file_operation_with_progress_rejects_unsupported_operation(self):
        app = self._make_app()
        target = types.SimpleNamespace(selected_entry_for_operation=mock.Mock(return_value=None))

        result = app._run_file_operation_with_progress(target, operation="compress")

        self.assertEqual(result.type, self.actions_mod.ActionType.ERROR)

    def test_start_background_operation_rejects_when_active(self):
        app = self._make_app()
        app._background_operation = {"done": False}

        result = app._start_background_operation(
            title="Copying",
            message="x",
            worker=lambda: None,
            source_win=None,
        )

        self.assertEqual(result.type, self.actions_mod.ActionType.ERROR)

    def test_start_background_operation_starts_worker_and_sets_progress_dialog(self):
        app = self._make_app()
        worker = mock.Mock(return_value=None)

        result = app._start_background_operation(
            title="Copying",
            message="copying...",
            worker=worker,
            source_win=None,
        )

        self.assertIsNone(result)
        self.assertTrue(app.has_background_operation())
        self.assertIsInstance(app.dialog, self.app_mod.ProgressDialog)

        for _ in range(50):
            state = app._background_operation
            if state and state.get("done"):
                break
            time.sleep(0.01)

        app._dispatch_window_result = mock.Mock()
        app.poll_background_operation()
        worker.assert_called_once_with()
        self.assertIsNone(app._background_operation)

    def test_poll_background_operation_keeps_state_while_worker_running(self):
        app = self._make_app()
        progress_dialog = types.SimpleNamespace(set_elapsed=mock.Mock())
        app._dispatch_window_result = mock.Mock()
        app._background_operation = {
            "dialog": progress_dialog,
            "source_win": None,
            "worker_result": None,
            "done": False,
            "started_at": 1.0,
            "thread": None,
        }

        with mock.patch.object(self.app_mod.time, "monotonic", return_value=2.0):
            app.poll_background_operation()

        progress_dialog.set_elapsed.assert_called_once_with(1.0)
        self.assertIsNotNone(app._background_operation)
        app._dispatch_window_result.assert_not_called()

    def test_poll_background_operation_updates_and_dispatches_completion(self):
        app = self._make_app()
        finished = self.actions_mod.ActionResult(self.actions_mod.ActionType.ERROR, "boom")
        progress_dialog = types.SimpleNamespace(set_elapsed=mock.Mock())
        source = object()
        app._dispatch_window_result = mock.Mock()
        app.dialog = progress_dialog
        app._background_operation = {
            "dialog": progress_dialog,
            "source_win": source,
            "worker_result": finished,
            "done": True,
            "started_at": 10.0,
            "thread": None,
        }

        with mock.patch.object(self.app_mod.time, "monotonic", return_value=12.5):
            app.poll_background_operation()

        progress_dialog.set_elapsed.assert_called_once_with(2.5)
        self.assertIsNone(app.dialog)
        self.assertIsNone(app._background_operation)
        app._dispatch_window_result.assert_called_once_with(finished, source)

    def test_resolve_dialog_result_keeps_dialog_replaced_by_callback(self):
        app = self._make_app()
        replacement = object()

        def _callback():
            app.dialog = replacement
            return None

        app.dialog = types.SimpleNamespace(title="Any", buttons=["OK"], callback=_callback)
        app._resolve_dialog_result(0)

        self.assertIs(app.dialog, replacement)

    def test_cleanup_joins_background_thread_when_alive(self):
        app = self._make_app()
        fake_thread = types.SimpleNamespace(is_alive=mock.Mock(return_value=True), join=mock.Mock())
        app._background_operation = {"thread": fake_thread}

        with mock.patch.object(self.app_mod, "disable_mouse_support") as disable_mouse_support:
            app.cleanup()

        fake_thread.join.assert_called_once_with(timeout=0.2)
        disable_mouse_support.assert_called_once_with()

    def test_show_new_dir_and_file_dialogs_set_callbacks(self):
        app = self._make_app()
        target = types.SimpleNamespace(
            create_directory=mock.Mock(return_value=None),
            create_file=mock.Mock(return_value=None),
        )

        app.show_new_dir_dialog(target)
        self.assertIsInstance(app.dialog, self.app_mod.InputDialog)
        result_dir = app.dialog.callback("folder")
        target.create_directory.assert_called_once_with("folder")
        self.assertIsNone(result_dir)

        app.show_new_file_dialog(target)
        self.assertIsInstance(app.dialog, self.app_mod.InputDialog)
        result_file = app.dialog.callback("file.txt")
        target.create_file.assert_called_once_with("file.txt")
        self.assertIsNone(result_file)

    def test_show_kill_confirm_dialog_sets_callback(self):
        app = self._make_app()
        payload = {"pid": 42, "command": "python app.py", "signal": 15}
        target = types.SimpleNamespace(kill_process=mock.Mock(return_value=None))

        app.show_kill_confirm_dialog(target, payload)

        self.assertIsInstance(app.dialog, self.app_mod.Dialog)
        result = app.dialog.callback()
        target.kill_process.assert_called_once_with(payload)
        self.assertIsNone(result)

    def test_show_kill_confirm_dialog_handles_missing_pid(self):
        app = self._make_app()
        target = types.SimpleNamespace()

        app.show_kill_confirm_dialog(target, {"command": "missing pid"})

        self.assertEqual(app.dialog.title, "Kill Error")

    def test_show_copy_move_dialogs_reject_invalid_selection(self):
        app = self._make_app()
        invalid = types.SimpleNamespace(
            current_path="/tmp",
            _selected_entry=mock.Mock(return_value=None),
        )
        app.show_copy_dialog(invalid)
        self.assertEqual(app.dialog.title, "Copy Error")

        invalid_parent = types.SimpleNamespace(
            current_path="/tmp",
            _selected_entry=mock.Mock(return_value=types.SimpleNamespace(name="..", is_dir=True)),
        )
        app.show_move_dialog(invalid_parent)
        self.assertEqual(app.dialog.title, "Move Error")

    def test_get_active_window_and_dispatch_ignore_paths(self):
        app = self._make_app()
        app.windows = [types.SimpleNamespace(active=False), types.SimpleNamespace(active=True)]
        self.assertIsNotNone(app.get_active_window())
        app.windows = [types.SimpleNamespace(active=False)]
        self.assertIsNone(app.get_active_window())

        app._dispatch_window_result(True, source_win=None)
        app._dispatch_window_result("invalid", source_win=None)
        self.assertIsNone(app.dialog)

    def test_dispatch_unhandled_action_type_logs_debug(self):
        app = self._make_app()
        unknown = self.actions_mod.ActionResult("mystery", "payload")

        with mock.patch.object(self.app_mod.LOGGER, "debug") as debug_log:
            app._dispatch_window_result(unknown, source_win=None)

        self.assertTrue(any("Unhandled ActionResult type" in str(call.args[0]) for call in debug_log.call_args_list if call.args))

    def test_handle_taskbar_click_restores_minimized_window(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        minimized = types.SimpleNamespace(
            minimized=True,
            title="Minimized",
            toggle_minimize=mock.Mock(),
        )
        normal = types.SimpleNamespace(minimized=False, title="Normal")
        app.windows = [normal, minimized]
        app.set_active_window = mock.Mock()

        handled = app.handle_taskbar_click(2, 28)  # taskbar row = h - 2

        self.assertTrue(handled)
        minimized.toggle_minimize.assert_called_once_with()
        app.set_active_window.assert_called_once_with(minimized)

    def test_handle_taskbar_click_false_paths(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        app.windows = []

        self.assertFalse(app.handle_taskbar_click(2, 10))  # not taskbar row
        self.assertFalse(app.handle_taskbar_click(2, 28))  # taskbar row but no minimized

        minimized = types.SimpleNamespace(minimized=True, title="One", toggle_minimize=mock.Mock())
        app.windows = [minimized]
        app.set_active_window = mock.Mock()
        self.assertFalse(app.handle_taskbar_click(119, 28))  # misses button area

    def test_resolve_dialog_result_ignores_invalid_index_or_missing_dialog(self):
        app = self._make_app()
        app.dialog = types.SimpleNamespace(title="Any", buttons=["OK"])
        app._resolve_dialog_result(-1)
        self.assertIsNotNone(app.dialog)

        app.dialog = None
        app._resolve_dialog_result(0)
        self.assertIsNone(app.dialog)

    def test_dialog_mouse_and_key_handlers(self):
        app = self._make_app()
        app.dialog = types.SimpleNamespace(
            handle_click=mock.Mock(return_value=0),
            handle_key=mock.Mock(return_value=0),
        )
        app._resolve_dialog_result = mock.Mock()

        handled_mouse_non_click = app._handle_dialog_mouse(1, 1, 0)
        handled_mouse_click = app._handle_dialog_mouse(1, 1, app.click_flags)
        handled_key = app._handle_dialog_key(10)

        self.assertTrue(handled_mouse_non_click)
        self.assertTrue(handled_mouse_click)
        self.assertTrue(handled_key)
        app._resolve_dialog_result.assert_called()


if __name__ == "__main__":
    unittest.main()

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
            "retrotui.core.viewer",
            "retrotui.core.plugin_manager",
            "retrotui.core.app",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.app_mod = importlib.import_module("retrotui.core.app")
        cls.viewer_mod = importlib.import_module("retrotui.core.viewer")
        cls.plugin_mod = importlib.import_module("retrotui.core.plugin_manager")
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
            "retrotui.core.viewer",
            "retrotui.core.plugin_manager",
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
        app.show_welcome = True
        app.icon_positions = {}
        app._dragging_win = None
        app._resizing_win = None
        app._last_icon_click_idx = None
        app._last_icon_click_ts = 0.0
        app.double_click_interval = 0.4
        app.drag_drop = self.app_mod.DragDropManager(app)
        # Wire event bus so tests run in the same mode as production.
        from retrotui.core.event_bus import EventBus
        app._event_bus = EventBus()
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
            mock.patch.object(self.app_mod, "load_config", return_value=types.SimpleNamespace(theme="win31", show_hidden=False, word_wrap_default=False, sunday_first=False, show_welcome=True, hidden_icons="", hidden_menu_items="")),
            mock.patch.object(self.app_mod, "configure_terminal") as configure_terminal,
            mock.patch.object(self.app_mod, "disable_flow_control") as disable_flow_control,
            mock.patch.object(self.app_mod, "enable_mouse_support", return_value=(11, 22, 33)),
            mock.patch.object(self.app_mod, "init_colors") as init_colors,
            mock.patch("retrotui.ui.menu.Menu", return_value=fake_menu),
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
        self.assertGreaterEqual(len(app.icons), len(self.app_mod.ICONS))
        expected = {(icon.get("label"), icon.get("action")) for icon in self.app_mod.ICONS}
        current = {(icon.get("label"), icon.get("action")) for icon in app.icons}
        self.assertTrue(expected.issubset(current))

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
            mock.patch.object(self.app_mod, "load_config", return_value=types.SimpleNamespace(theme="win31", show_hidden=False, word_wrap_default=False, sunday_first=False, show_welcome=True, hidden_icons="", hidden_menu_items="")),
            mock.patch.object(self.app_mod, "configure_terminal"),
            mock.patch.object(self.app_mod, "disable_flow_control"),
            mock.patch.object(self.app_mod, "enable_mouse_support", return_value=(1, 2, 3)),
            mock.patch.object(self.app_mod, "init_colors"),
            mock.patch("retrotui.ui.menu.Menu", return_value=fake_menu),
            mock.patch.object(self.app_mod, "build_welcome_content", return_value=["welcome"]),
            mock.patch.object(self.app_mod, "Window", return_value=types.SimpleNamespace(active=False)),
        ):
            app = self.app_mod.RetroTUI(stdscr)

        self.assertGreaterEqual(len(app.icons), len(self.app_mod.ICONS_ASCII))
        expected = {(icon.get("label"), icon.get("action")) for icon in self.app_mod.ICONS_ASCII}
        current = {(icon.get("label"), icon.get("action")) for icon in app.icons}
        self.assertTrue(expected.issubset(current))

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

        draw_desktop.assert_called_once_with(app, frame_size=None)
        draw_icons.assert_called_once_with(app, frame_size=None)
        draw_taskbar.assert_called_once_with(app, frame_size=None)
        draw_statusbar.assert_called_once_with(app, self.app_mod.APP_VERSION, frame_size=None)

    def test_draw_wrappers_forward_optional_frame_size(self):
        app = self._make_app()
        frame_size = (25, 80)

        with (
            mock.patch.object(self.app_mod, "draw_desktop", return_value="desktop") as draw_desktop,
            mock.patch.object(self.app_mod, "draw_icons", return_value="icons") as draw_icons,
            mock.patch.object(self.app_mod, "draw_taskbar", return_value="taskbar") as draw_taskbar,
            mock.patch.object(self.app_mod, "draw_statusbar", return_value="status") as draw_statusbar,
        ):
            self.assertEqual(app.draw_desktop(frame_size=frame_size), "desktop")
            self.assertEqual(app.draw_icons(frame_size=frame_size), "icons")
            self.assertEqual(app.draw_taskbar(frame_size=frame_size), "taskbar")
            self.assertEqual(app.draw_statusbar(frame_size=frame_size), "status")

        draw_desktop.assert_called_once_with(app, frame_size=frame_size)
        draw_icons.assert_called_once_with(app, frame_size=frame_size)
        draw_taskbar.assert_called_once_with(app, frame_size=frame_size)
        draw_statusbar.assert_called_once_with(
            app,
            self.app_mod.APP_VERSION,
            frame_size=frame_size,
        )

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

    def test_execute_action_invokes_callable_actions(self):
        app = self._make_app()
        called = {"ok": False}

        def _action():
            called["ok"] = True
            return None

        with mock.patch.object(self.app_mod, "execute_app_action") as runner:
            app.execute_action(_action)

        self.assertTrue(called["ok"])
        runner.assert_not_called()

    def test_execute_action_callable_failure_is_logged_and_ignored(self):
        app = self._make_app()

        def _action():
            raise RuntimeError("boom")

        with (
            mock.patch.object(self.app_mod, "execute_app_action") as runner,
            mock.patch.object(self.app_mod.LOGGER, "debug") as log_debug,
        ):
            app.execute_action(_action)

        runner.assert_not_called()
        self.assertTrue(
            any(
                call.args and "callable action failed" in str(call.args[0])
                for call in log_debug.call_args_list
            )
        )

    def test_open_plugin_build_failure_is_logged_and_does_not_spawn(self):
        app = self._make_app()
        bad_cls = mock.Mock(side_effect=RuntimeError("bad plugin"))
        app._plugins = {
            "demo": {
                "class": bad_cls,
                "manifest": {
                    "plugin": {
                        "id": "demo",
                        "name": "Demo",
                        "window": {"default_width": 40, "default_height": 15},
                    }
                },
            }
        }
        app._spawn_window = mock.Mock()
        app._next_window_offset = mock.Mock(return_value=(8, 3))

        with mock.patch.object(self.plugin_mod.LOGGER, "debug") as log_debug:
            app.open_plugin("demo")

        app._spawn_window.assert_not_called()
        self.assertTrue(
            any(
                call.args and "failed to open plugin" in str(call.args[0])
                for call in log_debug.call_args_list
            )
        )

    def test_register_plugin_manifest_load_error_is_logged_and_ignored(self):
        app = self._make_app()
        app._plugins = {}
        load_plugin = mock.Mock(side_effect=ValueError("bad manifest"))
        manifest = {"plugin": {"id": "demo"}}

        with mock.patch.object(self.plugin_mod.LOGGER, "debug") as log_debug:
            app._register_plugin_manifest(manifest, load_plugin)

        load_plugin.assert_called_once_with(manifest)
        self.assertEqual(app._plugins, {})
        self.assertTrue(
            any(
                call.args and "failed to load plugin manifest" in str(call.args[0])
                for call in log_debug.call_args_list
            )
        )

    def test_load_plugins_runtime_skips_discovery_when_plugins_hidden_by_default(self):
        app = self._make_app()
        app.config = self.app_mod.AppConfig()
        app.refresh_icons = mock.Mock()
        app._rebuild_global_menu = mock.Mock()

        with mock.patch("retrotui.plugins.loader.discover_plugins") as discover_plugins:
            self.plugin_mod.load_plugins_runtime(app)

        discover_plugins.assert_not_called()
        self.assertEqual(app._plugins, {})
        app.refresh_icons.assert_called_once_with()
        app._rebuild_global_menu.assert_called_once_with()

    def test_build_global_menu_items_adds_sorted_plugins_section(self):
        app = self._make_app()
        app.config = types.SimpleNamespace(hidden_icons="", hidden_menu_items="")
        app._plugins = {
            "zeta": {"manifest": {"plugin": {"id": "zeta", "name": "Zeta Tool"}}},
            "alpha": {"manifest": {"plugin": {"id": "alpha", "name": "Alpha Tool"}}},
        }

        menu_items = app._build_global_menu_items()

        self.assertIn("Plugins", menu_items)
        self.assertEqual(
            menu_items["Plugins"],
            [("Alpha Tool", "plugin:alpha"), ("Zeta Tool", "plugin:zeta")],
        )

    def test_build_global_menu_items_shows_placeholder_when_no_plugins(self):
        app = self._make_app()
        app.config = types.SimpleNamespace(hidden_icons="", hidden_menu_items="")
        app._plugins = {}

        menu_items = app._build_global_menu_items()

        self.assertIn("Plugins", menu_items)
        self.assertEqual(menu_items["Plugins"], [("(No plugins installed)", None)])

    def test_build_global_menu_items_hides_entries_using_menu_keys(self):
        app = self._make_app()
        app.config = types.SimpleNamespace(hidden_icons="", hidden_menu_items="calculator,plugin:alpha")
        app._plugins = {
            "alpha": {"manifest": {"plugin": {"id": "alpha", "name": "Alpha Tool"}}},
            "beta": {"manifest": {"plugin": {"id": "beta", "name": "Beta Tool"}}},
        }

        menu_items = app._build_global_menu_items()

        apps_labels = [label for label, _ in menu_items.get("Apps", [])]
        self.assertNotIn("Calculator", apps_labels)
        self.assertEqual(menu_items["Plugins"], [("Beta Tool", "plugin:beta")])

    def test_build_global_menu_items_defaults_to_core_apps_only(self):
        app = self._make_app()
        app.config = self.app_mod.AppConfig()
        app._plugins = {
            "alpha": {"manifest": {"plugin": {"id": "alpha", "name": "Alpha Tool"}}},
            "game": {"manifest": {"plugin": {"id": "game", "name": "Game Tool", "category": "game"}}},
        }

        menu_items = app._build_global_menu_items()

        self.assertEqual(set(menu_items), {"File"})
        file_actions = [action for _, action in menu_items["File"] if action is not None]
        self.assertEqual(
            file_actions,
            [
                self.actions_mod.AppAction.NOTEPAD,
                self.actions_mod.AppAction.FILE_MANAGER,
                self.actions_mod.AppAction.TERMINAL,
                self.actions_mod.AppAction.EXIT,
            ],
        )

    def test_refresh_icons_includes_plugins_and_honors_hidden_keys(self):
        app = self._make_app()
        app.use_unicode = True
        app.config = types.SimpleNamespace(hidden_icons="files,plugin:alpha", hidden_menu_items="")
        app._plugins = {
            "alpha": {"manifest": {"plugin": {"id": "alpha", "name": "Alpha Tool"}}},
            "beta": {"manifest": {"plugin": {"id": "beta", "name": "Beta Tool"}}},
        }

        app.refresh_icons()
        labels = [icon.get("label") for icon in app.icons]
        actions = [icon.get("action") for icon in app.icons]

        self.assertNotIn("Files", labels)
        self.assertNotIn("Alpha Tool", labels)
        self.assertIn("Beta Tool", labels)
        self.assertIn("plugin:beta", actions)

    def test_refresh_icons_defaults_to_core_apps_only(self):
        app = self._make_app()
        app.use_unicode = True
        app.config = self.app_mod.AppConfig()
        app._plugins = {
            "alpha": {"manifest": {"plugin": {"id": "alpha", "name": "Alpha Tool"}}},
        }

        app.refresh_icons()
        actions = [icon.get("action") for icon in app.icons]

        self.assertEqual(
            actions,
            [
                self.actions_mod.AppAction.FILE_MANAGER,
                self.actions_mod.AppAction.NOTEPAD,
                self.actions_mod.AppAction.TERMINAL,
            ],
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

    def test_dispatch_request_copy_move_between_panes_routes_operation(self):
        app = self._make_app()
        source = types.SimpleNamespace(
            dual_pane_enabled=True,
            active_pane=0,
            current_path="/left",
            secondary_path="/right",
        )
        app._run_file_operation_with_progress = mock.Mock(return_value=None)

        app._dispatch_window_result(
            self.actions_mod.ActionResult(
                self.actions_mod.ActionType.REQUEST_COPY_BETWEEN_PANES,
            ),
            source,
        )
        app._dispatch_window_result(
            self.actions_mod.ActionResult(
                self.actions_mod.ActionType.REQUEST_MOVE_BETWEEN_PANES,
                {"destination": "/custom"},
            ),
            source,
        )

        app._run_file_operation_with_progress.assert_has_calls(
            [
                mock.call(source, operation="copy", destination="/right"),
                mock.call(source, operation="move", destination="/custom"),
            ]
        )

    def test_dispatch_request_between_panes_reports_missing_destination(self):
        app = self._make_app()
        source = types.SimpleNamespace(
            dual_pane_enabled=True,
            active_pane=0,
            current_path="/left",
            secondary_path="",
        )

        app._dispatch_window_result(
            self.actions_mod.ActionResult(
                self.actions_mod.ActionType.REQUEST_COPY_BETWEEN_PANES,
            ),
            source,
        )

        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "Operation Error")
        self.assertIn("destination pane path is unavailable", app.dialog.message)

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

        mouse_router_mod = importlib.import_module("retrotui.core.mouse_router")
        with mock.patch.object(mouse_router_mod.time, "monotonic", side_effect=[10.0, 10.2]):
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

    def test_close_window_prefers_last_visible_window(self):
        app = self._make_app()
        closing = types.SimpleNamespace(active=True, visible=True)
        hidden = types.SimpleNamespace(active=False, visible=False)
        visible = types.SimpleNamespace(active=False, visible=True)
        app.windows = [closing, hidden, visible]

        app.close_window(closing)

        self.assertEqual(app.windows, [hidden, visible])
        self.assertFalse(hidden.active)
        self.assertTrue(visible.active)

    def test_close_window_calls_close_hook_and_logs_failures(self):
        app = self._make_app()
        good = types.SimpleNamespace(active=False, close=mock.Mock())
        bad = types.SimpleNamespace(active=False, close=mock.Mock(side_effect=RuntimeError("boom")))
        app.windows = [good, bad]

        app.close_window(good)
        self.assertEqual(app.windows, [bad])
        good.close.assert_called_once_with()

        from retrotui.core import window_manager as wm_mod
        with mock.patch.object(wm_mod.LOGGER, "debug") as log_debug:
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
        app.default_sunday_first = True
        app.icon_style = "retro_01"
        app.config = types.SimpleNamespace(hidden_icons="some_apps", hidden_menu_items="some_menu")

        with mock.patch.object(self.app_mod, "save_config", return_value="/tmp/config.toml") as save_config:
            result = app.persist_config()

        self.assertEqual(result, "/tmp/config.toml")
        save_config.assert_called_once_with(app.config)
        self.assertEqual(app.config.theme, "amiga")
        self.assertTrue(app.config.show_hidden)
        self.assertFalse(app.config.word_wrap_default)
        self.assertTrue(app.config.sunday_first)
        self.assertEqual(app.config.icon_style, "mini")

    def test_normalize_icon_style_maps_legacy_and_invalid_values(self):
        self.assertEqual(self.app_mod.RetroTUI._normalize_icon_style("retro_01"), "mini")
        self.assertEqual(self.app_mod.RetroTUI._normalize_icon_style("MINI"), "mini")
        self.assertEqual(self.app_mod.RetroTUI._normalize_icon_style("codex"), "default")
        self.assertEqual(self.app_mod.RetroTUI._normalize_icon_style("weird"), "default")

    def test_default_icon_style_uses_classic_grid_without_symbol(self):
        app = self._make_app()
        app.icon_style = "default"
        icon = {
            "label": "Files",
            "action": self.actions_mod.AppAction.FILE_MANAGER,
            "symbol": "📁",
            "art": ["┌──┐", "│FL│", "└──┘"],
        }
        styled = app._styled_icon_entry(icon)
        self.assertNotIn("symbol", styled)
        self.assertEqual(styled.get("art"), icon["art"])

    def test_persist_config_ignores_icon_save_parse_errors(self):
        app = self._make_app()
        app.theme_name = "win31"
        app.default_show_hidden = False
        app.default_word_wrap = False
        app.default_sunday_first = False
        app.config = types.SimpleNamespace(hidden_icons="", hidden_menu_items="")
        app._save_icon_positions = mock.Mock(side_effect=ValueError("bad icons"))

        with mock.patch.object(self.app_mod, "save_config", return_value="/tmp/config.toml"):
            result = app.persist_config()

        self.assertEqual(result, "/tmp/config.toml")
        app._save_icon_positions.assert_called_once_with("/tmp/config.toml")

    def test_open_file_viewer_video_error_opens_dialog(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))

        with (
            mock.patch.object(self.viewer_mod, "is_video_file", return_value=True),
            mock.patch.object(self.viewer_mod, "_play_ascii_video_backend", return_value=(False, "mpv missing")),
        ):
            app.open_file_viewer("/tmp/demo.mp4")

        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "ASCII Video Error")
        self.assertIn("mpv missing", app.dialog.message)

    def test_play_ascii_video_helper_success_and_error(self):
        app = self._make_app()

        with mock.patch.object(self.viewer_mod, "_play_ascii_video_backend", return_value=(True, None)) as player:
            app._play_ascii_video("/tmp/demo.mp4")
        player.assert_called_once_with(app.stdscr, "/tmp/demo.mp4", subtitle_path=None)
        self.assertIsNone(app.dialog)

        with mock.patch.object(self.viewer_mod, "_play_ascii_video_backend", return_value=(False, "backend error")):
            app._play_ascii_video("/tmp/demo.mp4", subtitle_path="/tmp/demo.srt")
        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "ASCII Video Error")
        self.assertIn("backend error", app.dialog.message)

    def test_show_video_open_dialog_sets_input_callback(self):
        app = self._make_app()
        app.show_video_open_dialog()
        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "Open Video")
        self.assertTrue(callable(getattr(app.dialog, "callback", None)))

    def test_handle_video_path_input_validation_and_subtitle_prompt(self):
        app = self._make_app()

        result = app._handle_video_path_input("")
        self.assertEqual(result.type, self.actions_mod.ActionType.ERROR)
        self.assertIn("cannot be empty", result.payload)

        with mock.patch.object(self.viewer_mod.os.path, "isfile", return_value=False):
            result = app._handle_video_path_input("/tmp/missing.mp4")
        self.assertEqual(result.type, self.actions_mod.ActionType.ERROR)
        self.assertIn("not found", result.payload)

        with (
            mock.patch.object(self.viewer_mod.os.path, "isfile", return_value=True),
            mock.patch.object(self.viewer_mod, "is_video_file", return_value=False),
        ):
            result = app._handle_video_path_input("/tmp/demo.txt")
        self.assertEqual(result.type, self.actions_mod.ActionType.ERROR)
        self.assertIn("Unsupported video format", result.payload)

        with (
            mock.patch.object(self.viewer_mod.os.path, "isfile", return_value=True),
            mock.patch.object(self.viewer_mod, "is_video_file", return_value=True),
        ):
            result = app._handle_video_path_input("/tmp/demo.mp4")
        self.assertIsNone(result)
        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "Subtitles (Optional)")
        self.assertTrue(callable(getattr(app.dialog, "callback", None)))

    def test_handle_subtitle_path_input_validation_and_playback(self):
        app = self._make_app()

        with mock.patch.object(self.viewer_mod.os.path, "isfile", return_value=False):
            result = app._handle_subtitle_path_input("/tmp/demo.mp4", "/tmp/missing.srt")
        self.assertEqual(result.type, self.actions_mod.ActionType.ERROR)
        self.assertIn("Subtitle file not found", result.payload)

        with (
            mock.patch.object(self.viewer_mod.os.path, "isfile", return_value=True),
            mock.patch.object(self.viewer_mod, "_play_ascii_video_backend", return_value=(True, None)),
        ):
            result = app._handle_subtitle_path_input("/tmp/demo.mp4", "/tmp/demo.srt")
        self.assertIsNone(result)

        with mock.patch.object(self.viewer_mod, "_play_ascii_video_backend", return_value=(True, None)) as player:
            result = app._handle_subtitle_path_input("/tmp/demo.mp4", "")
        self.assertIsNone(result)
        player.assert_called_once_with(app.stdscr, "/tmp/demo.mp4", subtitle_path=None)

    def test_open_file_viewer_binary_file_spawns_hex_viewer(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        app.windows = []
        app._spawn_window = mock.Mock()

        with (
            mock.patch.object(self.viewer_mod, "is_video_file", return_value=False),
            mock.patch("builtins.open", mock.mock_open(read_data=b"\x00\x01binary")),
            mock.patch.object(self.viewer_mod, "HexViewerWindow") as hex_cls,
        ):
            app.open_file_viewer("/tmp/bin.dat")

        hex_cls.assert_called_once()
        app._spawn_window.assert_called_once_with(hex_cls.return_value)

    def test_open_file_viewer_binary_probe_oserror_still_opens_notepad(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        app.windows = []
        app._spawn_window = mock.Mock()

        with (
            mock.patch.object(self.viewer_mod, "is_video_file", return_value=False),
            mock.patch("builtins.open", side_effect=OSError("cannot read")),
            mock.patch.object(self.viewer_mod, "NotepadWindow") as notepad_cls,
        ):
            app.open_file_viewer("/tmp/readme.txt")

        app._spawn_window.assert_called_once_with(notepad_cls.return_value)

    def test_open_file_viewer_text_spawns_notepad_window(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        app.windows = [types.SimpleNamespace(active=False), types.SimpleNamespace(active=True)]
        app._spawn_window = mock.Mock()

        with (
            mock.patch.object(self.viewer_mod, "is_video_file", return_value=False),
            mock.patch("builtins.open", mock.mock_open(read_data=b"plain text")),
            mock.patch.object(self.viewer_mod, "NotepadWindow") as notepad_cls,
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
            mock.patch.object(self.viewer_mod, "is_video_file", return_value=False),
            mock.patch.object(self.viewer_mod, "LogViewerWindow") as log_cls,
        ):
            app.open_file_viewer("/var/log/syslog.log")

        log_cls.assert_called_once()
        app._spawn_window.assert_called_once_with(log_cls.return_value)

    def test_open_file_viewer_image_extension_spawns_image_viewer(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        app.windows = []
        app._spawn_window = mock.Mock()

        with (
            mock.patch.object(self.viewer_mod, "is_video_file", return_value=False),
            mock.patch.object(self.viewer_mod, "ImageViewerWindow") as image_cls,
        ):
            image_cls.IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif"}
            app.open_file_viewer("/tmp/demo.png")

        image_cls.assert_called_once()
        app._spawn_window.assert_called_once_with(image_cls.return_value)

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
        self.assertFalse(app._background_operation["thread"].daemon)

        for _ in range(50):
            state = app._background_operation
            if state and state.get("done"):
                break
            time.sleep(0.01)

        app._dispatch_window_result = mock.Mock()
        app.poll_background_operation()
        worker.assert_called_once_with()
        self.assertIsNone(app._background_operation)

    def test_start_background_operation_worker_error_converts_to_action_error(self):
        app = self._make_app()
        worker = mock.Mock(side_effect=ValueError("copy failed"))
        app._dispatch_window_result = mock.Mock()

        result = app._start_background_operation(
            title="Copying",
            message="copying...",
            worker=worker,
            source_win=None,
        )

        self.assertIsNone(result)
        for _ in range(50):
            state = app._background_operation
            if state and state.get("done"):
                break
            time.sleep(0.01)

        app.poll_background_operation()
        worker.assert_called_once_with()
        self.assertIsNone(app._background_operation)
        dispatched = app._dispatch_window_result.call_args.args[0]
        self.assertEqual(dispatched.type, self.actions_mod.ActionType.ERROR)
        self.assertIn("copy failed", str(dispatched.payload))

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

        file_ops_mod = importlib.import_module("retrotui.core.file_operations")
        with mock.patch.object(file_ops_mod.time, "monotonic", return_value=2.0):
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

        file_ops_mod = importlib.import_module("retrotui.core.file_operations")
        with mock.patch.object(file_ops_mod.time, "monotonic", return_value=12.5):
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
        fake_thread = types.SimpleNamespace(
            is_alive=mock.Mock(side_effect=[True, False]),
            join=mock.Mock(),
        )
        app._background_operation = {"thread": fake_thread}

        with mock.patch.object(self.app_mod, "disable_mouse_support") as disable_mouse_support:
            app.cleanup()

        fake_thread.join.assert_called_once_with(
            timeout=self.app_mod.RetroTUI.BACKGROUND_OPERATION_JOIN_TIMEOUT
        )
        disable_mouse_support.assert_called_once_with()

    def test_runtime_signal_handler_install_and_restore(self):
        app = self._make_app()
        app._pending_sigint = False
        app._prev_sigint_handler = None
        app._prev_signal_handlers = {}
        app._sigint_handler_installed = False

        expected_signals = [self.app_mod.signal.SIGINT]
        sigbreak = getattr(self.app_mod.signal, "SIGBREAK", None)
        if sigbreak is not None:
            expected_signals.append(sigbreak)
        sigtstp = getattr(self.app_mod.signal, "SIGTSTP", None)
        if sigtstp is not None:
            expected_signals.append(sigtstp)
        sigterm = getattr(self.app_mod.signal, "SIGTERM", None)
        if sigterm is not None:
            expected_signals.append(sigterm)
        sighup = getattr(self.app_mod.signal, "SIGHUP", None)
        if sighup is not None:
            expected_signals.append(sighup)

        with mock.patch.object(self.app_mod.threading, "current_thread", return_value=self.app_mod.threading.main_thread()):
            with mock.patch.object(
                self.app_mod.signal,
                "getsignal",
                side_effect=lambda sig: f"old-{sig}",
            ) as getsig:
                with mock.patch.object(self.app_mod.signal, "signal") as setsig:
                    app._install_runtime_signal_handlers()
                    self.assertTrue(app._sigint_handler_installed)
                    self.assertEqual(getsig.call_count, len(expected_signals))
                    self.assertEqual(setsig.call_count, len(expected_signals))

                    installed = {call.args[0]: call.args[1] for call in setsig.call_args_list}
                    sigint_handler = installed[self.app_mod.signal.SIGINT]
                    self.assertIs(getattr(sigint_handler, "__self__", None), app)
                    self.assertEqual(getattr(sigint_handler, "__name__", ""), "_handle_sigint")
                    if sigbreak is not None:
                        sigbreak_handler = installed[sigbreak]
                        self.assertIs(getattr(sigbreak_handler, "__self__", None), app)
                        self.assertEqual(getattr(sigbreak_handler, "__name__", ""), "_handle_sigint")
                    if sigtstp is not None:
                        sigtstp_handler = installed[sigtstp]
                        self.assertIs(getattr(sigtstp_handler, "__self__", None), app)
                        self.assertEqual(getattr(sigtstp_handler, "__name__", ""), "_handle_sigtstp")
                    if sigterm is not None:
                        sigterm_handler = installed[sigterm]
                        self.assertIs(getattr(sigterm_handler, "__self__", None), app)
                        self.assertEqual(getattr(sigterm_handler, "__name__", ""), "_handle_shutdown_signal")
                    if sighup is not None:
                        sighup_handler = installed[sighup]
                        self.assertIs(getattr(sighup_handler, "__self__", None), app)
                        self.assertEqual(getattr(sighup_handler, "__name__", ""), "_handle_shutdown_signal")

                    setsig.reset_mock()

                    app._restore_runtime_signal_handlers()
                    self.assertFalse(app._sigint_handler_installed)
                    self.assertIsNone(app._prev_sigint_handler)
                    self.assertEqual(app._prev_signal_handlers, {})
                    self.assertEqual(setsig.call_count, len(expected_signals))

    def test_runtime_signal_handler_install_is_idempotent_when_already_installed(self):
        app = self._make_app()
        app._sigint_handler_installed = True
        app._prev_signal_handlers = {self.app_mod.signal.SIGINT: "old"}
        app._prev_sigint_handler = "old"

        with (
            mock.patch.object(self.app_mod.signal, "getsignal") as getsig,
            mock.patch.object(self.app_mod.signal, "signal") as setsig,
        ):
            app._install_runtime_signal_handlers()

        getsig.assert_not_called()
        setsig.assert_not_called()
        self.assertTrue(app._sigint_handler_installed)

    def test_runtime_signal_handler_install_skips_failing_signal(self):
        app = self._make_app()
        app._pending_sigint = False
        app._prev_sigint_handler = None
        app._prev_signal_handlers = {}
        app._sigint_handler_installed = False

        failing_sig = getattr(self.app_mod.signal, "SIGTERM", None)
        if failing_sig is None:
            self.skipTest("SIGTERM not available on this platform")

        def _setsig(sig, _handler):
            if sig == failing_sig:
                raise OSError("boom")
            return None

        with mock.patch.object(self.app_mod.threading, "current_thread", return_value=self.app_mod.threading.main_thread()):
            with mock.patch.object(
                self.app_mod.signal,
                "getsignal",
                side_effect=lambda sig: f"old-{sig}",
            ):
                with mock.patch.object(self.app_mod.signal, "signal", side_effect=_setsig) as setsig:
                    app._install_runtime_signal_handlers()

        self.assertGreaterEqual(setsig.call_count, 1)
        self.assertTrue(app._sigint_handler_installed)
        self.assertIn(self.app_mod.signal.SIGINT, app._prev_signal_handlers)
        self.assertNotIn(failing_sig, app._prev_signal_handlers)

    def test_handle_sigint_queue_and_consume_once(self):
        app = self._make_app()
        app._pending_sigint = False
        app._pending_signal_keys = []

        app._handle_sigint(None, None)

        self.assertEqual(app._consume_pending_sigint(), "\x03")
        self.assertIsNone(app._consume_pending_sigint())

    def test_handle_sigtstp_queue_and_consume_signal_key(self):
        app = self._make_app()
        app._pending_sigint = False
        app._pending_signal_keys = []

        app._handle_sigtstp(None, None)

        self.assertEqual(app._consume_pending_signal_key(), "\x1a")
        self.assertIsNone(app._consume_pending_signal_key())

    def test_consume_pending_sigint_ignores_non_sigint_signal_keys(self):
        app = self._make_app()
        app._pending_sigint = False
        app._pending_signal_keys = ["\x1a"]

        self.assertIsNone(app._consume_pending_sigint())
        self.assertEqual(app._pending_signal_keys, ["\x1a"])

    def test_restore_runtime_signal_handlers_clears_state_on_signal_error(self):
        app = self._make_app()
        app._sigint_handler_installed = True
        app._prev_signal_handlers = {self.app_mod.signal.SIGINT: "old"}
        app._prev_sigint_handler = "old"
        app._shutdown_signal = 15

        with mock.patch.object(self.app_mod.signal, "signal", side_effect=OSError("denied")) as setsig:
            app._restore_runtime_signal_handlers()

        setsig.assert_called()
        self.assertFalse(app._sigint_handler_installed)
        self.assertEqual(app._prev_signal_handlers, {})
        self.assertIsNone(app._prev_sigint_handler)
        self.assertIsNone(app._shutdown_signal)

    def test_handle_shutdown_signal_requests_clean_exit(self):
        app = self._make_app()
        app.running = True
        app._shutdown_signal = None

        app._handle_shutdown_signal(15, None)

        self.assertFalse(app.running)
        self.assertEqual(app._shutdown_signal, 15)

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

        toasts = app.notifications.visible_toasts
        self.assertTrue(any("No process selected" in t.message for t in toasts))

    def test_show_copy_move_dialogs_reject_invalid_selection(self):
        app = self._make_app()
        invalid = types.SimpleNamespace(
            current_path="/tmp",
            _selected_entry=mock.Mock(return_value=None),
        )
        app.show_copy_dialog(invalid)
        # Error now shown as toast notification instead of modal dialog.
        toasts = app.notifications.visible_toasts
        self.assertTrue(any("valid item to copy" in t.message for t in toasts))

        invalid_parent = types.SimpleNamespace(
            current_path="/tmp",
            _selected_entry=mock.Mock(return_value=types.SimpleNamespace(name="..", is_dir=True)),
        )
        app.show_move_dialog(invalid_parent)
        toasts = app.notifications.visible_toasts
        self.assertTrue(any("valid item to move" in t.message for t in toasts))

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

        handled = app.handle_taskbar_click(2, 29)  # taskbar row = h - 1

        self.assertTrue(handled)
        minimized.toggle_minimize.assert_called_once_with()
        app.set_active_window.assert_called_once_with(minimized)

    def test_handle_taskbar_click_false_paths(self):
        app = self._make_app()
        app.stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))
        app.windows = []

        self.assertFalse(app.handle_taskbar_click(2, 10))  # not taskbar row
        self.assertFalse(app.handle_taskbar_click(2, 29))  # taskbar row but no minimized

        minimized = types.SimpleNamespace(minimized=True, title="One", toggle_minimize=mock.Mock())
        app.windows = [minimized]
        app.set_active_window = mock.Mock()
        self.assertFalse(app.handle_taskbar_click(119, 29))  # misses button area

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

    def test_handle_right_click_sets_active_window_and_opens_context_menu(self):
        app = self._make_app()
        app.theme = object()
        app.context_menu = None
        app.set_active_window = mock.Mock()
        win = types.SimpleNamespace(
            visible=True,
            contains=mock.Mock(return_value=True),
            handle_right_click=mock.Mock(return_value=[{"label": "Copy", "action": "copy"}]),
        )
        app.windows = [win]

        with mock.patch("retrotui.ui.context_menu.ContextMenu") as context_menu_cls:
            context_menu = context_menu_cls.return_value
            handled = app.handle_right_click(4, 5, 0)

        self.assertTrue(handled)
        app.set_active_window.assert_called_once_with(win)
        context_menu_cls.assert_called_once_with(app.theme)
        context_menu.show.assert_called_once_with(4, 5, [{"label": "Copy", "action": "copy"}])

    def test_handle_right_click_uses_open_context_menu_before_routing(self):
        app = self._make_app()
        app.context_menu = types.SimpleNamespace(
            active=True,
            handle_click=mock.Mock(return_value=None),
            is_open=mock.Mock(return_value=True),
        )
        win = types.SimpleNamespace(
            visible=True,
            contains=mock.Mock(return_value=True),
            handle_right_click=mock.Mock(return_value=[{"label": "X", "action": "x"}]),
        )
        app.windows = [win]

        handled = app.handle_right_click(10, 10, 0)

        self.assertTrue(handled)
        app.context_menu.handle_click.assert_called_once_with(10, 10)
        win.handle_right_click.assert_not_called()

    def test_handle_right_click_window_handler_route_error_falls_back_to_desktop(self):
        app = self._make_app()
        app.context_menu = None
        app.set_active_window = mock.Mock()
        app._handle_desktop_right_click = mock.Mock(return_value=True)
        win = types.SimpleNamespace(
            visible=True,
            contains=mock.Mock(return_value=True),
            handle_right_click=mock.Mock(side_effect=ValueError("bad handler")),
        )
        app.windows = [win]

        handled = app.handle_right_click(7, 8, 0)

        self.assertTrue(handled)
        app.set_active_window.assert_called_once_with(win)
        app._handle_desktop_right_click.assert_called_once_with(7, 8, 0)

    def test_handle_right_click_desktop_route_error_returns_false(self):
        app = self._make_app()
        app.context_menu = None
        app.windows = []
        app._handle_desktop_right_click = mock.Mock(side_effect=ValueError("bad desktop"))

        handled = app.handle_right_click(7, 8, 0)

        self.assertFalse(handled)
        app._handle_desktop_right_click.assert_called_once_with(7, 8, 0)

    def test_desktop_icon_properties_action_opens_dialog(self):
        app = self._make_app()
        app.theme = object()
        app.context_menu = None
        app.get_icon_at = mock.Mock(return_value=0)
        app.icons = [{"label": "Notepad", "category": "Apps", "action": self.actions_mod.AppAction.NOTEPAD}]

        with mock.patch("retrotui.ui.context_menu.ContextMenu") as context_menu_cls:
            context_menu = context_menu_cls.return_value
            app._handle_desktop_right_click(12, 8, 0)
            shown_items = context_menu.show.call_args.args[2]

        properties_action = shown_items[2]["action"]
        self.assertTrue(callable(properties_action))
        properties_action()
        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "Notepad Properties")

    def test_desktop_context_menu_includes_icon_and_menu_editors(self):
        app = self._make_app()
        app.theme = object()
        app.context_menu = None
        app.get_icon_at = mock.Mock(return_value=-1)

        with mock.patch("retrotui.ui.context_menu.ContextMenu") as context_menu_cls:
            context_menu = context_menu_cls.return_value
            handled = app._handle_desktop_right_click(12, 8, 0)
            shown_items = context_menu.show.call_args.args[2]

        self.assertTrue(handled)
        label_to_action = {
            item["label"]: item["action"]
            for item in shown_items
            if isinstance(item, dict) and "label" in item and "action" in item
        }
        self.assertEqual(
            label_to_action.get("Desktop Icons"),
            self.actions_mod.AppAction.DESKTOP_ICON_MANAGER,
        )
        self.assertEqual(
            label_to_action.get("Icons"),
            self.actions_mod.AppAction.ICONS,
        )
        self.assertEqual(
            label_to_action.get("Menu Editor"),
            self.actions_mod.AppAction.MENU_EDITOR,
        )
        self.assertTrue(callable(label_to_action.get("Sort Icons (A-Z)")))

    def test_desktop_context_menu_defaults_to_core_apps_only(self):
        app = self._make_app()
        app.config = self.app_mod.AppConfig()
        app.theme = object()
        app.context_menu = None
        app.get_icon_at = mock.Mock(return_value=-1)

        with mock.patch("retrotui.ui.context_menu.ContextMenu") as context_menu_cls:
            context_menu = context_menu_cls.return_value
            handled = app._handle_desktop_right_click(12, 8, 0)
            shown_items = context_menu.show.call_args.args[2]

        self.assertTrue(handled)
        labels = [
            item["label"]
            for item in shown_items
            if isinstance(item, dict) and "label" in item
        ]
        self.assertEqual(labels, ["File Manager", "New Terminal", "New Notepad", "Exit"])
        self.assertNotIn("Desktop Icons", labels)
        self.assertNotIn("Settings", labels)

    def test_sort_desktop_icons_delegates_to_icon_manager(self):
        app = self._make_app()
        app.selected_icon = 3
        icon_mgr = types.SimpleNamespace(sort_positions=mock.Mock(return_value={"A": (3, 3)}))

        with mock.patch.object(app, "_get_icon_mgr", return_value=icon_mgr):
            result = app.sort_desktop_icons()

        self.assertIsNone(result)
        icon_mgr.sort_positions.assert_called_once_with()
        self.assertEqual(app.selected_icon, -1)


if __name__ == "__main__":
    unittest.main()

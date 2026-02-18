import importlib
import sys
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
    return fake


class _DummyDialog:
    def __init__(self, title, message, buttons, width=None):
        self.title = title
        self.message = message
        self.buttons = buttons
        self.width = width


class _DummyWindow:
    _next_id = 99

    def __init__(self, title, x, y, w, h, content=None):
        self.title = title
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.content = content


class _DummyFMWindow:
    def __init__(self, x, y, w, h):
        self.kind = "fm"
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class _DummyNotepadWindow:
    def __init__(self, x, y, w, h):
        self.kind = "np"
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class _DummyTerminalWindow:
    def __init__(self, x, y, w, h):
        self.kind = "term"
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class _DummySettingsWindow:
    def __init__(self, x, y, w, h, app):
        self.kind = "settings"
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.app = app


class _DummyCalculatorWindow:
    def __init__(self, x, y, w, h):
        self.kind = "calc"
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class _DummyLogViewerWindow:
    def __init__(self, x, y, w, h):
        self.kind = "log"
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class _DummyProcessManagerWindow:
    def __init__(self, x, y, w, h):
        self.kind = "proc"
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class _DummyClockCalendarWindow:
    def __init__(self, x, y, w, h):
        self.kind = "clock"
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class _DummyImageViewerWindow:
    def __init__(self, x, y, w, h):
        self.kind = "image"
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class _DummyTrashWindow:
    def __init__(self, x, y, w, h):
        self.kind = "trash"
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class ActionRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
            "retrotui.ui.window",
            "retrotui.apps.notepad",
            "retrotui.apps.filemanager",
            "retrotui.apps.settings",
            "retrotui.apps.terminal",
            "retrotui.apps.calculator",
            "retrotui.apps.logviewer",
            "retrotui.apps.process_manager",
            "retrotui.apps.clock",
            "retrotui.apps.image_viewer",
            "retrotui.apps.trash",
            "retrotui.core.actions",
            "retrotui.core.content",
            "retrotui.core.action_runner",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.action_runner = importlib.import_module("retrotui.core.action_runner")

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
            "retrotui.apps.settings",
            "retrotui.apps.terminal",
            "retrotui.apps.calculator",
            "retrotui.apps.logviewer",
            "retrotui.apps.process_manager",
            "retrotui.apps.clock",
            "retrotui.apps.image_viewer",
            "retrotui.apps.trash",
            "retrotui.core.actions",
            "retrotui.core.content",
            "retrotui.core.action_runner",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_app(self):
        return types.SimpleNamespace(
            dialog=None,
            _next_window_offset=mock.Mock(return_value=(12, 7)),
            _spawn_window=mock.Mock(),
            show_video_open_dialog=mock.Mock(),
        )

    def test_execute_exit_action_opens_confirmation_dialog(self):
        app = self._make_app()
        logger = mock.Mock()

        with mock.patch.object(self.action_runner, "Dialog", _DummyDialog):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.EXIT,
                logger,
                version="0.3.4",
            )

        self.assertIsNotNone(app.dialog)
        self.assertEqual(app.dialog.title, "Exit RetroTUI")
        self.assertEqual(app.dialog.buttons, ["Yes", "No"])

    def test_execute_about_action_uses_versioned_about_message(self):
        app = self._make_app()
        logger = mock.Mock()

        with (
            mock.patch.object(self.action_runner, "Dialog", _DummyDialog),
            mock.patch.object(self.action_runner, "build_about_message", return_value="about vX") as about_builder,
        ):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.ABOUT,
                logger,
                version="0.3.4",
            )

        about_builder.assert_called_once_with("0.3.4")
        self.assertEqual(app.dialog.title, "About RetroTUI")
        self.assertIn("about vX", app.dialog.message)

    def test_execute_help_action_uses_help_builder(self):
        app = self._make_app()
        logger = mock.Mock()

        with (
            mock.patch.object(self.action_runner, "Dialog", _DummyDialog),
            mock.patch.object(self.action_runner, "build_help_message", return_value="help body") as builder,
        ):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.HELP,
                logger,
                version="0.3.4",
            )

        builder.assert_called_once_with()
        self.assertEqual(app.dialog.title, "Keyboard & Mouse Help")
        self.assertEqual(app.dialog.buttons, ["OK"])
        self.assertIn("help body", app.dialog.message)

    def test_execute_ascii_video_action_opens_video_dialog(self):
        app = self._make_app()
        logger = mock.Mock()

        self.action_runner.execute_app_action(
            app,
            self.actions_mod.AppAction.ASCII_VIDEO,
            logger,
            version="0.3.4",
        )
        app.show_video_open_dialog.assert_called_once_with()
        self.assertIsNone(app.dialog)

    def test_execute_ascii_video_action_falls_back_to_info_dialog(self):
        app = self._make_app()
        delattr(app, "show_video_open_dialog")
        logger = mock.Mock()

        with mock.patch.object(self.action_runner, "Dialog", _DummyDialog):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.ASCII_VIDEO,
                logger,
                version="0.3.4",
            )

        self.assertEqual(app.dialog.title, "ASCII Video")
        self.assertIn("mpv", app.dialog.message)
        self.assertEqual(app.dialog.buttons, ["OK"])

    def test_execute_file_manager_spawns_window_with_offset(self):
        app = self._make_app()
        logger = mock.Mock()

        with mock.patch.object(self.action_runner, "FileManagerWindow", _DummyFMWindow):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.FILE_MANAGER,
                logger,
                version="0.3.4",
            )

        app._next_window_offset.assert_called_once_with(15, 3)
        app._spawn_window.assert_called_once()
        spawned = app._spawn_window.call_args.args[0]
        self.assertEqual(spawned.kind, "fm")
        self.assertEqual((spawned.x, spawned.y, spawned.w, spawned.h), (12, 7, 58, 22))

    def test_execute_file_manager_passes_show_hidden_when_supported(self):
        app = self._make_app()
        app.default_show_hidden = True
        logger = mock.Mock()

        class _KwargFMWindow:
            def __init__(self, x, y, w, h, show_hidden_default=False):
                self.show_hidden_default = show_hidden_default

        with mock.patch.object(self.action_runner, "FileManagerWindow", _KwargFMWindow):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.FILE_MANAGER,
                logger,
                version="0.9.0",
            )

        spawned = app._spawn_window.call_args.args[0]
        self.assertTrue(spawned.show_hidden_default)

    def test_execute_file_manager_type_error_is_not_swallowed(self):
        app = self._make_app()
        logger = mock.Mock()

        class _BrokenFMWindow:
            def __init__(self, x, y, w, h, show_hidden_default=False):
                raise TypeError("internal bug")

        with mock.patch.object(self.action_runner, "FileManagerWindow", _BrokenFMWindow):
            with self.assertRaises(TypeError):
                self.action_runner.execute_app_action(
                    app,
                    self.actions_mod.AppAction.FILE_MANAGER,
                    logger,
                    version="0.9.0",
                )

    def test_execute_notepad_spawns_window_with_offset(self):
        app = self._make_app()
        logger = mock.Mock()

        with mock.patch.object(self.action_runner, "NotepadWindow", _DummyNotepadWindow):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.NOTEPAD,
                logger,
                version="0.3.4",
            )

        app._next_window_offset.assert_called_once_with(20, 4)
        spawned = app._spawn_window.call_args.args[0]
        self.assertEqual(spawned.kind, "np")
        self.assertEqual((spawned.x, spawned.y, spawned.w, spawned.h), (12, 7, 60, 20))

    def test_execute_notepad_passes_wrap_default_when_supported(self):
        app = self._make_app()
        app.default_word_wrap = True
        logger = mock.Mock()

        class _KwargNotepadWindow:
            def __init__(self, x, y, w, h, wrap_default=False):
                self.wrap_default = wrap_default

        with mock.patch.object(self.action_runner, "NotepadWindow", _KwargNotepadWindow):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.NOTEPAD,
                logger,
                version="0.9.0",
            )

        spawned = app._spawn_window.call_args.args[0]
        self.assertTrue(spawned.wrap_default)

    def test_supports_constructor_kwarg_handles_varkw_and_bad_signatures(self):
        class _VarKw:
            def __init__(self, **_kwargs):
                pass

        self.assertTrue(self.action_runner._supports_constructor_kwarg(_VarKw, "anything"))
        self.assertFalse(self.action_runner._supports_constructor_kwarg(object(), "anything"))

    def test_execute_terminal_spawns_terminal_window_with_offset(self):
        app = self._make_app()
        logger = mock.Mock()

        with (
            mock.patch.object(self.action_runner, "TerminalWindow", _DummyTerminalWindow),
        ):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.TERMINAL,
                logger,
                version="0.3.4",
            )

        app._next_window_offset.assert_called_once_with(18, 5)
        spawned = app._spawn_window.call_args.args[0]
        self.assertEqual(spawned.kind, "term")
        self.assertEqual((spawned.x, spawned.y, spawned.w, spawned.h), (12, 7, 70, 18))

    def test_execute_image_viewer_spawns_image_window(self):
        app = self._make_app()
        logger = mock.Mock()

        with mock.patch.object(self.action_runner, "ImageViewerWindow", _DummyImageViewerWindow):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.IMAGE_VIEWER,
                logger,
                version="0.9.0",
            )

        app._next_window_offset.assert_called_once_with(14, 3)
        spawned = app._spawn_window.call_args.args[0]
        self.assertEqual(spawned.kind, "image")
        self.assertEqual((spawned.x, spawned.y, spawned.w, spawned.h), (12, 7, 84, 26))

    def test_execute_trash_spawns_trash_window(self):
        app = self._make_app()
        logger = mock.Mock()

        with mock.patch.object(self.action_runner, "TrashWindow", _DummyTrashWindow):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.TRASH_BIN,
                logger,
                version="0.9.0",
            )

        app._next_window_offset.assert_called_once_with(15, 4)
        spawned = app._spawn_window.call_args.args[0]
        self.assertEqual(spawned.kind, "trash")
        self.assertEqual((spawned.x, spawned.y, spawned.w, spawned.h), (12, 7, 62, 20))

    def test_execute_settings_spawns_settings_window(self):
        app = self._make_app()
        logger = mock.Mock()

        with mock.patch.object(self.action_runner, "SettingsWindow", _DummySettingsWindow):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.SETTINGS,
                logger,
                version="0.3.4",
            )

        app._next_window_offset.assert_called_once_with(22, 4)
        spawned = app._spawn_window.call_args.args[0]
        self.assertEqual(spawned.kind, "settings")
        self.assertIs(spawned.app, app)

    def test_execute_calculator_spawns_calculator_window(self):
        app = self._make_app()
        logger = mock.Mock()

        with mock.patch.object(self.action_runner, "CalculatorWindow", _DummyCalculatorWindow):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.CALCULATOR,
                logger,
                version="0.3.4",
            )

        app._next_window_offset.assert_called_once_with(24, 5)
        spawned = app._spawn_window.call_args.args[0]
        self.assertEqual(spawned.kind, "calc")
        self.assertEqual((spawned.x, spawned.y, spawned.w, spawned.h), (12, 7, 44, 14))

    def test_execute_log_viewer_spawns_log_window(self):
        app = self._make_app()
        logger = mock.Mock()

        with mock.patch.object(self.action_runner, "LogViewerWindow", _DummyLogViewerWindow):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.LOG_VIEWER,
                logger,
                version="0.9.0",
            )

        app._next_window_offset.assert_called_once_with(16, 4)
        spawned = app._spawn_window.call_args.args[0]
        self.assertEqual(spawned.kind, "log")
        self.assertEqual((spawned.x, spawned.y, spawned.w, spawned.h), (12, 7, 74, 22))

    def test_execute_process_manager_spawns_proc_window(self):
        app = self._make_app()
        logger = mock.Mock()

        with mock.patch.object(
            self.action_runner, "ProcessManagerWindow", _DummyProcessManagerWindow
        ):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.PROCESS_MANAGER,
                logger,
                version="0.9.0",
            )

        app._next_window_offset.assert_called_once_with(14, 3)
        spawned = app._spawn_window.call_args.args[0]
        self.assertEqual(spawned.kind, "proc")
        self.assertEqual((spawned.x, spawned.y, spawned.w, spawned.h), (12, 7, 76, 22))

    def test_execute_clock_calendar_spawns_clock_window(self):
        app = self._make_app()
        logger = mock.Mock()

        with mock.patch.object(
            self.action_runner, "ClockCalendarWindow", _DummyClockCalendarWindow
        ):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.CLOCK_CALENDAR,
                logger,
                version="0.9.0",
            )

        app._next_window_offset.assert_called_once_with(30, 6)
        spawned = app._spawn_window.call_args.args[0]
        self.assertEqual(spawned.kind, "clock")
        self.assertEqual((spawned.x, spawned.y, spawned.w, spawned.h), (12, 7, 34, 14))

    def test_execute_new_window_uses_incremental_title(self):
        app = self._make_app()
        logger = mock.Mock()

        with mock.patch.object(self.action_runner, "Window", _DummyWindow):
            self.action_runner.execute_app_action(
                app,
                self.actions_mod.AppAction.NEW_WINDOW,
                logger,
                version="0.3.4",
            )

        app._next_window_offset.assert_called_once_with(20, 3)
        spawned = app._spawn_window.call_args.args[0]
        self.assertEqual(spawned.title, "Window 99")
        self.assertEqual(spawned.content, ["", " New empty window", ""])

    def test_execute_unknown_action_logs_warning(self):
        app = self._make_app()
        logger = mock.Mock()

        self.action_runner.execute_app_action(
            app,
            "unknown",
            logger,
            version="0.3.4",
        )

        logger.warning.assert_called_once_with("Unknown action received: %s", "unknown")


if __name__ == "__main__":
    unittest.main()

import importlib
import locale
import re
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


def _fake_curses_module() -> types.ModuleType:
    fake = types.ModuleType("curses")
    fake.error = Exception
    fake.wrapper = lambda fn: fn(None)
    fake.endwin = lambda: None
    return fake


def _load_main_module():
    fake_curses = _fake_curses_module()
    fake_app_module = types.ModuleType("retrotui.core.app")

    class _DummyRetroTUI:
        def __init__(self, stdscr):
            self.stdscr = stdscr

        def run(self):
            return None

    fake_app_module.RetroTUI = _DummyRetroTUI

    with mock.patch.dict(
        sys.modules,
        {"curses": fake_curses, "retrotui.core.app": fake_app_module},
    ):
        sys.modules.pop("retrotui.__main__", None)
        return importlib.import_module("retrotui.__main__")


class EntryPointTests(unittest.TestCase):
    def test_module_import_tolerates_locale_error(self):
        fake_curses = _fake_curses_module()
        fake_app_module = types.ModuleType("retrotui.core.app")
        fake_app_module.RetroTUI = type("_Dummy", (), {"__init__": lambda self, stdscr: None, "run": lambda self: None})

        with (
            mock.patch.dict(sys.modules, {"curses": fake_curses, "retrotui.core.app": fake_app_module}),
            mock.patch("locale.setlocale", side_effect=locale.Error("bad locale")),
            mock.patch("logging.basicConfig") as basic_config,
            mock.patch.dict("os.environ", {}, clear=True),
        ):
            sys.modules.pop("retrotui.__main__", None)
            mod = importlib.import_module("retrotui.__main__")

        self.assertTrue(hasattr(mod, "run"))
        basic_config.assert_not_called()

    def test_module_import_enables_debug_logging_when_env_set(self):
        fake_curses = _fake_curses_module()
        fake_app_module = types.ModuleType("retrotui.core.app")
        fake_app_module.RetroTUI = type("_Dummy", (), {"__init__": lambda self, stdscr: None, "run": lambda self: None})

        with (
            mock.patch.dict(sys.modules, {"curses": fake_curses, "retrotui.core.app": fake_app_module}),
            mock.patch("locale.setlocale", return_value="ok"),
            mock.patch("logging.basicConfig") as basic_config,
            mock.patch.dict("os.environ", {"RETROTUI_DEBUG": "1"}, clear=True),
        ):
            sys.modules.pop("retrotui.__main__", None)
            mod = importlib.import_module("retrotui.__main__")

        self.assertTrue(hasattr(mod, "run"))
        basic_config.assert_called_once()

    def test_main_constructs_app_and_runs(self):
        mod = _load_main_module()
        app_instance = mock.Mock()
        stdscr = object()

        with mock.patch.object(mod, "RetroTUI", return_value=app_instance) as app_cls:
            mod.main(stdscr)

        app_cls.assert_called_once_with(stdscr)
        app_instance.run.assert_called_once_with()

    def test_run_returns_zero_when_wrapper_succeeds(self):
        mod = _load_main_module()

        with mock.patch.object(mod.curses, "wrapper", return_value=None) as wrapper:
            rc = mod.run()

        self.assertEqual(rc, 0)
        wrapper.assert_called_once_with(mod.main)

    def test_run_returns_130_on_keyboard_interrupt(self):
        mod = _load_main_module()

        with mock.patch.object(mod.curses, "wrapper", side_effect=KeyboardInterrupt):
            rc = mod.run()

        self.assertEqual(rc, 130)

    def test_run_returns_1_on_unhandled_exception(self):
        mod = _load_main_module()

        with (
            mock.patch.object(mod.curses, "wrapper", side_effect=RuntimeError("boom")),
            mock.patch.object(mod.curses, "endwin", return_value=None) as endwin,
            mock.patch("builtins.print") as print_mock,
            mock.patch("traceback.print_exc") as traceback_mock,
        ):
            rc = mod.run()

        self.assertEqual(rc, 1)
        endwin.assert_called_once_with()
        traceback_mock.assert_called_once_with()
        joined_prints = " ".join(str(call.args[0]) for call in print_mock.call_args_list if call.args)
        self.assertIn("boom", joined_prints)

    def test_run_ignores_endwin_error_on_unhandled_exception(self):
        mod = _load_main_module()

        with (
            mock.patch.object(mod.curses, "wrapper", side_effect=RuntimeError("boom")),
            mock.patch.object(mod.curses, "endwin", side_effect=mod.curses.error("endwin fail")) as endwin,
            mock.patch("builtins.print"),
            mock.patch("traceback.print_exc") as traceback_mock,
        ):
            rc = mod.run()

        self.assertEqual(rc, 1)
        endwin.assert_called_once_with()
        traceback_mock.assert_called_once_with()

    def test_main_cli_delegates_to_run(self):
        mod = _load_main_module()

        with mock.patch.object(mod, "run", return_value=7) as run_mock:
            rc = mod.main_cli()

        self.assertEqual(rc, 7)
        run_mock.assert_called_once_with()

    def test_module_main_guard_raises_system_exit_from_main_cli(self):
        fake_curses = _fake_curses_module()
        fake_app_module = types.ModuleType("retrotui.core.app")
        fake_app_module.RetroTUI = type("_Dummy", (), {"__init__": lambda self, stdscr: None, "run": lambda self: None})

        with (
            mock.patch.dict(sys.modules, {"curses": fake_curses, "retrotui.core.app": fake_app_module}),
            mock.patch("locale.setlocale", return_value="ok"),
            mock.patch.dict("os.environ", {}, clear=True),
        ):
            sys.modules.pop("retrotui.__main__", None)
            with self.assertRaises(SystemExit) as exc:
                runpy.run_module("retrotui.__main__", run_name="__main__")

        self.assertEqual(exc.exception.code, 0)


class StaticModuleContentTests(unittest.TestCase):
    def test_constants_module_exposes_expected_data(self):
        with mock.patch.dict(sys.modules, {"curses": _fake_curses_module()}):
            sys.modules.pop("retrotui.constants", None)
            constants = importlib.import_module("retrotui.constants")

        self.assertGreaterEqual(len(constants.ICONS), 6)
        self.assertGreaterEqual(len(constants.ICONS_ASCII), 6)
        self.assertIn(".mp4", constants.VIDEO_EXTENSIONS)
        self.assertIn("label", constants.ICONS[0])
        self.assertIn("action", constants.ICONS[0])

    def test_package_version_matches_runtime_constant(self):
        for mod_name in list(sys.modules):
            if mod_name == "retrotui" or mod_name.startswith("retrotui."):
                sys.modules.pop(mod_name, None)
        package = importlib.import_module("retrotui")
        package = importlib.reload(package)
        app_text = Path("retrotui/core/app.py").read_text(encoding="utf-8")
        match = re.search(r"^APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", app_text, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        app_version = match.group(1)

        self.assertEqual(package.__version__, app_version)
        self.assertEqual(package.__version__, "0.9.1")

    def test_content_builders_include_expected_sections(self):
        with mock.patch.dict(sys.modules, {"curses": _fake_curses_module()}):
            sys.modules.pop("retrotui.utils", None)
            sys.modules.pop("retrotui.core.content", None)
            content = importlib.import_module("retrotui.core.content")
        welcome = content.build_welcome_content("0.9.1")
        help_text = content.build_help_message()
        settings = content.build_settings_content()

        with mock.patch.object(content, "get_system_info", return_value=["OS: test", "CPU: test"]):
            about = content.build_about_message("0.9.1")

        self.assertTrue(any("v0.9.1" in line for line in welcome))
        self.assertIn("Ctrl+Q", help_text)
        self.assertTrue(any("Theme:" in line for line in settings))
        self.assertIn("RetroTUI v0.9.1", about)
        self.assertIn("OS: test", about)


if __name__ == "__main__":
    unittest.main()

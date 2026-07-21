import importlib
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from retrotui.core import terminal_environment as terminal_env


_CURSES_IMPORT_CONTRACT = {
    "KEY_LEFT": 260,
    "KEY_RIGHT": 261,
    "KEY_UP": 259,
    "KEY_DOWN": 258,
    "KEY_ENTER": 343,
    "KEY_HOME": 262,
    "KEY_END": 360,
    "KEY_PPAGE": 339,
    "KEY_NPAGE": 338,
    "KEY_BACKSPACE": 263,
    "KEY_DC": 330,
    "KEY_IC": 331,
    "A_BOLD": 1,
    "A_REVERSE": 2,
    "A_DIM": 4,
    "A_UNDERLINE": 8,
    "COLOR_WHITE": 7,
    "COLOR_BLUE": 4,
    "COLOR_BLACK": 0,
    "COLOR_CYAN": 6,
    "COLOR_YELLOW": 3,
    "COLORS": 256,
    "COLOR_PAIRS": 256,
    "error": Exception,
    "color_pair": lambda _pair: 0,
    "can_change_color": lambda: False,
    "start_color": lambda: None,
    "use_default_colors": lambda: None,
    "init_color": lambda *_args: None,
    "init_pair": lambda *_args: None,
}


def _fresh_cli_modules():
    """Import the entrypoint and its environment dependency as one generation."""
    sys.modules.pop("retrotui.__main__", None)
    sys.modules.pop("retrotui.core.terminal_environment", None)
    current_env = importlib.import_module("retrotui.core.terminal_environment")
    entry = importlib.import_module("retrotui.__main__")
    return entry, current_env


class TerminalEnvironmentTests(unittest.TestCase):
    def test_bundled_source_declares_conservative_profile(self):
        source = terminal_env.terminfo_source_text()

        self.assertIn("retrotui|RetroTUI embedded terminal", source)
        self.assertIn("colors#8", source)
        self.assertIn("smcup=\\E[?1049h", source)
        self.assertIn("smkx=\\E[?1h", source)
        self.assertNotIn("setrgb", source.lower())
        self.assertNotIn("colors#256", source)

    def test_candidate_dirs_deduplicate_and_honor_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            explicit = Path(tmp) / "explicit"
            extra = Path(tmp) / "extra"
            env = {
                "TERMINFO": os.fspath(explicit),
                "TERMINFO_DIRS": os.pathsep.join((os.fspath(extra), os.fspath(explicit))),
                "XDG_DATA_HOME": os.fspath(Path(tmp) / "xdg"),
            }

            dirs = terminal_env.candidate_terminfo_dirs(env, home=home)

        self.assertEqual(dirs[0], explicit)
        self.assertIn(extra, dirs)
        self.assertIn(home / ".terminfo", dirs)
        self.assertIn(Path(tmp) / "xdg" / "terminfo", dirs)
        self.assertEqual(dirs.count(explicit), 1)

    def test_terminfo_detection_accepts_character_and_hex_layouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            character_entry = root / "r" / terminal_env.TERMINFO_NAME
            character_entry.parent.mkdir(parents=True)
            character_entry.write_bytes(b"compiled")
            self.assertTrue(
                terminal_env.terminfo_is_installed(env={"TERMINFO": os.fspath(root)})
            )

            character_entry.unlink()
            hex_entry = root / f"{ord('r'):x}" / terminal_env.TERMINFO_NAME
            hex_entry.parent.mkdir(parents=True)
            hex_entry.write_bytes(b"compiled")
            self.assertTrue(
                terminal_env.terminfo_is_installed(env={"TERMINFO": os.fspath(root)})
            )

    def test_child_environment_uses_safe_fallback_when_profile_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            child = terminal_env.build_child_environment(env={}, home=tmp)

        self.assertEqual(child["TERM"], "ansi")
        self.assertEqual(child["TERM_PROGRAM"], "RetroTUI")
        self.assertEqual(child["COLORTERM"], "")
        self.assertEqual(child["RETROTUI_EMBEDDED_TERMINAL"], "1")

    def test_child_environment_uses_retrotui_when_profile_is_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / ".terminfo" / "r" / terminal_env.TERMINFO_NAME
            entry.parent.mkdir(parents=True)
            entry.write_bytes(b"compiled")

            child = terminal_env.build_child_environment(env={}, home=tmp)

        self.assertEqual(child["TERM"], terminal_env.TERMINFO_NAME)

    def test_child_term_and_per_window_overrides_are_respected(self):
        child = terminal_env.build_child_environment(
            {"TERM": "vt100", "CUSTOM": 7},
            env={"RETROTUI_CHILD_TERM": "screen"},
        )

        self.assertEqual(child["TERM"], "vt100")
        self.assertEqual(child["CUSTOM"], "7")

    def test_install_terminfo_invokes_tic_and_verifies_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "db"

            def fake_run(command, **kwargs):
                self.assertEqual(command[:3], ["/usr/bin/tic", "-x", "-o"])
                self.assertEqual(Path(command[3]), target)
                self.assertTrue(Path(command[4]).name.endswith(".src"))
                compiled = target / "r" / terminal_env.TERMINFO_NAME
                compiled.parent.mkdir(parents=True, exist_ok=True)
                compiled.write_bytes(b"compiled")
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch.object(terminal_env.subprocess, "run", side_effect=fake_run):
                installed = terminal_env.install_terminfo(target, tic_path="/usr/bin/tic")

        self.assertEqual(installed, target)

    def test_install_terminfo_reports_missing_compiler(self):
        with mock.patch.object(terminal_env.shutil, "which", return_value=None):
            with self.assertRaises(terminal_env.TerminfoInstallError):
                terminal_env.install_terminfo()

    def test_action_runner_injects_environment_only_when_supported(self):
        curses_module = importlib.import_module("curses")
        sys.modules.pop("retrotui.core.action_runner", None)
        try:
            with mock.patch.dict(
                vars(curses_module),
                _CURSES_IMPORT_CONTRACT,
                clear=False,
            ):
                action_runner = importlib.import_module("retrotui.core.action_runner")

            class TerminalWithEnvironment:
                def __init__(self, x, y, w, h, env=None):
                    self.env = env

            app = types.SimpleNamespace(
                _next_window_offset=mock.Mock(return_value=(1, 2)),
                _spawn_window=mock.Mock(),
                terminal_env_overrides={"SHELL_MARKER": "yes"},
            )

            with (
                mock.patch.object(action_runner, "TerminalWindow", TerminalWithEnvironment),
                mock.patch.object(
                    action_runner,
                    "build_child_environment",
                    return_value={"TERM": "retrotui", "SHELL_MARKER": "yes"},
                ) as builder,
            ):
                handled = action_runner._spawn_registered_app(
                    app,
                    action_runner.AppAction.TERMINAL,
                    action_runner._APP_REGISTRY,
                )

            self.assertTrue(handled)
            builder.assert_called_once_with(app.terminal_env_overrides)
            spawned = app._spawn_window.call_args.args[0]
            self.assertEqual(spawned.env["TERM"], "retrotui")
        finally:
            sys.modules.pop("retrotui.core.action_runner", None)

    def test_cli_installs_terminfo_without_starting_curses(self):
        entry, current_env = _fresh_cli_modules()
        target = Path("/tmp/retrotui-terminfo")
        with (
            mock.patch.object(current_env, "install_terminfo", return_value=target) as installer,
            mock.patch.object(entry, "run", return_value=99) as run_mock,
            mock.patch("builtins.print"),
        ):
            result = entry.main_cli(
                ["--install-terminfo", "--terminfo-dir", os.fspath(target)]
            )

        self.assertEqual(result, 0)
        installer.assert_called_once_with(os.fspath(target))
        run_mock.assert_not_called()

    def test_cli_returns_two_when_installation_fails(self):
        entry, current_env = _fresh_cli_modules()
        with (
            mock.patch.object(
                current_env,
                "install_terminfo",
                side_effect=current_env.TerminfoInstallError("missing tic"),
            ),
            mock.patch.object(entry, "run", return_value=99) as run_mock,
            mock.patch("builtins.print"),
        ):
            result = entry.main_cli(["--install-terminfo"])

        self.assertEqual(result, 2)
        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()

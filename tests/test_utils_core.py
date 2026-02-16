import importlib
import io
import os
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.COLOR_WHITE = 7
    fake.COLOR_BLUE = 4
    fake.COLOR_BLACK = 0
    fake.COLOR_CYAN = 6
    fake.COLOR_YELLOW = 3
    fake.COLORS = 256
    fake.A_DIM = 2
    fake.error = Exception
    fake.color_pair = lambda value: value
    fake.start_color = lambda: None
    fake.use_default_colors = lambda: None
    fake.can_change_color = lambda: True
    fake.init_color = lambda *_: None
    fake.init_pair = lambda *_: None
    fake.def_prog_mode = lambda: None
    fake.endwin = lambda: None
    fake.reset_prog_mode = lambda: None
    return fake


class UtilsCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in ("retrotui.constants", "retrotui.utils"):
            sys.modules.pop(mod_name, None)
        cls.utils = importlib.import_module("retrotui.utils")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in ("retrotui.constants", "retrotui.utils"):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_init_colors_configures_extended_palette(self):
        with (
            mock.patch.object(self.utils.curses, "can_change_color", return_value=True),
            mock.patch.object(self.utils.curses, "COLORS", 256),
            mock.patch.object(self.utils.curses, "init_color") as init_color,
            mock.patch.object(self.utils.curses, "init_pair") as init_pair,
        ):
            self.utils.init_colors()

        self.assertEqual(init_color.call_count, 4)
        self.assertGreaterEqual(init_pair.call_count, 15)

    def test_init_colors_uses_fallback_when_palette_not_customizable(self):
        with (
            mock.patch.object(self.utils.curses, "can_change_color", return_value=False),
            mock.patch.object(self.utils.curses, "init_color") as init_color,
            mock.patch.object(self.utils.curses, "init_pair") as init_pair,
        ):
            self.utils.init_colors()

        init_color.assert_not_called()
        self.assertGreaterEqual(init_pair.call_count, 15)

    def test_safe_addstr_clips_and_handles_errors(self):
        win = types.SimpleNamespace(
            getmaxyx=mock.Mock(return_value=(5, 10)),
            addnstr=mock.Mock(),
        )
        self.utils.safe_addstr(win, 1, 1, "hello", 0)
        win.addnstr.assert_called_once_with(1, 1, "hello", 8, 0)

        win.addnstr.reset_mock()
        self.utils.safe_addstr(win, -1, 1, "x", 0)
        self.utils.safe_addstr(win, 1, 10, "x", 0)
        self.assertFalse(win.addnstr.called)
        self.utils.safe_addstr(win, 1, 9, "x", 0)  # max_len <= 0 branch
        self.assertFalse(win.addnstr.called)

        win_error = types.SimpleNamespace(
            getmaxyx=mock.Mock(return_value=(5, 10)),
            addnstr=mock.Mock(side_effect=self.utils.curses.error("boom")),
        )
        # Should not raise.
        self.utils.safe_addstr(win_error, 1, 1, "hello", 0)

    def test_normalize_key_code_variants(self):
        self.assertEqual(self.utils.normalize_key_code(123), 123)
        self.assertEqual(self.utils.normalize_key_code("\n"), 10)
        self.assertEqual(self.utils.normalize_key_code("\r"), 10)
        self.assertEqual(self.utils.normalize_key_code("\x1b"), 27)
        self.assertEqual(self.utils.normalize_key_code("\t"), 9)
        self.assertEqual(self.utils.normalize_key_code("\x7f"), 127)
        self.assertEqual(self.utils.normalize_key_code("\b"), 8)
        self.assertEqual(self.utils.normalize_key_code("a"), ord("a"))
        self.assertIsNone(self.utils.normalize_key_code(""))
        self.assertIsNone(self.utils.normalize_key_code("ab"))
        self.assertIsNone(self.utils.normalize_key_code(None))

    def test_draw_box_calls_safe_addstr_for_edges(self):
        win = types.SimpleNamespace()
        with mock.patch.object(self.utils, "safe_addstr") as safe_addstr:
            self.utils.draw_box(win, y=2, x=3, h=4, w=8, attr=9, double=True)
        # top + 2 vertical rows x2 + bottom
        self.assertEqual(safe_addstr.call_count, 6)

        with mock.patch.object(self.utils, "safe_addstr") as safe_addstr:
            self.utils.draw_box(win, y=0, x=0, h=3, w=5, attr=1, double=False)
        self.assertEqual(safe_addstr.call_count, 4)

    def test_check_unicode_support_handles_encoding_failures(self):
        with mock.patch("retrotui.utils.locale.getpreferredencoding", return_value="utf-8"):
            self.assertTrue(self.utils.check_unicode_support())

        with mock.patch("retrotui.utils.locale.getpreferredencoding", return_value="ascii"):
            self.assertFalse(self.utils.check_unicode_support())

    def test_get_system_info_with_uname_and_meminfo(self):
        fake_uname = types.SimpleNamespace(
            sysname="Linux",
            release="6.1.0",
            nodename="retro",
            machine="x86_64",
        )
        meminfo = io.StringIO("MemTotal:       2097152 kB\nMemFree: 100 kB\n")
        with (
            mock.patch("retrotui.utils.os.uname", return_value=fake_uname, create=True),
            mock.patch("builtins.open", return_value=meminfo),
            mock.patch.dict("retrotui.utils.os.environ", {"TERM": "xterm", "SHELL": "/bin/bash"}, clear=False),
        ):
            info = self.utils.get_system_info()

        joined = "\n".join(info)
        self.assertIn("OS: Linux 6.1.0", joined)
        self.assertIn("Host: retro", joined)
        self.assertIn("Arch: x86_64", joined)
        self.assertIn("RAM: 2048 MB", joined)
        self.assertIn("Terminal: xterm", joined)
        self.assertIn("Shell: bash", joined)
        self.assertIn("Python:", joined)

    def test_get_system_info_fallback_when_uname_or_meminfo_fail(self):
        with (
            mock.patch("retrotui.utils.os.uname", side_effect=OSError("no uname"), create=True),
            mock.patch("builtins.open", side_effect=OSError("no meminfo")),
            mock.patch.dict("retrotui.utils.os.environ", {}, clear=True),
        ):
            info = self.utils.get_system_info()

        joined = "\n".join(info)
        self.assertIn("OS: Linux", joined)
        self.assertIn("Terminal: unknown", joined)
        self.assertIn("Shell: unknown", joined)

    def test_is_video_file_detects_extensions_case_insensitive(self):
        self.assertTrue(self.utils.is_video_file("demo.MP4"))
        self.assertTrue(self.utils.is_video_file("movie.mkv"))
        self.assertFalse(self.utils.is_video_file("notes.txt"))

    def test_play_ascii_video_prefers_mplayer_when_mpv_missing(self):
        stdscr = types.SimpleNamespace(refresh=mock.Mock())

        def which(name):
            return "/usr/bin/mplayer" if name == "mplayer" else None

        # Non-zero return code but elapsed > 2s should count as successful playback.
        result = types.SimpleNamespace(returncode=1)
        with (
            mock.patch("retrotui.utils.shutil.which", side_effect=which),
            mock.patch("retrotui.utils.subprocess.run", return_value=result),
            mock.patch("retrotui.utils.time.time", side_effect=[0.0, 3.2]),
            mock.patch("retrotui.utils.curses.def_prog_mode"),
            mock.patch("retrotui.utils.curses.endwin"),
            mock.patch("retrotui.utils.curses.reset_prog_mode"),
        ):
            success, error = self.utils.play_ascii_video(stdscr, "demo.mp4")

        self.assertTrue(success)
        self.assertIsNone(error)
        stdscr.refresh.assert_called_once()

    def test_play_ascii_video_returns_error_on_subprocess_oserror(self):
        with (
            mock.patch("retrotui.utils.shutil.which", side_effect=lambda name: "/usr/bin/mpv" if name == "mpv" else None),
            mock.patch("retrotui.utils.subprocess.run", side_effect=OSError("boom")),
            mock.patch("retrotui.utils.curses.def_prog_mode"),
            mock.patch("retrotui.utils.curses.endwin"),
            mock.patch("retrotui.utils.curses.reset_prog_mode"),
        ):
            success, error = self.utils.play_ascii_video(None, "demo.mp4")

        self.assertFalse(success)
        self.assertIn("boom", error)

    def test_play_ascii_video_returns_backend_error_when_playback_fails(self):
        failed = types.SimpleNamespace(returncode=1)
        with (
            mock.patch("retrotui.utils.shutil.which", side_effect=lambda name: "/usr/bin/mpv" if name == "mpv" else None),
            mock.patch("retrotui.utils.subprocess.run", return_value=failed),
            mock.patch("retrotui.utils.time.time", side_effect=[0.0, 0.1, 0.2, 0.3]),
            mock.patch("retrotui.utils.curses.def_prog_mode"),
            mock.patch("retrotui.utils.curses.endwin"),
            mock.patch("retrotui.utils.curses.reset_prog_mode"),
        ):
            success, error = self.utils.play_ascii_video(None, "demo.mp4")

        self.assertFalse(success)
        self.assertIn("Backend probado:", error)
        self.assertIn("Código de salida: 1", error)

    def test_play_ascii_video_handles_reset_mode_errors(self):
        ok_result = types.SimpleNamespace(returncode=0)
        with (
            mock.patch("retrotui.utils.shutil.which", side_effect=lambda name: "/usr/bin/mpv" if name == "mpv" else None),
            mock.patch("retrotui.utils.subprocess.run", return_value=ok_result),
            mock.patch("retrotui.utils.time.time", side_effect=[0.0, 0.1]),
            mock.patch("retrotui.utils.curses.def_prog_mode"),
            mock.patch("retrotui.utils.curses.endwin"),
            mock.patch("retrotui.utils.curses.reset_prog_mode", side_effect=self.utils.curses.error("reset fail")),
        ):
            success, error = self.utils.play_ascii_video(None, "demo.mp4")

        self.assertTrue(success)
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()

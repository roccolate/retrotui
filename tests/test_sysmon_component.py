import importlib
import sys
import unittest
from unittest import mock

from _support import make_fake_curses


class SystemMonitorComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = make_fake_curses()
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.window",
            "retrotui.apps.sysmon",
        ):
            sys.modules.pop(mod_name, None)
        cls.mod = importlib.import_module("retrotui.apps.sysmon")

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.window",
            "retrotui.apps.sysmon",
        ):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_draw_uses_imported_curses_module(self):
        with mock.patch.object(self.mod, "_PROC_AVAILABLE", False):
            win = self.mod.SystemMonitorWindow(0, 0, 50, 18)

        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.mod, "safe_addstr") as safe_addstr,
        ):
            win.draw(None)

        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list]
        self.assertTrue(any("CPU Usage" in line for line in rendered))
        self.assertTrue(any("System stats unavailable" in line for line in rendered))

    def test_proc_reads_use_explicit_encoding(self):
        win = self.mod.SystemMonitorWindow.__new__(self.mod.SystemMonitorWindow)
        file_mock = mock.mock_open(read_data="cpu  1 2 3 4 5\n")

        with (
            mock.patch.object(self.mod, "_PROC_AVAILABLE", True),
            mock.patch("builtins.open", file_mock),
        ):
            self.assertEqual(win._get_cpu_times(), (4.0, 15.0))

        file_mock.assert_called_once_with(
            "/proc/stat",
            "r",
            encoding="utf-8",
            errors="replace",
        )


if __name__ == "__main__":
    unittest.main()

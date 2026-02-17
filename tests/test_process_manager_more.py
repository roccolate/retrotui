"""More Process Manager tests covering parsing fallbacks and sorting."""

from __future__ import annotations

import importlib
import sys
import unittest
from unittest import mock

from _support import make_fake_curses


class ProcessManagerMoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = make_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.theme",
            "retrotui.utils",
            "retrotui.ui.dialog",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.apps.process_manager",
        ):
            sys.modules.pop(mod_name, None)

        cls.pm_mod = importlib.import_module("retrotui.apps.process_manager")
        cls.ProcessManagerWindow = cls.pm_mod.ProcessManagerWindow
        cls.ProcessRow = cls.pm_mod.ProcessRow

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.process_manager",
            "retrotui.ui.window",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
            "retrotui.utils",
            "retrotui.theme",
            "retrotui.constants",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def setUp(self):
        self.win = self.ProcessManagerWindow(0, 0, 80, 20)

    def test_read_mem_defaults_on_error(self):
        with mock.patch.object(self.ProcessManagerWindow, "_read_first_line", side_effect=OSError()):
            self.assertEqual(self.ProcessManagerWindow._read_mem_total_kb(), 1)
            self.assertEqual(self.ProcessManagerWindow._read_mem_available_kb(), 0)

    def test_read_total_jiffies_and_loadavg(self):
        with mock.patch.object(self.ProcessManagerWindow, "_read_first_line", return_value="notcpu 1 2 3"):
            self.assertEqual(self.ProcessManagerWindow._read_total_jiffies(), 0)

        with mock.patch.object(self.ProcessManagerWindow, "_read_first_line", return_value="cpu 1 2 x 4"):
            self.assertEqual(self.ProcessManagerWindow._read_total_jiffies(), 7)

        with mock.patch.object(self.ProcessManagerWindow, "_read_first_line", return_value=""):
            self.assertEqual(self.ProcessManagerWindow._read_load_average(), "- - -")

    def test_read_command_prefers_cmdline_then_comm_then_fallback(self):
        def fake_read_first_line(path):
            if path.endswith("/comm"):
                return "commname"
            raise OSError()

        with mock.patch.object(self.ProcessManagerWindow, "_read_first_line", side_effect=fake_read_first_line):
            self.assertEqual(self.ProcessManagerWindow._read_command(12345), "commname")

        def fake_open_cmdline(path, mode="r", *args, **kwargs):
            class FakeFile:
                def read(self):
                    return b"/bin/echo\x00arg\x00"

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            if str(path).endswith("/cmdline"):
                return FakeFile()
            raise OSError()

        with mock.patch("builtins.open", fake_open_cmdline):
            self.assertIn("/bin/echo", self.ProcessManagerWindow._read_command(1))

    def test_read_process_row_various_edge_cases(self):
        with mock.patch.object(self.win, "_read_first_line", return_value="no_paren_line"):
            self.assertIsNone(self.win._read_process_row(1, 10, 1024))

        stat_line = "(name) shorttail"
        with mock.patch.object(self.win, "_read_first_line", side_effect=[stat_line, OSError()]):
            self.assertIsNone(self.win._read_process_row(1, 10, 1024))

        stat_line = "(p) R 0 0 0 0 0 0 0 0 0 0 5 6 7 8 9 10 11 12"

        def fake_read_first_line(path):
            if str(path).endswith("/stat"):
                return stat_line
            raise OSError()

        with mock.patch.object(self.win, "_read_first_line", side_effect=fake_read_first_line):
            row = self.win._read_process_row(2, total_delta=0, mem_total_kb=1024)
            self.assertIsNotNone(row)
            self.assertEqual(row.cpu_percent, 0.0)

        self.win._prev_proc_ticks = {3: 5}
        stat_line2 = "(n) S 0 0 0 0 0 0 0 0 0 0 10 15 0 0 0 0 0 0"

        def fake_read_first_line2(path):
            path = str(path)
            if path.endswith("/stat"):
                return stat_line2
            if path.endswith("/statm"):
                return "0 4 0 0 0"
            if path.endswith("/cmdline"):
                raise OSError()
            if path.endswith("/comm"):
                return "cp"
            return ""

        with mock.patch.object(self.win, "_read_first_line", side_effect=fake_read_first_line2):
            row2 = self.win._read_process_row(3, total_delta=10, mem_total_kb=1024)
            self.assertIsNotNone(row2)
            self.assertGreaterEqual(row2.cpu_percent, 0.0)

    def test_sorting_and_selection_visibility(self):
        r1 = self.ProcessRow(pid=1, cpu_percent=1.0, mem_percent=5.0, command="a", total_ticks=0)
        r2 = self.ProcessRow(pid=2, cpu_percent=2.0, mem_percent=1.0, command="b", total_ticks=0)
        self.win.rows = [r1, r2]
        self.win.sort_key = "mem"
        self.win.sort_reverse = False
        self.win._sort_rows()
        self.assertEqual(self.win.rows[0].mem_percent, 1.0)

        self.win.rows = [
            self.ProcessRow(pid=i, cpu_percent=0, mem_percent=0, command=str(i), total_ticks=0)
            for i in range(20)
        ]
        self.win.selected_index = 19
        self.win.scroll_offset = 0
        self.win._ensure_selection_visible()
        self.assertGreaterEqual(self.win.scroll_offset, 0)


if __name__ == "__main__":
    unittest.main()


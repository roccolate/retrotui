"""Extra Process Manager tests for formatting and action paths."""

from __future__ import annotations

import importlib
import os
import sys
import unittest
from unittest import mock

from _support import make_fake_curses


class ProcessManagerExtraTests(unittest.TestCase):
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
            "retrotui.core.actions",
            "retrotui.apps.process_manager",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.pm_mod = importlib.import_module("retrotui.apps.process_manager")
        cls.ProcessManagerWindow = cls.pm_mod.ProcessManagerWindow
        cls.ProcessRow = cls.pm_mod.ProcessRow
        cls.ActionType = cls.actions_mod.ActionType

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.process_manager",
            "retrotui.core.actions",
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

    def test_format_uptime_variants(self):
        self.assertEqual(self.ProcessManagerWindow._format_uptime(3600), "01h 00m")
        seconds = 1 * 86400 + 2 * 3600 + 3 * 60
        self.assertIn("d", self.ProcessManagerWindow._format_uptime(seconds))

    def test_refresh_processes_populates_rows_and_summaries(self):
        self.win._read_mem_total_kb = lambda: 2048
        self.win._read_mem_available_kb = lambda: 1024
        self.win._read_uptime_seconds = lambda: 3600 * 2 + 30 * 60
        self.win._read_load_average = lambda: "0.10 0.20 0.30"

        with mock.patch.object(os, "listdir", return_value=["123", "456"]):
            def fake_read_process_row(self_obj, pid, total_delta, mem_total_kb):
                pid = int(pid)
                return self.ProcessRow(
                    pid=pid,
                    cpu_percent=0.0,
                    mem_percent=1.0 * pid,
                    command=f"cmd{pid}",
                    total_ticks=10,
                )

            with mock.patch.object(self.ProcessManagerWindow, "_read_process_row", new=fake_read_process_row):
                self.win.refresh_processes(force=True)

        self.assertGreaterEqual(len(self.win.rows), 2)
        self.assertEqual(self.win.summary_mem, "1MB/2MB")
        self.assertEqual(self.win.summary_load, "0.10 0.20 0.30")

    def test_request_kill_and_kill_process_paths(self):
        self.win.rows = []
        res = self.win.request_kill_selected()
        self.assertEqual(res.type, self.ActionType.ERROR)

        self.win.rows = [self.ProcessRow(pid=999, cpu_percent=0.0, mem_percent=0.0, command="c", total_ticks=0)]
        self.win.selected_index = 0
        req = self.win.request_kill_selected()
        self.assertEqual(req.type, self.ActionType.REQUEST_KILL_CONFIRM)
        self.assertEqual(req.payload["pid"], 999)

        err = self.win.kill_process({})
        self.assertEqual(err.type, self.ActionType.ERROR)

        called = {"refreshed": False}

        def fake_refresh(force=False):
            called["refreshed"] = True

        self.win.refresh_processes = fake_refresh

        with mock.patch.object(os, "kill", side_effect=ProcessLookupError()):
            out = self.win.kill_process({"pid": 999, "signal": 15})
        self.assertIsNone(out)
        self.assertTrue(called["refreshed"])

        with mock.patch.object(os, "kill", side_effect=PermissionError()):
            out = self.win.kill_process({"pid": 999, "signal": 15})
        self.assertEqual(out.type, self.ActionType.ERROR)

        with mock.patch.object(os, "kill", side_effect=OSError("boom")):
            out = self.win.kill_process({"pid": 999, "signal": 15})
        self.assertEqual(out.type, self.ActionType.ERROR)

    def test_execute_action_sort_and_close(self):
        calls = {"count": 0}

        def track_refresh(force=False):
            calls["count"] += 1

        self.win.refresh_processes = track_refresh

        self.win.execute_action("pm_sort_cpu")
        self.assertEqual(self.win.sort_key, "cpu")

        self.win.execute_action("pm_sort_pid")
        self.assertEqual(self.win.sort_key, "pid")

        self.win.rows = [self.ProcessRow(pid=111, cpu_percent=0.0, mem_percent=0.0, command="c", total_ticks=0)]
        self.win.selected_index = 0
        res = self.win.execute_action("pm_kill")
        self.assertEqual(res.type, self.ActionType.REQUEST_KILL_CONFIRM)

        res_close = self.win.execute_action("pm_close")
        self.assertEqual(res_close.type, self.ActionType.EXECUTE)


if __name__ == "__main__":
    unittest.main()


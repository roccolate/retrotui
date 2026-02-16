import importlib
import signal
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_PPAGE = 339
    fake.KEY_NPAGE = 338
    fake.KEY_HOME = 262
    fake.KEY_END = 360
    fake.KEY_DC = 330
    fake.KEY_F5 = 269
    fake.A_BOLD = 1
    fake.error = Exception
    fake.color_pair = lambda value: value * 10
    return fake


class ProcessManagerComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.window",
            "retrotui.ui.menu",
            "retrotui.core.actions",
            "retrotui.apps.process_manager",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.pm_mod = importlib.import_module("retrotui.apps.process_manager")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.window",
            "retrotui.ui.menu",
            "retrotui.core.actions",
            "retrotui.apps.process_manager",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_window(self):
        return self.pm_mod.ProcessManagerWindow(0, 0, 76, 22)

    def test_request_kill_selected_returns_confirm_action(self):
        win = self._make_window()
        win.rows = [
            self.pm_mod.ProcessRow(
                pid=123,
                cpu_percent=7.0,
                mem_percent=2.0,
                command="python app.py",
                total_ticks=100,
            )
        ]
        win.selected_index = 0

        result = win.request_kill_selected()

        self.assertEqual(result.type, self.actions_mod.ActionType.REQUEST_KILL_CONFIRM)
        self.assertEqual(result.payload["pid"], 123)
        self.assertEqual(result.payload["signal"], signal.SIGTERM)

    def test_kill_process_calls_os_kill_and_refreshes(self):
        win = self._make_window()
        payload = {"pid": 9999, "signal": signal.SIGTERM}

        with (
            mock.patch.object(self.pm_mod.os, "kill") as os_kill,
            mock.patch.object(win, "refresh_processes") as refresh,
        ):
            result = win.kill_process(payload)

        self.assertIsNone(result)
        os_kill.assert_called_once_with(9999, signal.SIGTERM)
        refresh.assert_called_once_with(force=True)

    def test_kill_process_permission_error_returns_error_action(self):
        win = self._make_window()
        payload = {"pid": 1, "signal": signal.SIGTERM}

        with mock.patch.object(self.pm_mod.os, "kill", side_effect=PermissionError):
            result = win.kill_process(payload)

        self.assertEqual(result.type, self.actions_mod.ActionType.ERROR)
        self.assertIn("Permission denied", result.payload)

    def test_handle_key_sort_and_close_paths(self):
        win = self._make_window()

        with mock.patch.object(win, "_set_sort") as set_sort:
            win.handle_key(ord("c"))
            win.handle_key(ord("m"))
            win.handle_key(ord("p"))

        self.assertEqual(set_sort.call_args_list[0].args, ("cpu",))
        self.assertEqual(set_sort.call_args_list[1].args, ("mem",))
        self.assertEqual(set_sort.call_args_list[2].args, ("pid",))

        close_result = win.handle_key(ord("q"))
        self.assertEqual(close_result.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(close_result.payload, self.actions_mod.AppAction.CLOSE_WINDOW)

    def test_draw_renders_table_and_status(self):
        win = self._make_window()
        win.rows = [
            self.pm_mod.ProcessRow(111, 12.3, 4.5, "proc-a", 10),
            self.pm_mod.ProcessRow(222, 1.0, 0.2, "proc-b", 20),
        ]
        win.selected_index = 0
        win.summary_uptime = "01h 10m"
        win.summary_load = "0.10 0.20 0.30"
        win.summary_mem = "200MB/1000MB"

        with (
            mock.patch.object(win, "refresh_processes", return_value=None),
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.pm_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(self.pm_mod, "theme_attr", return_value=0),
        ):
            win.draw(None)

        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("PID" in text and "CPU%" in text for text in rendered))
        self.assertTrue(any("proc-a" in text for text in rendered))
        self.assertTrue(any("Uptime" in text for text in rendered))


if __name__ == "__main__":
    unittest.main()


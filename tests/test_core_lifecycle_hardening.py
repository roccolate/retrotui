"""Focused regressions for lifecycle, process identity, and cleanup hardening."""
from __future__ import annotations

import ast
import os
import signal
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

from retrotui import __main__ as main_mod
from retrotui.apps.process_manager import ProcessManagerWindow, ProcessRow
from retrotui.apps.wifi_manager import WifiManagerWindow
from retrotui.core import event_loop
from retrotui.core.actions import ActionType, ProcessSignalPayload


class ProcessIdentityTests(unittest.TestCase):
    def _window(self):
        win = ProcessManagerWindow.__new__(ProcessManagerWindow)
        win.rows = []
        win.selected_index = 0
        win.refresh_processes = mock.Mock()
        return win

    def test_payload_preserves_process_start_identity(self):
        payload = ProcessSignalPayload.from_value({
            "pid": 7,
            "signal": signal.SIGTERM,
            "start_time_ticks": 1234,
        })
        self.assertEqual(payload.start_time_ticks, 1234)
        self.assertEqual(payload["start_time_ticks"], 1234)

    def test_confirmation_captures_start_time(self):
        win = self._window()
        win.rows = [ProcessRow(7, 0.0, 0.0, "demo", 10, 1234)]

        result = win.request_kill_selected()

        self.assertEqual(result.type, ActionType.REQUEST_KILL_CONFIRM)
        self.assertEqual(result.payload.start_time_ticks, 1234)

    def test_reused_pid_is_not_signalled(self):
        win = self._window()
        win._read_process_start_time_ticks = mock.Mock(return_value=222)
        payload = ProcessSignalPayload(
            pid=77,
            signal=signal.SIGTERM,
            start_time_ticks=111,
        )

        with (
            mock.patch.object(os, "pidfd_open", None, create=True),
            mock.patch.object(signal, "pidfd_send_signal", None, create=True),
            mock.patch.object(os, "kill") as kill,
        ):
            result = win.kill_process(payload)

        self.assertEqual(result.type, ActionType.REFRESH)
        self.assertIn("another process", result.payload)
        kill.assert_not_called()

    def test_pidfd_keeps_signal_bound_to_verified_process(self):
        win = self._window()
        win._read_process_start_time_ticks = mock.Mock(return_value=111)
        payload = ProcessSignalPayload(
            pid=77,
            signal=signal.SIGTERM,
            start_time_ticks=111,
        )

        with (
            mock.patch.object(os, "pidfd_open", return_value=55, create=True) as open_pidfd,
            mock.patch.object(signal, "pidfd_send_signal", create=True) as send_pidfd,
            mock.patch.object(os, "close") as close_fd,
            mock.patch.object(os, "kill") as kill,
        ):
            result = win.kill_process(payload)

        self.assertIsNone(result)
        open_pidfd.assert_called_once_with(77, 0)
        send_pidfd.assert_called_once_with(55, signal.SIGTERM)
        close_fd.assert_called_once_with(55)
        kill.assert_not_called()


class RuntimeLifecycleTests(unittest.TestCase):
    def test_idle_clock_without_menu_is_a_clean_noop(self):
        app = types.SimpleNamespace(
            _dirty=False,
            _frame_size=(25, 80),
            menu=None,
            stdscr=types.SimpleNamespace(noutrefresh=mock.Mock()),
        )
        self.assertFalse(event_loop._refresh_idle_clock(app))
        app.stdscr.noutrefresh.assert_not_called()

    def test_event_loop_returns_failed_cleanup_status(self):
        app = types.SimpleNamespace(
            running=False,
            cleanup=mock.Mock(return_value=False),
            _install_runtime_signal_handlers=mock.Mock(),
        )
        with (
            mock.patch.object(event_loop, "_ensure_runtime_metrics", return_value={}),
            mock.patch.object(event_loop, "_emit_runtime_metrics"),
        ):
            result = event_loop.run_app_loop(app)
        self.assertFalse(result)
        app.cleanup.assert_called_once_with()

    def test_entrypoint_reports_incomplete_cleanup(self):
        with (
            mock.patch.object(main_mod.curses, "wrapper", return_value=False, create=True),
            mock.patch("builtins.print") as output,
        ):
            code = main_mod.run()
        self.assertEqual(code, 1)
        self.assertTrue(any(call.kwargs.get("file") is sys.stderr for call in output.call_args_list))


class WifiLifecycleTests(unittest.TestCase):
    def _window(self):
        win = WifiManagerWindow.__new__(WifiManagerWindow)
        win.nmcli = "/usr/bin/nmcli"
        win._connect_lock = threading.Lock()
        win._connect_in_progress = True
        win._connect_result = None
        win._connect_result_ssid = None
        win._connecting_ssid = "demo"
        win.refresh = mock.Mock()
        return win

    def test_unexpected_worker_failure_finalizes_state(self):
        win = self._window()
        with mock.patch(
            "retrotui.apps.wifi_manager.subprocess.run",
            side_effect=RuntimeError("boom"),
        ):
            win._connect_worker(threading.Event(), "demo", "secret")

        self.assertFalse(win._connect_in_progress)
        self.assertIsNone(win._connecting_ssid)
        self.assertEqual(win._connect_result[0], False)
        self.assertIn("boom", win._connect_result[1])

    def test_password_is_passed_on_stdin_not_argv(self):
        win = self._window()
        completed = types.SimpleNamespace(returncode=0, stderr="", stdout="")
        with mock.patch(
            "retrotui.apps.wifi_manager.subprocess.run",
            return_value=completed,
        ) as run:
            win._connect_worker(threading.Event(), "demo", "secret")

        command = run.call_args.args[0]
        self.assertNotIn("secret", command)
        self.assertEqual(run.call_args.kwargs["input"], "secret\n")


class CleanupStructureTests(unittest.TestCase):
    def test_retronet_has_one_window_class_definition(self):
        import retrotui.apps.retronet as retronet

        tree = ast.parse(Path(retronet.__file__).read_text(encoding="utf-8"))
        classes = [
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "RetroNetWindow"
        ]
        self.assertEqual(len(classes), 1)


if __name__ == "__main__":
    unittest.main()

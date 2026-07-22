from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one anchor in {relative_path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def write_new(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    if path.exists():
        raise RuntimeError(f"refusing to overwrite existing file: {relative_path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


replace_once(
    "retrotui/core/actions.py",
    '''    pid: int = 0
    command: str = ""
    signal: int = 15
    _payload_fields: ClassVar[tuple[str, ...]] = ("pid", "command", "signal")
''',
    '''    pid: int = 0
    command: str = ""
    signal: int = 15
    start_time_ticks: int = 0
    _payload_fields: ClassVar[tuple[str, ...]] = (
        "pid",
        "command",
        "signal",
        "start_time_ticks",
    )
''',
)
replace_once(
    "retrotui/core/actions.py",
    '''        try:
            signal_number = int(value.get("signal", 15) or 15)
        except (TypeError, ValueError, OverflowError):
            signal_number = 15
        command = value.get("command", "")
        return cls(
            pid=pid,
            command=str(command or ""),
            signal=signal_number,
        )
''',
    '''        try:
            signal_number = int(value.get("signal", 15) or 15)
        except (TypeError, ValueError, OverflowError):
            signal_number = 15
        try:
            start_time_ticks = int(value.get("start_time_ticks", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            start_time_ticks = 0
        command = value.get("command", "")
        return cls(
            pid=pid,
            command=str(command or ""),
            signal=signal_number,
            start_time_ticks=max(0, start_time_ticks),
        )
''',
)

replace_once(
    "retrotui/apps/process_manager.py",
    '''import curses
import os
import signal
import time
''',
    '''import curses
import errno
import os
import signal
import time
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''    command: str
    total_ticks: int
''',
    '''    command: str
    total_ticks: int
    start_time_ticks: int = 0
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''    def _read_process_row(self, pid, total_delta, mem_total_kb):
        stat_path = f"/proc/{pid}/stat"
        statm_path = f"/proc/{pid}/statm"

        try:
            stat_line = self._read_first_line(stat_path)
        except OSError:
            return None

        close = stat_line.rfind(")")
        if close < 0:
            return None
        tail = stat_line[close + 2 :].split()
        if len(tail) < 13:
            return None
        try:
            utime = int(tail[11])
            stime = int(tail[12])
            total_ticks = utime + stime
        except (ValueError, IndexError):
            return None
''',
    '''    @staticmethod
    def _read_process_start_time_ticks(pid):
        """Return Linux process start ticks, or ``None`` when it is gone."""
        try:
            stat_line = ProcessManagerWindow._read_first_line(f"/proc/{pid}/stat")
        except OSError:
            return None
        close = stat_line.rfind(")")
        if close < 0:
            return None
        tail = stat_line[close + 2 :].split()
        if len(tail) < 20:
            return None
        try:
            return int(tail[19])
        except (ValueError, IndexError):
            return None

    def _read_process_row(self, pid, total_delta, mem_total_kb):
        stat_path = f"/proc/{pid}/stat"
        statm_path = f"/proc/{pid}/statm"

        try:
            stat_line = self._read_first_line(stat_path)
        except OSError:
            return None

        close = stat_line.rfind(")")
        if close < 0:
            return None
        tail = stat_line[close + 2 :].split()
        if len(tail) < 20:
            return None
        try:
            utime = int(tail[11])
            stime = int(tail[12])
            total_ticks = utime + stime
            start_time_ticks = int(tail[19])
        except (ValueError, IndexError):
            return None
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''            command=command,
            total_ticks=total_ticks,
        )
''',
    '''            command=command,
            total_ticks=total_ticks,
            start_time_ticks=start_time_ticks,
        )
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''    def request_kill_selected(self):
        """Return a kill-confirmation request for currently selected process."""
        row = self._selected_row()
        if row is None:
            return ActionResult(ActionType.ERROR, "No process selected.")
        payload = ProcessSignalPayload(
            pid=row.pid,
            command=row.command,
            signal=signal.SIGTERM,
        )
        return ActionResult(ActionType.REQUEST_KILL_CONFIRM, payload)

    def kill_process(self, payload):
        """Send requested signal to one process."""
        data = ProcessSignalPayload.from_value(payload)
        pid = data.pid
        sig = data.signal
        if pid <= 0:
            return ActionResult(ActionType.ERROR, "Invalid PID.")
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            # Process already exited. Refresh the listing and tell the
            # user so the action doesn't look like a silent no-op.
            self.refresh_processes(force=True)
            return ActionResult(ActionType.REFRESH, f"Process {pid} was already gone.")
        except PermissionError:
            return ActionResult(ActionType.ERROR, f"Permission denied for PID {pid}.")
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))
        self.refresh_processes(force=True)
        return None
''',
    '''    def request_kill_selected(self):
        """Return a kill-confirmation request for currently selected process."""
        row = self._selected_row()
        if row is None:
            return ActionResult(ActionType.ERROR, "No process selected.")
        payload = ProcessSignalPayload(
            pid=row.pid,
            command=row.command,
            signal=signal.SIGTERM,
            start_time_ticks=row.start_time_ticks,
        )
        return ActionResult(ActionType.REQUEST_KILL_CONFIRM, payload)

    def kill_process(self, payload):
        """Signal the process identity selected by the user, never a reused PID."""
        data = ProcessSignalPayload.from_value(payload)
        pid = data.pid
        sig = data.signal
        expected_start = data.start_time_ticks
        if pid <= 0:
            return ActionResult(ActionType.ERROR, "Invalid PID.")

        pidfd = None
        pidfd_open = getattr(os, "pidfd_open", None)
        pidfd_send_signal = getattr(signal, "pidfd_send_signal", None)
        try:
            if expected_start > 0:
                if callable(pidfd_open) and callable(pidfd_send_signal):
                    try:
                        pidfd = pidfd_open(pid, 0)
                    except ProcessLookupError:
                        self.refresh_processes(force=True)
                        return ActionResult(
                            ActionType.REFRESH,
                            f"Process {pid} was already gone.",
                        )
                    except OSError as exc:
                        unsupported = {
                            errno.ENOSYS,
                            errno.EINVAL,
                            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
                        }
                        if exc.errno not in unsupported:
                            return ActionResult(ActionType.ERROR, str(exc))

                current_start = self._read_process_start_time_ticks(pid)
                if current_start is None:
                    self.refresh_processes(force=True)
                    return ActionResult(
                        ActionType.REFRESH,
                        f"Process {pid} was already gone.",
                    )
                if current_start != expected_start:
                    self.refresh_processes(force=True)
                    return ActionResult(
                        ActionType.REFRESH,
                        f"PID {pid} now belongs to another process; no signal was sent.",
                    )

            if pidfd is not None:
                pidfd_send_signal(pidfd, sig)
            else:
                os.kill(pid, sig)
        except ProcessLookupError:
            self.refresh_processes(force=True)
            return ActionResult(ActionType.REFRESH, f"Process {pid} was already gone.")
        except PermissionError:
            return ActionResult(ActionType.ERROR, f"Permission denied for PID {pid}.")
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))
        finally:
            if pidfd is not None:
                try:
                    os.close(pidfd)
                except OSError:
                    pass
        self.refresh_processes(force=True)
        return None
''',
)

replace_once(
    "retrotui/core/event_loop.py",
    '''    menu = getattr(app, "menu", None)
    refresh_clock = getattr(menu, "refresh_clock", None)
    if callable(refresh_clock):
''',
    '''    menu = getattr(app, "menu", None)
    refresh_clock = getattr(menu, "refresh_clock", None)
    updated = False
    if callable(refresh_clock):
''',
)
replace_once(
    "retrotui/core/event_loop.py",
    '''    app._event_loop_first_error = None
    app._event_loop_first_error_phase = None

    try:
''',
    '''    app._event_loop_first_error = None
    app._event_loop_first_error_phase = None
    cleanup_ok = True

    try:
''',
)
replace_once(
    "retrotui/core/event_loop.py",
    '''    finally:
        _emit_runtime_metrics(metrics, final=True)
        try:
            app.cleanup()
        except Exception:
            if first_error is None:
                raise
            LOGGER.exception(
                "cleanup failed after event-loop error; preserving original cause"
            )
''',
    '''    finally:
        _emit_runtime_metrics(metrics, final=True)
        try:
            cleanup_ok = app.cleanup() is not False
        except Exception:
            cleanup_ok = False
            if first_error is None:
                raise
            LOGGER.exception(
                "cleanup failed after event-loop error; preserving original cause"
            )
    return cleanup_ok
''',
)

replace_once(
    "retrotui/core/app.py",
    '''        if getattr(self, "_cleanup_complete", False):
            return True
''',
    '''        if getattr(self, "_cleanup_complete", False):
            return getattr(self, "_cleanup_result", True)
''',
)
replace_once(
    "retrotui/core/app.py",
    '''        finally:
            disable_mouse_support()
            self._cleanup_complete = True
            self._cleanup_started = False
        return success
''',
    '''        except Exception:
            success = False
            raise
        finally:
            self._cleanup_result = success
            disable_mouse_support()
            self._cleanup_complete = True
            self._cleanup_started = False
        return success
''',
)

replace_once(
    "retrotui/__main__.py",
    '''    app.run()
    # Capture the most recent external shutdown signal so ``run()`` can
''',
    '''    cleanup_ok = app.run()
    # Capture the most recent external shutdown signal so ``run()`` can
''',
)
replace_once(
    "retrotui/__main__.py",
    '''    if isinstance(shutdown_signal, int) and not isinstance(shutdown_signal, bool):
        _LAST_SHUTDOWN_SIGNAL = shutdown_signal

def _default_crash_log_dir() -> Path:
''',
    '''    if isinstance(shutdown_signal, int) and not isinstance(shutdown_signal, bool):
        _LAST_SHUTDOWN_SIGNAL = shutdown_signal
    return cleanup_ok


def _default_crash_log_dir() -> Path:
''',
)
replace_once(
    "retrotui/__main__.py",
    '''    try:
        curses.wrapper(main)
        print('\\033c', end='')
        if _LAST_SHUTDOWN_SIGNAL is not None:
            # Convention: ``128 + signum`` for terminations by signal.
            return 128 + _LAST_SHUTDOWN_SIGNAL
        return 0
''',
    '''    try:
        cleanup_ok = curses.wrapper(main)
        print('\\033c', end='')
        if _LAST_SHUTDOWN_SIGNAL is not None:
            # Convention: ``128 + signum`` for terminations by signal.
            return 128 + _LAST_SHUTDOWN_SIGNAL
        if cleanup_ok is False:
            print(
                "RetroTUI exited before every worker/window stopped cleanly.",
                file=sys.stderr,
            )
            return 1
        return 0
''',
)

replace_once(
    "retrotui/apps/wifi_manager.py",
    '''    def _connect_worker(self, cancel_event, ssid=None, password=None):
        # Legacy direct call: _connect_worker(ssid, password).
        if not callable(getattr(cancel_event, "is_set", None)):
            password = ssid
            ssid = cancel_event
            cancel_event = threading.Event()
        if cancel_event.is_set():
            self._finish_connect(False, "Connection cancelled.", cancel_event)
            return
        cmd = [self.nmcli, "dev", "wifi", "connect", ssid]
        if password:
            # Prefer stdin (--ask) so the password does not appear in
            # process listings. If the --ask invocation fails for any
            # reason, fall back to the explicit ``password`` argument —
            # but if it does, surface the failure to the user rather
            # than silently downgrading security.
            error_message = ""
            try:
                res = subprocess.run(
                    [self.nmcli, "--ask", "dev", "wifi", "connect", ssid],
                    input=password + "\\n",
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=NMCLI_CONNECT_TIMEOUT,
                )
                success = res.returncode == 0
                if not success:
                    error_message = (res.stderr or res.stdout or "").strip() or "Connection failed."
                self._finish_connect(success, error_message, cancel_event)
                return
            except subprocess.TimeoutExpired:
                self._finish_connect(False, "Connection timed out.", cancel_event)
                return
            except OSError as exc:
                # The --ask path is unavailable (e.g. ``nmcli`` not on
                # PATH for that subprocess call, or the option
                # rejected). Don't silently retry with the password on
                # argv — tell the user the secure path failed.
                self._finish_connect(
                    False,
                    f"Could not run nmcli --ask: {exc}. "
                    "Password was not sent insecurely; please report the error.",
                    cancel_event,
                )
                return
            cmd.extend(["password", password])
        success = False
        error_message = ""
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=NMCLI_CONNECT_TIMEOUT,
            )
            success = res.returncode == 0
            if not success:
                error_message = (res.stderr or res.stdout or "").strip() or "Connection failed."
        except subprocess.TimeoutExpired:
            error_message = "Connection timed out."
        except OSError as exc:
            error_message = str(exc) or "Execution failed."
        self._finish_connect(success, error_message, cancel_event)
''',
    '''    def _connect_worker(self, cancel_event, ssid=None, password=None):
        # Legacy direct call: _connect_worker(ssid, password).
        if not callable(getattr(cancel_event, "is_set", None)):
            password = ssid
            ssid = cancel_event
            cancel_event = threading.Event()
        if cancel_event.is_set():
            self._finish_connect(False, "Connection cancelled.", cancel_event)
            return

        success = False
        error_message = ""
        try:
            if password:
                cmd = [self.nmcli, "--ask", "dev", "wifi", "connect", ssid]
                run_kwargs = {"input": password + "\\n"}
            else:
                cmd = [self.nmcli, "dev", "wifi", "connect", ssid]
                run_kwargs = {}
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=NMCLI_CONNECT_TIMEOUT,
                **run_kwargs,
            )
            success = res.returncode == 0
            if not success:
                error_message = (
                    (res.stderr or res.stdout or "").strip()
                    or "Connection failed."
                )
        except subprocess.TimeoutExpired:
            error_message = "Connection timed out."
        except OSError as exc:
            error_message = str(exc) or "Execution failed."
        except Exception as exc:  # Worker boundary: always finalize owned state.
            LOGGER.exception("Unexpected nmcli connection failure")
            error_message = str(exc) or exc.__class__.__name__
        finally:
            self._finish_connect(success, error_message, cancel_event)
''',
)

replace_once(
    "retrotui/apps/retronet.py",
    '''class RetroNetWindow(Window):
    """Nostalgic yet ultra-modern text browser."""


def _cleanup_stale_viewsource_files''',
    '''def _cleanup_stale_viewsource_files''',
)
replace_once(
    "retrotui/apps/retronet.py",
    '''class RetroNetWindow(Window):

    def __init__(self, x, y, w, h):
''',
    '''class RetroNetWindow(Window):
    """Nostalgic text browser with isolated per-tab worker state."""

    def __init__(self, x, y, w, h):
''',
)

write_new(
    "tests/test_core_lifecycle_hardening.py",
    '''"""Focused regressions for lifecycle, process identity, and cleanup hardening."""
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

from _support import make_fake_curses

sys.modules["curses"] = make_fake_curses()

from retrotui import __main__ as main_mod
from retrotui.apps.process_manager import ProcessManagerWindow, ProcessRow
from retrotui.apps.wifi_manager import WifiManagerWindow
from retrotui.core import event_loop
from retrotui.core.actions import ActionType, ProcessSignalPayload
from retrotui.core.app import RetroTUI


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

    def test_cleanup_failure_remains_false_when_called_again(self):
        app = RetroTUI.__new__(RetroTUI)
        app._cleanup_complete = False
        app._cleanup_started = False
        app.running = True
        app._file_ops = types.SimpleNamespace(shutdown=mock.Mock(return_value=False))
        app._restore_runtime_signal_handlers = mock.Mock()
        app.windows = []
        app.window_mgr = types.SimpleNamespace(close_window=mock.Mock(return_value=True))
        app.dialog = None
        app.context_menu = None

        with mock.patch("retrotui.core.app.disable_mouse_support"):
            first = app.cleanup()
            second = app.cleanup()

        self.assertFalse(first)
        self.assertFalse(second)

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
''',
)

for relative_path in (
    "tools/apply_core_lifecycle_hardening.py",
    ".github/workflows/apply-core-lifecycle-hardening.yml",
):
    path = ROOT / relative_path
    if path.exists():
        path.unlink()

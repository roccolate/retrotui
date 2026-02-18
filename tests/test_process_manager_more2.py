import os
import sys
import types
import tempfile
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.BUTTON1_PRESSED = 1
    fake.BUTTON1_CLICKED = 2
    fake.BUTTON1_DOUBLE_CLICKED = 4
    fake.REPORT_MOUSE_POSITION = 0
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_LEFT = 260
    fake.KEY_RIGHT = 261
    fake.KEY_ENTER = 343
    fake.KEY_BACKSPACE = 263
    fake.KEY_DC = 330
    fake.KEY_HOME = 262
    fake.KEY_END = 360
    fake.KEY_PPAGE = 339
    fake.KEY_NPAGE = 338
    fake.KEY_F5 = -1
    sys.modules.setdefault("curses", fake)


_install_fake_curses()

from retrotui.apps.process_manager import ProcessManagerWindow, ProcessRow
from retrotui.core.actions import ActionType


class ProcessManagerMoreTests(unittest.TestCase):
    def setUp(self):
        self.win = ProcessManagerWindow(0, 0, 80, 20)

    def test_format_uptime(self):
        # hours/minutes
        self.assertEqual(self.win._format_uptime(3600 * 2 + 60 * 5), "02h 05m")
        # days present
        self.assertTrue(self.win._format_uptime(90000).endswith("m"))

    def test_sort_rows(self):
        rows = [
            ProcessRow(pid=1, cpu_percent=0.1, mem_percent=5.0, command='a', total_ticks=1),
            ProcessRow(pid=2, cpu_percent=9.9, mem_percent=1.0, command='b', total_ticks=2),
            ProcessRow(pid=3, cpu_percent=5.0, mem_percent=2.0, command='c', total_ticks=3),
        ]
        self.win.rows = list(rows)
        self.win.sort_key = 'cpu'
        self.win.sort_reverse = True
        self.win._sort_rows()
        self.assertEqual(self.win.rows[0].pid, 2)
        self.win.sort_key = 'mem'
        self.win.sort_reverse = False
        self.win._sort_rows()
        self.assertEqual(self.win.rows[0].pid, 2 if self.win.rows[0].mem_percent == 1.0 else self.win.rows[-1].pid)

    def test_refresh_processes_proc_error(self):
        with mock.patch('os.listdir', side_effect=OSError('boom')):
            self.win.refresh_processes(force=True)
            self.assertIsNotNone(self.win._error_message)

    def test_read_process_row_parsing_and_cpu_mem(self):
        pid = 99999

        # craft stat line: pid (name) <rest> ... ensure at least 13 tail fields with utime/stime at indexes 11/12
        tail = ['0'] * 11 + ['2', '3'] + ['0'] * 10
        stat_line = f"{pid} (mycmd) X " + ' '.join(tail)

        def fake_read_first_line(path):
            if path.endswith('/stat'):
                return stat_line
            if path.endswith('/statm'):
                return '7 5 0 0 0 0 0'
            if path.endswith('/comm'):
                return 'mycmd'
            if path.endswith('/stat'):
                return stat_line
            if path.endswith('/uptime'):
                return '123.45 0.0'
            if path.endswith('/loadavg'):
                return '0.01 0.02 0.03 1/1 0'
            return ''

        orig = ProcessManagerWindow._read_first_line
        try:
            ProcessManagerWindow._read_first_line = staticmethod(fake_read_first_line)
            # make it look like we had previous ticks so cpu_percent is computed
            self.win._prev_proc_ticks = {pid: 1}
            row = self.win._read_process_row(pid, total_delta=10, mem_total_kb=1000)
            self.assertIsNotNone(row)
            self.assertGreaterEqual(row.mem_percent, 0.0)
            self.assertEqual(row.pid, pid)
        finally:
            ProcessManagerWindow._read_first_line = staticmethod(orig)

    def test_request_and_kill_process_behavior(self):
        # no selection
        self.win.rows = []
        self.assertEqual(self.win.request_kill_selected().type, ActionType.ERROR)

        # create a fake row and test permission/lookup
        r = ProcessRow(pid=12345, cpu_percent=0, mem_percent=0, command='x', total_ticks=0)
        self.win.rows = [r]
        self.win.selected_index = 0
        res = self.win.request_kill_selected()
        self.assertEqual(res.type, ActionType.REQUEST_KILL_CONFIRM)

        # kill with invalid pid
        err = self.win.kill_process({'pid': 0})
        self.assertEqual(err.type, ActionType.ERROR)

        # ProcessLookupError -> refresh and return None
        with mock.patch('os.kill', side_effect=ProcessLookupError):
            with mock.patch.object(self.win, 'refresh_processes') as fake_refresh:
                out = self.win.kill_process({'pid': 12345})
                self.assertIsNone(out)
                fake_refresh.assert_called()

        # PermissionError -> error result
        with mock.patch('os.kill', side_effect=PermissionError):
            out2 = self.win.kill_process({'pid': 12345})
            self.assertEqual(out2.type, ActionType.ERROR)

        # success path
        with mock.patch('os.kill', return_value=None):
            with mock.patch.object(self.win, 'refresh_processes') as fake_refresh2:
                out3 = self.win.kill_process({'pid': 12345})
                self.assertIsNone(out3)
                fake_refresh2.assert_called()


if __name__ == '__main__':
    unittest.main()

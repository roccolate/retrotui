import os
import unittest
import tempfile
import types
import sys
from tests._support import make_fake_curses

sys.modules['curses'] = make_fake_curses()

from retrotui.apps.process_manager import (
    ProcessManagerWindow,
)


class ProcessManagerRemainingTests(unittest.TestCase):
    def test_format_uptime_variants(self):
        # less than a day
        self.assertEqual(ProcessManagerWindow._format_uptime(3661), '01h 01m')
        # several days
        days = 2 * 86400 + 3 * 3600 + 5 * 60
        self.assertTrue('d' in ProcessManagerWindow._format_uptime(days))

    def test_read_total_jiffies_malformed(self):
        orig = ProcessManagerWindow._read_first_line
        ProcessManagerWindow._read_first_line = staticmethod(lambda p: 'no-cpu')
        try:
            self.assertEqual(ProcessManagerWindow._read_total_jiffies(), 0)
        finally:
            ProcessManagerWindow._read_first_line = orig

    def test_read_command_fallbacks(self):
        # Ensure that when cmdline open fails, comm is used via _read_first_line
        orig_open = open
        def fake_open(path, *a, **k):
            raise OSError()
        orig_first = ProcessManagerWindow._read_first_line
        ProcessManagerWindow._read_first_line = staticmethod(lambda p: 'comm-name')
        try:
            builtins_open = __builtins__['open'] if isinstance(__builtins__, dict) else __builtins__.open
            # monkeypatch by assigning to builtins
            if isinstance(__builtins__, dict):
                __builtins__['open'] = fake_open
            else:
                __builtins__.open = fake_open
            try:
                self.assertEqual(ProcessManagerWindow._read_command(99999), 'comm-name')
            finally:
                if isinstance(__builtins__, dict):
                    __builtins__['open'] = builtins_open
                else:
                    __builtins__.open = builtins_open
        finally:
            ProcessManagerWindow._read_first_line = orig_first

    def test_read_process_row_parsing_and_cpu_mem(self):
        win = ProcessManagerWindow(0, 0, 80, 24)
        # craft fake stat and statm lines
        pid = 12345
        def fake_read_first(path):
            if path.endswith('/stat'):
                # format: pid (name) rest... ensure enough tail fields
                return f"{pid} (proc) S 0 0 0 0 0 0 0 0 0 100 50 0 0 0 0 0 0 0 0 0 0 0"
            if path.endswith('/statm'):
                return '10 2 0 0 0 0 0'
            return '0'

        orig = ProcessManagerWindow._read_first_line
        ProcessManagerWindow._read_first_line = staticmethod(fake_read_first)
        try:
            # simulate previous totals so cpu_percent computes non-zero
            total_delta = 100
            win._page_kb = 4
            win._cpu_count = 1
            win._prev_proc_ticks = {pid: 50}
            row = win._read_process_row(pid, total_delta, mem_total_kb=1024)
            self.assertIsNotNone(row)
            self.assertEqual(row.pid, pid)
            self.assertGreaterEqual(row.mem_percent, 0.0)
        finally:
            ProcessManagerWindow._read_first_line = orig

    def test_refresh_processes_proc_error(self):
        win = ProcessManagerWindow(0, 0, 80, 24)
        orig_listdir = os.listdir
        os.listdir = lambda p: (_ for _ in ()).throw(OSError('boom'))
        try:
            win.refresh_processes(force=True)
            self.assertIsNotNone(win._error_message)
        finally:
            os.listdir = orig_listdir


if __name__ == '__main__':
    unittest.main()

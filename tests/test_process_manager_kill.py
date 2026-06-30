import os
import types
import sys
import unittest
from _support import make_fake_curses

sys.modules['curses'] = make_fake_curses()

from retrotui.apps.process_manager import ProcessManagerWindow
from retrotui.core.actions import ActionType


class ProcessManagerKillTests(unittest.TestCase):
    def test_request_kill_selected_no_rows(self):
        win = ProcessManagerWindow(0, 0, 80, 24)
        win.rows = []
        res = win.request_kill_selected()
        self.assertIsNotNone(res)
        self.assertEqual(res.type, ActionType.ERROR)

    def test_kill_process_invalid_pid(self):
        win = ProcessManagerWindow(0, 0, 80, 24)
        res = win.kill_process({'pid': 0, 'signal': 15})
        self.assertIsNotNone(res)
        self.assertEqual(res.type, ActionType.ERROR)

    def test_kill_process_processlookup_and_permission(self):
        win = ProcessManagerWindow(0, 0, 80, 24)
        orig_kill = os.kill
        try:
            # ProcessLookupError -> the process is already gone; surface
            # a REFRESH with a human-readable message so the user is
            # not left wondering why the kill button silently did
            # nothing.
            def raise_lookup(pid, sig):
                raise ProcessLookupError()
            os.kill = raise_lookup
            res = win.kill_process({'pid': 99999, 'signal': 15})
            self.assertIsNotNone(res)
            self.assertEqual(res.type, ActionType.REFRESH)

            # PermissionError -> returns ActionResult error
            def raise_perm(pid, sig):
                raise PermissionError()
            os.kill = raise_perm
            res = win.kill_process({'pid': 99999, 'signal': 15})
            self.assertIsNotNone(res)
            self.assertEqual(res.type, ActionType.ERROR)
        finally:
            os.kill = orig_kill


if __name__ == '__main__':
    unittest.main()

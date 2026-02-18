import sys
import types
import unittest
from tests._support import make_fake_curses

sys.modules['curses'] = make_fake_curses()

from retrotui.apps.process_manager import ProcessManagerWindow, ProcessRow
from retrotui.core.actions import ActionType


class FakeStdScr:
    def __init__(self, h=24, w=80):
        self.h = h
        self.w = w
        self.calls = []

    def getmaxyx(self):
        return self.h, self.w

    def addnstr(self, y, x, text, max_len, attr=0):
        self.calls.append((y, x, text[:max_len], attr))

    def refresh(self):
        pass


class ProcessManagerMoreEdgesTests(unittest.TestCase):
    def test_draw_renders_table_and_summary(self):
        win = ProcessManagerWindow(0, 0, 80, 12)
        win.rows = [
            ProcessRow(pid=1, cpu_percent=1.0, mem_percent=2.0, command='one', total_ticks=10),
            ProcessRow(pid=2, cpu_percent=3.0, mem_percent=4.0, command='two', total_ticks=20),
        ]
        std = FakeStdScr(h=12, w=80)
        win.visible = True
        win.draw(std)
        self.assertTrue(len(std.calls) > 0)

    def test_handle_click_double_returns_kill_request(self):
        win = ProcessManagerWindow(0, 0, 80, 12)
        win.rows = [ProcessRow(pid=42, cpu_percent=0, mem_percent=0, command='x', total_ticks=0)]
        win.selected_index = 0
        bx, by, bw, bh = win.body_rect()
        # click on first data row (by+1)
        res = win.handle_click(bx, by + 1, bstate=sys.modules['curses'].BUTTON1_DOUBLE_CLICKED)
        self.assertIsNotNone(res)
        self.assertEqual(res.type, ActionType.REQUEST_KILL_CONFIRM)

    def test_handle_key_sorts_and_close(self):
        win = ProcessManagerWindow(0, 0, 80, 12)
        # c -> sort cpu
        win.handle_key(ord('c'))
        self.assertEqual(win.sort_key, 'cpu')
        win.handle_key(ord('m'))
        self.assertEqual(win.sort_key, 'mem')
        win.handle_key(ord('p'))
        self.assertEqual(win.sort_key, 'pid')
        # k -> request kill
        res = win.handle_key(ord('k'))
        self.assertIsNotNone(res)
        # q -> close
        res = win.handle_key(ord('q'))
        self.assertIsNotNone(res)
        self.assertEqual(res.type, ActionType.EXECUTE)


if __name__ == '__main__':
    unittest.main()

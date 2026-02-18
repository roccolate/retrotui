import sys
import types
import unittest

from _support import make_fake_curses

sys.modules['curses'] = make_fake_curses()

from retrotui.apps.process_manager import ProcessManagerWindow, ProcessRow


class ProcessManagerSortPagingTests(unittest.TestCase):
    def test_sort_rows_cpu_and_mem_and_pid(self):
        win = ProcessManagerWindow(0, 0, 80, 20)
        win.rows = [
            ProcessRow(pid=1, cpu_percent=1.0, mem_percent=5.0, command='a', total_ticks=10),
            ProcessRow(pid=2, cpu_percent=10.0, mem_percent=1.0, command='b', total_ticks=20),
            ProcessRow(pid=3, cpu_percent=5.0, mem_percent=2.0, command='c', total_ticks=30),
        ]

        win.sort_key = 'cpu'
        win.sort_reverse = True
        win._sort_rows()
        self.assertEqual(win.rows[0].pid, 2)

        win.sort_key = 'mem'
        win.sort_reverse = True
        win._sort_rows()
        self.assertEqual(win.rows[0].pid, 1)

        win.sort_key = 'pid'
        win.sort_reverse = False
        win._sort_rows()
        self.assertEqual(win.rows[0].pid, 1)

    def test_visible_rows_and_paging_handle_key(self):
        win = ProcessManagerWindow(0, 0, 80, 10)
        # create many rows
        win.rows = [ProcessRow(pid=i, cpu_percent=0, mem_percent=0, command=str(i), total_ticks=0) for i in range(30)]
        # page down increases selected_index
        prev = win.selected_index
        import curses
        win.handle_key(curses.KEY_NPAGE)
        self.assertGreaterEqual(win.selected_index, prev)
        # page up decreases selected_index
        win.handle_key(curses.KEY_PPAGE)
        # ensure index within bounds
        self.assertTrue(0 <= win.selected_index < len(win.rows))


if __name__ == '__main__':
    unittest.main()

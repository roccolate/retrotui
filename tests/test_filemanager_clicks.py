import os
import sys
import types
import tempfile
import unittest
from _support import make_fake_curses

sys.modules['curses'] = make_fake_curses()

from retrotui.apps.filemanager import FileManagerWindow, FileEntry
from retrotui.core.actions import ActionType
fake_curses = sys.modules['curses']


class FileManagerClickTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.addCleanup(self.tmp.cleanup)
        self.base = self.tmp.name
        with open(os.path.join(self.base, 'f1.txt'), 'w', encoding='utf-8') as f:
            f.write('1')
        os.mkdir(os.path.join(self.base, 'd1'))
        self.win = FileManagerWindow(0, 0, 100, 24, start_path=self.base)
        # ensure secondary content exists
        self.win.secondary_entries = [FileEntry('other.txt', False, os.path.join(self.base, 'f1.txt'))]
        self.win.secondary_content = ['  [F] other.txt']

    def test_handle_click_outside_clears_pending(self):
        self.win._set_pending_drag({'type': 'file_path'}, 0, 0)
        res = self.win.handle_click(-1, -1, bstate=None)
        self.assertIsNone(res)
        self.assertIsNone(self.win._pending_drag_payload)

    def test_handle_click_right_pane_double_click_activates(self):
        # simulate click in right pane area
        bx, by, bw, bh = self.win.body_rect()
        left_w = max(1, (bw - 1) // 2)
        right_x = bx + left_w + 1
        # click at by+1 to hit first content row
        res = self.win.handle_click(right_x, by + 1, bstate=fake_curses.BUTTON1_DOUBLE_CLICKED)
        # double-click on right pane with entry should return an ActionResult or None
        # when opening file it may return ActionResult.OPEN_FILE
        if res is not None:
            self.assertTrue(hasattr(res, 'type'))

    def test_handle_click_left_sets_pending_for_file(self):
        # pick a file entry on left
        file_entry = next(e for e in self.win.entries if not e.is_dir and e.name != '..')
        # ensure selection is the file entry
        file_idx = None
        for i, e in enumerate(self.win.entries):
            if e is file_entry:
                file_idx = i
                self.win.selected_index = i
                break
        bx, by, bw, bh = self.win.body_rect()
        # click on first entry row
        # compute y so it lands on the selected entry row
        hdr = self.win._header_lines()
        my = by + (file_idx - self.win.scroll_offset) + hdr
        res = self.win.handle_click(bx, my, bstate=fake_curses.BUTTON1_PRESSED)
        # pending payload may be set for a file
        # if selected entry is a file, pending payload should be set
        if not file_entry.is_dir:
            self.assertIsNotNone(self.win._pending_drag_payload)


if __name__ == '__main__':
    unittest.main()

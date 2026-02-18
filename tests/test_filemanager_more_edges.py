import os
import sys
import tempfile
import unittest
from _support import make_fake_curses

sys.modules['curses'] = make_fake_curses()
fake_curses = sys.modules['curses']

from retrotui.apps.filemanager import FileManagerWindow, FileEntry
from retrotui.core.actions import ActionType


class FileManagerMoreEdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.addCleanup(self.tmp.cleanup)
        self.base = self.tmp.name
        with open(os.path.join(self.base, 'f.txt'), 'w', encoding='utf-8') as f:
            f.write('x')
        os.mkdir(os.path.join(self.base, 'd'))
        self.win = FileManagerWindow(0, 0, 60, 10, start_path=self.base)

    def test_panel_layout_small_width(self):
        # width below PREVIEW_MIN_WIDTH should disable preview
        self.win.w = 30
        list_w, sep, px, pw = self.win._panel_layout()
        self.assertEqual(pw, 0)

    def test_preview_stat_key_on_missing_path(self):
        key = self.win._preview_stat_key(os.path.join(self.base, 'nope'))
        self.assertEqual(key[1], None)

    def test_entry_preview_directory_unreadable(self):
        # make directory unreadable by pointing to a path that raises OSError
        entry = FileEntry('d', True, os.path.join(self.base, 'd'))
        # simulate os.listdir raising
        orig = os.listdir
        os.listdir = lambda p: (_ for _ in ()).throw(OSError('boom'))
        try:
            lines = self.win._entry_preview_lines(entry, max_lines=3)
            self.assertEqual(lines, ['[directory not readable]'])
        finally:
            os.listdir = orig

    def test_entry_info_unreadable(self):
        entry = FileEntry('f.txt', False, os.path.join(self.base, 'f.txt'))
        orig = os.stat
        def raise_os(path):
            raise OSError()
        os.stat = raise_os
        try:
            info = self.win._entry_info_lines(entry)
            self.assertIn('unreadable', ''.join(info))
        finally:
            os.stat = orig

    def test_dual_copy_move_between_panes_errors(self):
        # enable dual pane but no selection
        self.win.dual_pane_enabled = True
        self.win.active_pane = 0
        # clear entries
        self.win.entries = []
        res = self.win._dual_copy_move_between_panes(move=False)
        self.assertIsNotNone(res)

    def test_copy_move_selected_via_resolve_errors(self):
        # select file and attempt copy to invalid dest
        self.win._rebuild_content()
        self.win.selected_index = 0
        res = self.win.copy_selected('')
        self.assertIsNotNone(res)


if __name__ == '__main__':
    unittest.main()

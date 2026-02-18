import os
import sys
import shutil
import tempfile
from tests._support import make_fake_curses
import unittest

sys.modules['curses'] = make_fake_curses()

from retrotui.apps.filemanager import FileManagerWindow, FileEntry


class FileManagerDualCopyMoveTests(unittest.TestCase):
    def setUp(self):
        self.left = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.right = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.addCleanup(self.left.cleanup)
        self.addCleanup(self.right.cleanup)
        # left dir has a file
        with open(os.path.join(self.left.name, 'a.txt'), 'w', encoding='utf-8') as f:
            f.write('a')
        self.win = FileManagerWindow(0, 0, 120, 30, start_path=self.left.name)
        self.win.dual_pane_enabled = True
        self.win.secondary_path = self.right.name
        # rebuild content for both panes
        self.win._rebuild_content()
        self.win._rebuild_secondary_content()

    def test_dual_copy_between_panes(self):
        # select the file on left
        for i, e in enumerate(self.win.entries):
            if e.name == 'a.txt':
                self.win.selected_index = i
                break
        # perform copy
        res = self.win._dual_copy_move_between_panes(move=False)
        self.assertIsNone(res)
        # file should exist on right
        self.assertTrue(os.path.exists(os.path.join(self.right.name, 'a.txt')))

    def test_dual_move_between_panes(self):
        # select the file on left again
        for i, e in enumerate(self.win.entries):
            if e.name == 'a.txt':
                self.win.selected_index = i
                break
        # move
        res = self.win._dual_copy_move_between_panes(move=True)
        self.assertIsNone(res)
        # original gone, moved to right
        self.assertFalse(os.path.exists(os.path.join(self.left.name, 'a.txt')))
        self.assertTrue(os.path.exists(os.path.join(self.right.name, 'a.txt')))


if __name__ == '__main__':
    unittest.main()

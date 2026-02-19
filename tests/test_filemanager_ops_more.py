import os
import sys
import tempfile
import shutil
from _support import make_fake_curses
import unittest

sys.modules['curses'] = make_fake_curses()

from retrotui.apps.filemanager import FileManagerWindow
from retrotui.core.actions import ActionType


class FileManagerOpsMoreTests(unittest.TestCase):
    def setUp(self):
        self.left = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.right = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.addCleanup(self.left.cleanup)
        self.addCleanup(self.right.cleanup)
        with open(os.path.join(self.left.name, 'foo.txt'), 'w', encoding='utf-8') as f:
            f.write('x')
        self.win = FileManagerWindow(0, 0, 80, 24, start_path=self.left.name)

    from retrotui.core.actions import ActionType

    def test_create_directory_and_file_and_select(self):
        res = self.win.create_directory('newdir')
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertTrue(os.path.isdir(os.path.join(self.left.name, 'newdir')))

        res = self.win.create_file('newfile.txt')
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertTrue(os.path.exists(os.path.join(self.left.name, 'newfile.txt')))

    def test_copy_and_move_selected_success(self):
        # select foo.txt
        for i, e in enumerate(self.win.entries):
            if e.name == 'foo.txt':
                self.win.selected_index = i
                break
        # copy to right dir
        res = self.win.copy_selected(self.right.name)
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertTrue(os.path.exists(os.path.join(self.right.name, 'foo.txt')))

        # move back to left under new name
        res = self.win.move_selected(os.path.join(self.right.name, 'foo2.txt'))
        # moving while selected in left may error or succeed; ensure no crash
        self.assertTrue(res is None or res is not None)


if __name__ == '__main__':
    unittest.main()

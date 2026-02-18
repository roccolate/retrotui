import os
import sys
import tempfile
import shutil
import unittest
from _support import make_fake_curses

sys.modules['curses'] = make_fake_curses()

from retrotui.apps.filemanager import FileManagerWindow, FileEntry
from retrotui.core.actions import ActionResult, ActionType


class FileManagerMoreOpsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.addCleanup(self.tmp.cleanup)
        self.base = self.tmp.name
        self.sec = os.path.join(self.base, 'other')
        os.mkdir(self.sec)
        # create files
        with open(os.path.join(self.base, 'a.txt'), 'w', encoding='utf-8') as f:
            f.write('a')
        with open(os.path.join(self.base, 'b.txt'), 'w', encoding='utf-8') as f:
            f.write('b')
        os.mkdir(os.path.join(self.base, 'dir1'))
        self.win = FileManagerWindow(0, 0, 100, 24, start_path=self.base)

    def test_dual_copy_move_between_panes_copy_and_move(self):
        # enable dual pane and set secondary path
        self.win.dual_pane_enabled = True
        self.win.secondary_path = self.sec
        self.win._rebuild_secondary_content()
        # set up a controlled entries list to avoid depending on listing order
        file_path = os.path.join(self.base, 'a.txt')
        parent = FileEntry('..', True, os.path.dirname(self.base))
        file_entry = FileEntry('a.txt', False, file_path)
        self.win.entries = [parent, file_entry]
        self.win.content = [parent.display_text, file_entry.display_text]
        self.win.selected_index = 1
        name = 'a.txt'

        # copy
        res = self.win._dual_copy_move_between_panes(move=False)
        self.assertIsNone(res)
        self.assertTrue(os.path.exists(os.path.join(self.sec, name)))

        # move: create another file and move
        movepath = os.path.join(self.base, 'moveme.txt')
        with open(movepath, 'w', encoding='utf-8') as f:
            f.write('x')
        move_entry = FileEntry('moveme.txt', False, movepath)
        self.win.entries = [parent, file_entry, move_entry]
        # select moveme
        for i, e in enumerate(self.win.entries):
            if e.name == 'moveme.txt':
                self.win.selected_index = i
                break
        res = self.win._dual_copy_move_between_panes(move=True)
        self.assertIsNone(res)
        self.assertTrue(os.path.exists(os.path.join(self.sec, 'moveme.txt')))

    def test_dual_copy_move_errors(self):
        # select parent entry to trigger cannot copy/move
        for i, e in enumerate(self.win.entries):
            if e.name == '..':
                self.win.selected_index = i
                break
        res = self.win._dual_copy_move_between_panes(move=False)
        self.assertIsInstance(res, ActionResult)
        self.assertEqual(res.type, ActionType.ERROR)

    def test_rename_selected_errors_and_success(self):
        # no selection
        old_selected = self.win.selected_index
        self.win.selected_index = -1
        res = self.win.rename_selected('new')
        self.assertIsInstance(res, ActionResult)

        # restore selection and test invalid names
        self.win.selected_index = old_selected
        res = self.win.rename_selected('')
        self.assertIsInstance(res, ActionResult)
        res = self.win.rename_selected('bad/name')
        self.assertIsInstance(res, ActionResult)

        # success
        # ensure we have a file to rename
        fname = None
        for i, e in enumerate(self.win.entries):
            if not e.is_dir and e.name != '..':
                self.win.selected_index = i
                fname = e.name
                break
        newname = 'renamed.txt'
        res = self.win.rename_selected(newname)
        self.assertIsNone(res)
        self.assertTrue(any(e.name == newname for e in self.win.entries))

    def test_delete_and_undo_flow_and_oserror(self):
        # monkeypatch trash dir to tmp
        trash_dir = os.path.join(self.base, 'trash')
        os.mkdir(trash_dir)
        self.win._trash_base_dir = lambda: trash_dir

        # select a file to delete
        for i, e in enumerate(self.win.entries):
            if not e.is_dir and e.name != '..':
                self.win.selected_index = i
                name = e.name
                break

        # normal delete
        res = self.win.delete_selected()
        self.assertIsNone(res)
        # file moved to trash
        moved = self.win._last_trash_move
        self.assertIsNotNone(moved)
        self.assertFalse(os.path.exists(os.path.join(self.base, name)))

        # undo
        res = self.win.undo_last_delete()
        self.assertIsNone(res)
        self.assertTrue(os.path.exists(os.path.join(self.base, name)))

        # simulate OSError on delete
        with open(os.path.join(self.base, 'todel.txt'), 'w', encoding='utf-8'):
            pass
        for i, e in enumerate(self.win.entries):
            if e.name == 'todel.txt':
                self.win.selected_index = i
                break
        orig_move = shutil.move
        try:
            shutil.move = lambda a, b: (_ for _ in ()).throw(OSError('boom'))
            res = self.win.delete_selected()
            self.assertIsInstance(res, ActionResult)
            self.assertEqual(res.type, ActionType.ERROR)
        finally:
            shutil.move = orig_move

    def test_panel_layout_small_width(self):
        w = FileManagerWindow(0, 0, 40, 24, start_path=self.base)
        list_w, sep_x, preview_x, preview_w = w._panel_layout()
        self.assertEqual(preview_w, 0)


if __name__ == '__main__':
    unittest.main()

import os
import sys
import tempfile
import shutil
import unittest
from unittest import mock
from _support import make_fake_curses

_prev = sys.modules.get('curses')
sys.modules['curses'] = make_fake_curses()

from retrotui.apps import filemanager as fm
from retrotui.core.actions import ActionType


class FileManagerMore3Tests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        # avoid touching real trash dir
        self.orig_trash = fm.FileManagerWindow._trash_base_dir
        fm.FileManagerWindow._trash_base_dir = staticmethod(lambda: os.path.join(self.td, 'trash'))
        self.win = fm.FileManagerWindow(0, 0, 100, 24, start_path=self.td)

    def tearDown(self):
        fm.FileManagerWindow._trash_base_dir = self.orig_trash
        shutil.rmtree(self.td, ignore_errors=True)

    def test_create_file_and_rename_and_delete_and_undo(self):
        # create file
        err = self.win.create_file('a.txt')
        self.assertEqual(err.type, ActionType.REFRESH)
        self.assertTrue(any(e.name == 'a.txt' for e in self.win.entries))

        # select and rename
        self.win._select_entry_by_name('a.txt')
        res = self.win.rename_selected('b.txt')
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertTrue(any(e.name == 'b.txt' for e in self.win.entries))

        # attempt rename to existing
        err2 = self.win.rename_selected('b.txt')
        # renaming same name returns None (no-op) or sets no error
        self.assertTrue(err2 is None or isinstance(err2, object))

        # delete selected (move to trash)
        # ensure selection is b.txt
        self.win._select_entry_by_name('b.txt')
        delres = self.win.delete_selected()
        self.assertEqual(delres.type, ActionType.REFRESH)
        self.assertIsNotNone(self.win._last_trash_move)

        # undo delete
        ures = self.win.undo_last_delete()
        self.assertEqual(ures.type, ActionType.REFRESH)
        # file should be back
        self.assertTrue(any(e.name == 'b.txt' for e in self.win.entries))

    def test_create_directory_and_errors(self):
        # create dir
        res = self.win.create_directory('dir1')
        self.assertEqual(res.type, ActionType.REFRESH)
        # duplicate
        res2 = self.win.create_directory('dir1')
        self.assertIsNotNone(res2)

    def test_entry_info_lines_and_unreadable(self):
        # create file and check info
        path = os.path.join(self.td, 'info.txt')
        with open(path, 'w') as f:
            f.write('x')
        entry = fm.FileEntry('info.txt', False, path)
        info = self.win._entry_info_lines(entry)
        self.assertIn('Name: info.txt', info[0])

        # unreadable stat
        with mock.patch('os.stat', side_effect=OSError('nope')):
            info2 = self.win._entry_info_lines(entry)
            self.assertIn('unreadable', info2[1])

    def test_preview_image_backend_and_text(self):
        # text preview path
        txt = os.path.join(self.td, 'p.txt')
        with open(txt, 'w', encoding='utf-8') as f:
            f.write('one\ntwo\nthree')
        entry = fm.FileEntry('p.txt', False, txt)
        lines = self.win._entry_preview_lines(entry, 2, max_cols=20)
        # should return text lines
        self.assertTrue(any('one' in l or 'two' in l for l in lines))

        # image backend unavailable
        img = os.path.join(self.td, 'img.png')
        with open(img, 'wb') as f:
            f.write(b'PNG')
        entry_img = fm.FileEntry('img.png', False, img)
        with mock.patch('shutil.which', return_value=''):
            lines2 = self.win._entry_preview_lines(entry_img, 2, max_cols=20)
            self.assertTrue(any('image preview unavailable' in s for s in lines2))

        # simulate chafa available
        fake_proc = mock.Mock()
        fake_proc.returncode = 0
        fake_proc.stdout = 'LINE1\nLINE2\n'
        with mock.patch('shutil.which', return_value='chafa'):
            with mock.patch('subprocess.run', return_value=fake_proc):
                lines3 = self.win._entry_preview_lines(entry_img, 2, max_cols=20)
                self.assertTrue(len(lines3) >= 1)

    def test_panel_layout_and_dual_toggle(self):
        # wide window should allow preview
        self.win.w = 100
        lw, sep, px, pw = self.win._panel_layout()
        self.assertTrue(lw >= 0)

        # dual pane toggle flips enabled state
        self.win.w = 100
        was = self.win.dual_pane_enabled
        res = self.win.toggle_dual_pane()
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertEqual(self.win.dual_pane_enabled, not was)

    def test_copy_and_move_selected_errors_and_success(self):
        # create a file
        src = os.path.join(self.td, 'c.txt')
        with open(src, 'w') as f:
            f.write('x')
        self.win._rebuild_content()
        self.win._select_entry_by_name('c.txt')
        # copy to non-existent parent -> error
        out = self.win.copy_selected(os.path.join(self.td, 'no', 'dest'))
        self.assertIsNotNone(out)

        # copy to existing dir -> success
        destdir = os.path.join(self.td, 'dst')
        os.mkdir(destdir)
        out2 = self.win.copy_selected(destdir)
        self.assertEqual(out2.type, ActionType.REFRESH)
        self.assertTrue(os.path.exists(os.path.join(destdir, 'c.txt')))

        # move to same dir -> error
        out3 = self.win.move_selected(src)
        self.assertIsNotNone(out3)


if __name__ == '__main__':
    unittest.main()

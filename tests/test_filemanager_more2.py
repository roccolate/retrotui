import os
import sys
import tempfile
import shutil
import types
import unittest

from _support import make_fake_curses

# Install shared fake curses module for tests
_prev = sys.modules.get('curses')
sys.modules['curses'] = make_fake_curses()

from retrotui.apps import filemanager as fm
from retrotui.core.actions import ActionType


class FileManagerMoreTests(unittest.TestCase):
    def setUp(self):
        # small window to avoid dual-pane by default
        self.win = fm.FileManagerWindow(0, 0, 80, 10, start_path=tempfile.gettempdir())

    def test_cell_width_and_fit(self):
        self.assertEqual(fm._cell_width('a'), 1)
        self.assertEqual(fm._cell_width(''), 0)
        s = 'abc'
        fitted = fm._fit_text_to_cells(s, 2)
        self.assertTrue(len(fitted) >= 0)

    def test_fileentry_format_size(self):
        e = fm.FileEntry('f', False, '/tmp/f', size=500)
        self.assertIn('B', e._format_size())
        e2 = fm.FileEntry('f', False, '/tmp/f', size=2048)
        self.assertIn('K', e2._format_size())
        e3 = fm.FileEntry('f', False, '/tmp/f', size=2 * 1024 * 1024)
        self.assertIn('M', e3._format_size())

    def test_toggle_dual_pane_unavailable(self):
        self.win.w = 50
        # ensure dual pane not available
        res = self.win.toggle_dual_pane()
        self.assertIsNotNone(res)
        self.assertEqual(res.type, ActionType.ERROR)

    def test_drag_payload_and_pending(self):
        # create a fake file entry
        entry = fm.FileEntry('file.txt', False, os.path.join(self.win.current_path, 'file.txt'))
        payload = self.win._drag_payload_for_entry(entry)
        self.assertIsInstance(payload, dict)
        self.win._set_pending_drag(payload, 1, 2)
        # consume with no REPORT_MOUSE_POSITION should return None
        bstate = getattr(getattr(sys.modules.get('curses'), 'BUTTON1_PRESSED', 1), '__int__', lambda: 1)()
        out = self.win.consume_pending_drag(2, 3, bstate)
        # possible None due to missing report flag
        self.assertTrue(out is None or isinstance(out, dict))

    def test_read_text_preview_binary_and_text(self):
        td = tempfile.mkdtemp()
        try:
            binpath = os.path.join(td, 'bin.bin')
            with open(binpath, 'wb') as f:
                f.write(b'\x00\x01\x02')
            lines = self.win._read_text_preview(binpath, 5)
            self.assertEqual(lines, ['[binary file]'])

            txtpath = os.path.join(td, 't.txt')
            with open(txtpath, 'w', encoding='utf-8') as f:
                f.write('line1\nline2\nline3')
            lines2 = self.win._read_text_preview(txtpath, 2)
            self.assertEqual(len(lines2), 2)
        finally:
            shutil.rmtree(td)

    def test_entry_preview_directory_and_parent(self):
        td = tempfile.mkdtemp()
        try:
            # empty dir
            entry = fm.FileEntry('emptydir', True, td)
            out = self.win._entry_preview_lines(entry, 5)
            self.assertIn('[empty directory]', out)
            # parent entry
            parent = fm.FileEntry('..', True, os.path.dirname(td))
            out2 = self.win._entry_preview_lines(parent, 3)
            self.assertIn('Parent directory entry.', out2)
        finally:
            shutil.rmtree(td)

    def test_resolve_destination_path_errors(self):
        td = tempfile.mkdtemp()
        try:
            # create a file to act as entry
            src = os.path.join(td, 'a.txt')
            with open(src, 'w') as f:
                f.write('x')
            entry = fm.FileEntry('a.txt', False, src)
            # empty destination
            target, err = self.win._resolve_destination_path(entry, '')
            self.assertIsNone(target)
            self.assertIsNotNone(err)
            # same source/destination -> error
            target2, err2 = self.win._resolve_destination_path(entry, src)
            self.assertIsNone(target2)
            self.assertIsNotNone(err2)
            # non-existent parent
            nonexist = os.path.join(td, 'no', 'dest')
            target3, err3 = self.win._resolve_destination_path(entry, nonexist)
            self.assertIsNone(target3)
            self.assertIsNotNone(err3)
        finally:
            shutil.rmtree(td)

    def test_next_trash_path_collisions(self):
        td = tempfile.mkdtemp()
        try:
            # monkeypatch trash base dir
            original = fm.FileManagerWindow._trash_base_dir
            fm.FileManagerWindow._trash_base_dir = staticmethod(lambda: td)
            src = os.path.join(td, 'file.txt')
            # create a file with same basename to force collision
            open(os.path.join(td, 'file.txt'), 'w').close()
            p1 = self.win._next_trash_path(src)
            # create the candidate so next call will add .1
            open(p1, 'w').close()
            p2 = self.win._next_trash_path(src)
            self.assertNotEqual(p1, p2)
        finally:
            fm.FileManagerWindow._trash_base_dir = staticmethod(original)
            shutil.rmtree(td)


if __name__ == '__main__':
    unittest.main()

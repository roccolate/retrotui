import os
import sys
import tempfile
import subprocess
import shutil
import unittest
from types import SimpleNamespace
from _support import make_fake_curses

sys.modules['curses'] = make_fake_curses()
import curses

from retrotui.apps.filemanager import FileManagerWindow, FileEntry
from retrotui.core.actions import ActionResult, ActionType


class FileManagerPreviewOpsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.addCleanup(self.tmp.cleanup)
        self.base = self.tmp.name
        # create some files and dirs
        with open(os.path.join(self.base, 'text.txt'), 'w', encoding='utf-8') as f:
            f.write('line1\nline2\n')
        with open(os.path.join(self.base, 'bin.bin'), 'wb') as f:
            f.write(b'\x00\x01')
        os.mkdir(os.path.join(self.base, 'emptydir'))
        self.win = FileManagerWindow(0, 0, 80, 24, start_path=self.base)

    def test_read_text_preview_empty_and_binary(self):
        # empty file
        empty = os.path.join(self.base, 'empty.txt')
        open(empty, 'w', encoding='utf-8').close()
        out = self.win._read_text_preview(empty, max_lines=5)
        self.assertEqual(out, ['[empty file]'])

        # binary file
        out = self.win._read_text_preview(os.path.join(self.base, 'bin.bin'), max_lines=5)
        self.assertEqual(out, ['[binary file]'])

    def test_read_image_preview_with_backend(self):
        # simulate chafa present and subprocess.run returning textual output
        orig_which = shutil.which
        orig_run = subprocess.run
        try:
            shutil.which = lambda name: '/usr/bin/chafa' if name == 'chafa' else None

            def fake_run(cmd, stdout, stderr, text, timeout, check):
                return SimpleNamespace(returncode=0, stdout='ARTLINE1\nARTLINE2')

            subprocess.run = fake_run
            fake_img = os.path.join(self.base, 'pic.png')
            with open(fake_img, 'wb'):
                pass
            lines = self.win._read_image_preview(fake_img, max_lines=5, max_cols=20)
            self.assertIn('ARTLINE1', lines[0])
        finally:
            shutil.which = orig_which
            subprocess.run = orig_run

    def test_entry_preview_lines_dir_and_file_and_cache(self):
        # directory preview
        entry_dir = FileEntry('emptydir', True, os.path.join(self.base, 'emptydir'))
        lines = self.win._entry_preview_lines(entry_dir, max_lines=5, max_cols=20)
        self.assertEqual(lines, ['[empty directory]'])

        # file preview uses _read_text_preview
        entry_file = FileEntry('text.txt', False, os.path.join(self.base, 'text.txt'))
        first = self.win._entry_preview_lines(entry_file, max_lines=5, max_cols=20)
        self.assertTrue(len(first) >= 1)

        # cache behavior: calling again should return the same cached lines
        second = self.win._entry_preview_lines(entry_file, max_lines=5, max_cols=20)
        self.assertEqual(first, second)

        # invalidate cache and change file content then verify different output
        self.win._invalidate_preview_cache()
        with open(entry_file.full_path, 'w', encoding='utf-8') as f:
            f.write('new')
        third = self.win._entry_preview_lines(entry_file, max_lines=5, max_cols=20)
        self.assertNotEqual(second, third)

    def test_resolve_destination_path_errors(self):
        # create source file and attempt to resolve to same path
        src = os.path.join(self.base, 'text.txt')
        entry = FileEntry('text.txt', False, src)
        target, error = self.win._resolve_destination_path(entry, src)
        self.assertIsNone(target)
        self.assertIsInstance(error, ActionResult)
        self.assertEqual(error.type, ActionType.ERROR)

        # non-existing parent dir
        target, error = self.win._resolve_destination_path(entry, os.path.join(self.base, 'nope', 'out.txt'))
        self.assertIsNone(target)
        self.assertIsInstance(error, ActionResult)

    def test_copy_move_selected_destination_exists(self):
        # select existing file and attempt copy to an existing destination
        # select first regular file
        for i, e in enumerate(self.win.entries):
            if not e.is_dir and e.name != '..':
                self.win.selected_index = i
                break
        # destination is same directory and same name -> exists
        dest = os.path.join(self.base, 'text.txt')
        res = self.win.copy_selected(dest)
        self.assertIsInstance(res, ActionResult)
        self.assertEqual(res.type, ActionType.ERROR)

    def test_next_trash_path_collision(self):
        # use a controlled trash dir inside tmp
        trash_dir = os.path.join(self.base, 'trash')
        os.makedirs(trash_dir, exist_ok=True)
        # monkeypatch the instance method
        self.win._trash_base_dir = lambda: trash_dir
        orig = os.path.exists
        try:
            # create base name and first alt existing
            open(os.path.join(trash_dir, 'text.txt'), 'w', encoding='utf-8').close()
            open(os.path.join(trash_dir, 'text.txt.1'), 'w', encoding='utf-8').close()
            nxt = self.win._next_trash_path(os.path.join(self.base, 'text.txt'))
            self.assertTrue(nxt.endswith('text.txt.2'))
        finally:
            os.path.exists = orig

    def test_pending_drag_flow(self):
        # pick a regular file
        for i, e in enumerate(self.win.entries):
            if not e.is_dir and e.name != '..':
                entry = e
                break
        payload = self.win._drag_payload_for_entry(entry)
        self.assertIsNotNone(payload)
        self.win._set_pending_drag(payload, 5, 5)
        self.assertIsNotNone(self.win._pending_drag_payload)
        # simulate mouse move with REPORT_MOUSE_POSITION and BUTTON1_PRESSED
        bstate = curses.BUTTON1_PRESSED | getattr(curses, 'REPORT_MOUSE_POSITION', 0)
        consumed = self.win.consume_pending_drag(6, 6, bstate)
        self.assertEqual(consumed, payload)


if __name__ == '__main__':
    unittest.main()

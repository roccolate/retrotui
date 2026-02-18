import os
import tempfile
import shutil
import subprocess
import types
import sys
import unittest
from tests._support import make_fake_curses

# ensure complete fake curses API used across the test-suite
sys.modules['curses'] = make_fake_curses()
fake_curses = sys.modules['curses']

from retrotui.apps.filemanager import FileManagerWindow, FileEntry


class FileManagerRemainingTests(unittest.TestCase):
    def setUp(self):
        # create repo-local temp dir
        self.tmpdir = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.addCleanup(self.tmpdir.cleanup)
        self.base = self.tmpdir.name
        # create a file and directory
        with open(os.path.join(self.base, 'a.txt'), 'w', encoding='utf-8') as f:
            f.write('hello\nworld')
        os.mkdir(os.path.join(self.base, 'sub'))
        self.win = FileManagerWindow(0, 0, 80, 24, start_path=self.base)

    def test_read_text_preview_text_and_binary(self):
        txt = os.path.join(self.base, 'a.txt')
        lines = self.win._read_text_preview(txt, max_lines=5)
        self.assertIn('hello', ''.join(lines))

        # binary file
        binf = os.path.join(self.base, 'bin.dat')
        with open(binf, 'wb') as f:
            f.write(b"\x00\x01\x02")
        self.assertEqual(self.win._read_text_preview(binf, 3), ['[binary file]'])

    def test_read_image_preview_backends_and_errors(self):
        img = os.path.join(self.base, 'img.png')
        with open(img, 'wb') as f:
            f.write(b'FAKE')

        # no backend available
        orig_which = shutil.which
        shutil.which = lambda name: None
        try:
            res = self.win._read_image_preview(img, max_lines=3, max_cols=10)
            self.assertTrue(any('image preview unavailable' in s for s in res))
        finally:
            shutil.which = orig_which

        # backend present but subprocess fails
        def fake_which(name):
            return '/usr/bin/chafa'

        orig_run = subprocess.run
        # reset cached backend and enable fake which
        self.win._image_preview_backend = None
        shutil.which = fake_which
        def fake_run(*args, **kwargs):
            raise OSError('boom')
        subprocess.run = fake_run
        try:
            res = self.win._read_image_preview(img, max_lines=2, max_cols=10)
            self.assertTrue(any('image preview failed' in s for s in res))
        finally:
            subprocess.run = orig_run
            shutil.which = orig_which

        # backend present and returns output
        # reset cached backend and enable fake which
        self.win._image_preview_backend = None
        shutil.which = fake_which
        class C:
            def __init__(self):
                self.returncode = 0
                self.stdout = 'LINE1\nLINE2\n'
        subprocess.run = lambda *a, **k: C()
        try:
            res = self.win._read_image_preview(img, max_lines=5, max_cols=10)
            self.assertEqual(res[:2], ['LINE1', 'LINE2'])
        finally:
            subprocess.run = orig_run
            shutil.which = orig_which

    def test_preview_cache_and_invalidation(self):
        entry = FileEntry('a.txt', False, os.path.join(self.base, 'a.txt'), size=5)
        # first read populates cache
        lines1 = self.win._entry_preview_lines(entry, max_lines=3, max_cols=20)
        key1 = self.win._preview_cache['key']
        # second read should use cache and return same lines
        lines2 = self.win._entry_preview_lines(entry, max_lines=3, max_cols=20)
        self.assertEqual(lines1, lines2)
        self.assertEqual(key1, self.win._preview_cache['key'])
        # touch file to change mtime and invalidate
        os.utime(entry.full_path, None)
        self.win._invalidate_preview_cache()
        _ = self.win._entry_preview_lines(entry, max_lines=3, max_cols=20)
        self.assertIsNotNone(self.win._preview_cache['key'])

    def test_resolve_destination_path_errors(self):
        entry = FileEntry('a.txt', False, os.path.join(self.base, 'a.txt'), size=5)
        # empty destination
        tgt, err = self.win._resolve_destination_path(entry, '')
        self.assertIsNotNone(err)

        # same as source
        tgt, err = self.win._resolve_destination_path(entry, entry.full_path)
        self.assertIsNotNone(err)

        # parent not exist
        tgt, err = self.win._resolve_destination_path(entry, os.path.join(self.base, 'no', 'f'))
        self.assertIsNotNone(err)

        # destination exists
        dup = os.path.join(self.base, 'dup.txt')
        with open(dup, 'w', encoding='utf-8') as f:
            f.write('x')
        tgt, err = self.win._resolve_destination_path(entry, dup)
        self.assertIsNotNone(err)

        # copy dir into itself
        d = os.path.join(self.base, 'sub')
        entry_dir = FileEntry('sub', True, d)
        tgt, err = self.win._resolve_destination_path(entry_dir, os.path.join(d, 'nested'))
        # parent missing -> error
        self.assertIsNotNone(err)


if __name__ == '__main__':
    unittest.main()

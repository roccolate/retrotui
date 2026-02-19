import os
import sys
import tempfile
import shutil
import unittest
from unittest import mock

from _support import make_fake_curses

# ensure a consistent fake curses implementation
_prev = sys.modules.get('curses')
sys.modules['curses'] = make_fake_curses()

from retrotui.apps import filemanager as fm
from retrotui.core.actions import ActionType


class FakeStdScr:
    def __init__(self):
        self.calls = []
        self.stdscr = self

    def getmaxyx(self):
        return (24, 80)

    def addnstr(self, y, x, text, max_len, attr=None):
        self.calls.append((y, x, text[:max_len], attr))

    def addstr(self, y, x, text, attr=None):
        # fallback
        self.addnstr(y, x, text, len(text), attr)


class FileManagerDrawOpsTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.win = fm.FileManagerWindow(0, 0, 80, 10, start_path=self.td)

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_draw_pane_contents_and_draw_single(self):
        std = FakeStdScr()
        content = [' header', '  [D] ..', '  [F] a.txt']
        # patch safe_addstr to call std.addstr
        with mock.patch('retrotui.apps.filemanager.safe_addstr') as fake_sa:
            def call_safe(stdscr, y, x, text, attr):
                std.addstr(y, x, text, attr)

            fake_sa.side_effect = call_safe
            # draw pane contents with selected index 2
            self.win._draw_pane_contents(std, 0, 0, 3, 20, 10, content, 0, 2, '')
            # ensure selected line was drawn
            self.assertTrue(any('a.txt' in c[2] for c in std.calls))

    def test_draw_with_preview_lines_and_menu(self):
        std = FakeStdScr()
        # ensure there is a file to preview
        path = os.path.join(self.td, 'p.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('one\n')
        self.win._rebuild_content()
        with mock.patch('retrotui.apps.filemanager.safe_addstr') as fake_sa:
            fake_sa.side_effect = lambda s, y, x, t, a=None: std.addstr(y, x, t, a)
            # call draw which will internally call preview lines
            self.win.draw(std)
            # summary and preview lines should be present
            self.assertTrue(len(std.calls) > 0)

    def test_read_image_preview_failure_and_success(self):
        img = os.path.join(self.td, 'img.png')
        with open(img, 'wb') as f:
            f.write(b'PNG')
        # backend not present
        with mock.patch('shutil.which', return_value=''):
            lines = self.win._read_image_preview(img, 2, 10)
            self.assertTrue('image preview unavailable' in lines[0])

        # backend present but subprocess fails
        fake = mock.Mock()
        fake.returncode = 1
        fake.stdout = ''
        self.win._image_preview_backend = None
        with mock.patch('shutil.which', return_value='chafa'):
            with mock.patch('subprocess.run', return_value=fake):
                lines2 = self.win._read_image_preview(img, 2, 10)
                self.assertTrue('image preview failed' in lines2[0])

        # backend success
        fake_ok = mock.Mock()
        fake_ok.returncode = 0
        fake_ok.stdout = 'L1\nL2\n'
        self.win._image_preview_backend = None
        with mock.patch('shutil.which', return_value='chafa'):
            with mock.patch('subprocess.run', return_value=fake_ok):
                lines3 = self.win._read_image_preview(img, 2, 10)
                self.assertEqual(lines3[0], 'L1')

    def test_dual_copy_move_move_flow(self):
        # enable dual pane and create file
        self.win.w = 120
        self.win.dual_pane_enabled = True
        self.win.active_pane = 0
        # left file
        src = os.path.join(self.td, 'leftfile.txt')
        with open(src, 'w') as f:
            f.write('x')
        self.win._rebuild_content()
        self.win._select_entry_by_name('leftfile.txt')
        # prepare secondary dir
        sec = os.path.join(self.td, 'sec')
        os.mkdir(sec)
        self.win.secondary_path = sec
        self.win._rebuild_secondary_content()
        # perform move
        res = self.win._dual_copy_move_between_panes(move=True)
        # should succeed
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertTrue(os.path.exists(os.path.join(sec, 'leftfile.txt')))

    def test_delete_selected_oserror(self):
        # create file and make shutil.move raise
        src = os.path.join(self.td, 'todel.txt')
        with open(src, 'w') as f:
            f.write('x')
        self.win._rebuild_content()
        self.win._select_entry_by_name('todel.txt')
        with mock.patch('shutil.move', side_effect=OSError('disk')):
            out = self.win.delete_selected()
            self.assertIsNotNone(out)


if __name__ == '__main__':
    unittest.main()

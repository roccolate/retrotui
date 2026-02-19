import os
import sys
import tempfile
import shutil
import types
import unittest
from _support import make_fake_curses

sys.modules['curses'] = make_fake_curses()
fake_curses = sys.modules['curses']

from retrotui.apps.filemanager import (
    FileManagerWindow,
    FileEntry,
    _cell_width,
    _fit_text_to_cells,
)
from retrotui.core.actions import ActionType


class FakeStdScr:
    def __init__(self):
        self.calls = []
        self.stdscr = self

    def addnstr(self, y, x, text, max_len, attr=0):
        self.calls.append((y, x, text[:max_len], attr))

    def getmaxyx(self):
        return (24, 80)


class FileManagerAdditionalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.addCleanup(self.tmp.cleanup)
        self.base = self.tmp.name
        with open(os.path.join(self.base, 'one.txt'), 'w', encoding='utf-8') as f:
            f.write('hello')
        os.mkdir(os.path.join(self.base, 'sub'))
        self.win = FileManagerWindow(0, 0, 80, 24, start_path=self.base)

    def test_cell_width_and_fit_text(self):
        self.assertEqual(_cell_width('a'), 1)
        self.assertEqual(_cell_width(''), 0)
        # East Asian wide char
        self.assertEqual(_cell_width('界'), 2)
        s = 'abcd'
        self.assertEqual(_fit_text_to_cells(s, 2), 'ab')
        # padding
        self.assertEqual(len(_fit_text_to_cells('x', 4)), 4)

    def test_fileentry_size_format_units(self):
        e1 = FileEntry('f', False, os.path.join(self.base, 'one.txt'), size=500)
        self.assertIn('B', e1.display_text)
        e2 = FileEntry('f', False, os.path.join(self.base, 'one.txt'), size=2048)
        self.assertIn('K', e2.display_text)
        e3 = FileEntry('f', False, os.path.join(self.base, 'one.txt'), size=2_000_000)
        self.assertIn('M', e3.display_text)

    def test_toggle_dual_pane_unavailable(self):
        # force narrow width
        self.win.w = 10
        res = self.win.toggle_dual_pane()
        self.assertIsNotNone(res)
        self.assertEqual(res.type, ActionType.ERROR)

    def test_draw_pane_contents_selection(self):
        std = FakeStdScr()
        content = ['a', 'b', 'c']
        # selection index within visible rows
        self.win._draw_pane_contents(std, 0, 0, 0, 10, 5, content, 0, 1, 0, True)
        self.assertTrue(any(call[0] == 1 for call in std.calls))

    def test_set_and_navigate_bookmark(self):
        # invalid slot
        res = self.win.set_bookmark(9)
        self.assertIsNotNone(res)
        # non-directory bookmark
        fake_file = os.path.join(self.base, 'one.txt')
        res = self.win.set_bookmark(1, path=fake_file)
        self.assertIsNotNone(res)
        # valid bookmark and navigate
        res = self.win.set_bookmark(1, path=self.base)
        self.assertEqual(res.type, ActionType.REFRESH)
        res = self.win.navigate_bookmark(1)
        self.assertEqual(res.type, ActionType.REFRESH)

    def test_delete_selected_handles_oserror(self):
        # pick an entry and monkeypatch shutil.move to raise
        for i, e in enumerate(self.win.entries):
            if not e.is_dir and e.name != '..':
                self.win.selected_index = i
                break
        orig = shutil.move
        try:
            shutil.move = lambda a, b: (_ for _ in ()).throw(OSError('nope'))
            res = self.win.delete_selected()
            self.assertIsNotNone(res)
            self.assertEqual(res.type, ActionType.ERROR)
        finally:
            shutil.move = orig

    def test_toggle_hidden_rebuilds(self):
        before = len(self.win.entries)
        self.win.toggle_hidden()
        self.assertIsNotNone(self.win.entries)

    def test_handle_key_dual_calls_dual_copy_move(self):
        called = {'copy': False, 'move': False}
        def fake_dual(move=False):
            called['move' if move else 'copy'] = True
            return None
        self.win.dual_pane_enabled = True
        self.win._dual_copy_move_between_panes = fake_dual
        import curses
        # F5 copy
        self.win.handle_key(curses.KEY_F5)
        # F4 move
        self.win.handle_key(curses.KEY_F4)
        self.assertTrue(called['copy'])
        self.assertTrue(called['move'])


if __name__ == '__main__':
    unittest.main()

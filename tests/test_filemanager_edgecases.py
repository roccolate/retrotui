import os
import tempfile
import shutil
import sys
import types
import unittest
from tests._support import make_fake_curses

sys.modules['curses'] = make_fake_curses()

from retrotui.apps.filemanager import FileManagerWindow, FileEntry
fake_curses = sys.modules['curses']


class FileManagerEdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.addCleanup(self.tmp.cleanup)
        self.base = self.tmp.name
        # files and dirs
        with open(os.path.join(self.base, 'old.txt'), 'w', encoding='utf-8') as f:
            f.write('x')
        with open(os.path.join(self.base, 'todel.txt'), 'w', encoding='utf-8') as f:
            f.write('y')
        os.mkdir(os.path.join(self.base, 'dir'))
        self.win = FileManagerWindow(0, 0, 80, 24, start_path=self.base)

    def _select_by_name(self, name):
        for i, e in enumerate(self.win.entries):
            if e.name == name:
                self.win.selected_index = i
                return True
        return False

    def test_drag_payload_and_consume_variants(self):
        file_entry = next(e for e in self.win.entries if not e.is_dir and e.name != '..')
        dir_entry = next(e for e in self.win.entries if e.is_dir and e.name != '..')

        self.assertIsNone(self.win._drag_payload_for_entry(FileEntry('..', True, self.base)))
        self.assertIsNone(self.win._drag_payload_for_entry(dir_entry))
        payload = self.win._drag_payload_for_entry(file_entry)
        self.assertIsNotNone(payload)

        # set pending and call consume with missing BUTTON1_PRESSED -> clears
        self.win._set_pending_drag(payload, 1, 1)
        res = self.win.consume_pending_drag(1, 1, 0)
        self.assertIsNone(res)
        self.assertIsNone(self.win._pending_drag_payload)

        # set pending again, BUTTON1_PRESSED but missing REPORT_MOUSE_POSITION -> still pending
        self.win._set_pending_drag(payload, 2, 2)
        bstate = fake_curses.BUTTON1_PRESSED
        res = self.win.consume_pending_drag(2, 2, bstate)
        self.assertIsNone(res)
        self.assertIsNotNone(self.win._pending_drag_payload)

        # now provide both and moved coords -> should return payload
        bstate = fake_curses.BUTTON1_PRESSED | fake_curses.REPORT_MOUSE_POSITION
        res = self.win.consume_pending_drag(3, 3, bstate)
        self.assertEqual(res, payload)
        self.assertIsNone(self.win._pending_drag_payload)

    def test_next_trash_path_collisions_and_undo_delete(self):
        # ensure trash base inside tmp
        self.win._trash_base_dir = staticmethod(lambda: os.path.join(self.base, 'trash'))
        os.makedirs(self.win._trash_base_dir(), exist_ok=True)
        src = os.path.join(self.base, 'todel.txt')
        # create candidate collision
        candidate = os.path.join(self.win._trash_base_dir(), 'todel.txt')
        with open(candidate, 'w', encoding='utf-8') as f:
            f.write('z')
        alt = self.win._next_trash_path(src)
        self.assertNotEqual(alt, candidate)

        # delete_selected should move file into trash and set last move
        self._select_by_name('todel.txt')
        res = self.win.delete_selected()
        self.assertIsNone(res)
        self.assertIsNotNone(self.win._last_trash_move)
        trash_path = self.win._last_trash_move['trash']
        self.assertTrue(os.path.exists(trash_path))

        # undo should restore
        res = self.win.undo_last_delete()
        self.assertIsNone(res)
        self.assertTrue(os.path.exists(os.path.join(self.base, 'todel.txt')))

    def test_rename_selected_errors_and_success(self):
        self._select_by_name('old.txt')
        # invalid name
        res = self.win.rename_selected('')
        self.assertIsNotNone(res)
        res = self.win.rename_selected('bad/name')
        self.assertIsNotNone(res)

        # success
        res = self.win.rename_selected('new.txt')
        self.assertIsNone(res)
        self.assertTrue(os.path.exists(os.path.join(self.base, 'new.txt')))


if __name__ == '__main__':
    unittest.main()

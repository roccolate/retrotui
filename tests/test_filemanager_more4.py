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


class FileManagerMore4Tests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.orig_trash = fm.FileManagerWindow._trash_base_dir
        fm.FileManagerWindow._trash_base_dir = staticmethod(lambda: os.path.join(self.td, 'trash'))
        self.win = fm.FileManagerWindow(0, 0, 100, 24, start_path=self.td)

    def tearDown(self):
        fm.FileManagerWindow._trash_base_dir = self.orig_trash
        shutil.rmtree(self.td, ignore_errors=True)

    def test_build_listing_permission_error(self):
        with mock.patch('os.listdir', side_effect=PermissionError('denied')):
            self.win.current_path = '/noaccess'
            self.win._rebuild_content()
            self.assertIsNotNone(self.win.error_message)
            # content header + separator + error line -> index 2 or 3 may vary
            self.assertTrue(any('Permission denied' in s for s in self.win.content))

    def test_toggle_hidden_rebuilds(self):
        # create hidden file
        open(os.path.join(self.td, '.hidden'), 'w').close()
        self.win._rebuild_content()
        hidden_visible = any(e.name == '.hidden' for e in self.win.entries)
        self.assertFalse(hidden_visible)
        self.win.toggle_hidden()
        self.win._rebuild_content()
        self.assertTrue(any(e.name == '.hidden' for e in self.win.entries))

    def test_navigate_parent_selects_old_dir(self):
        subdir = os.path.join(self.td, 'sub')
        os.mkdir(subdir)
        self.win.navigate_to(subdir)
        self.win.navigate_parent()
        self.assertEqual(self.win.current_path, self.td)
        self.assertTrue(self.win._select_entry_by_name('sub'))

    def test_bookmark_set_and_navigate(self):
        self.win.set_bookmark(1)
        self.assertIn(1, self.win.bookmarks)
        self.assertEqual(self.win.bookmarks[1], os.path.realpath(self.td))
        # navigate to bookmark
        res = self.win.navigate_bookmark(1)
        self.assertIsNone(res)

    def test_dual_copy_move_between_panes(self):
        self.win.w = 120  # enable dual
        self.win.dual_pane_enabled = True
        self.win.active_pane = 0
        # create file in left
        self.win.create_file('left.txt')
        # switch to right, create dir
        self.win.active_pane = 1
        self.win.secondary_path = os.path.join(self.td, 'rightdir')
        os.makedirs(self.win.secondary_path, exist_ok=True)
        self.win._rebuild_secondary_content()
        # copy from left to right
        self.win.active_pane = 0
        self.win._select_entry_by_name('left.txt')
        res_copy = self.win._dual_copy_move_between_panes(move=False)
        self.assertIsNone(res_copy)
        self.assertTrue(os.path.exists(os.path.join(self.win.secondary_path, 'left.txt')))

    def test_handle_key_fkeys_and_tab(self):
        # When dual-pane disabled, F5 requests copy entry
        self.win.dual_pane_enabled = False
        fake_f5 = 300
        self.win.KEY_F5 = fake_f5
        act = self.win.handle_key(fake_f5)
        self.assertEqual(act.type, ActionType.REQUEST_COPY_ENTRY)
        # Tab switches pane in dual
        self.win.dual_pane_enabled = True
        self.win.active_pane = 0
        res_tab = self.win.handle_tab_key()
        self.assertTrue(res_tab)
        self.assertEqual(self.win.active_pane, 1)
        # H toggle hidden
        prev = self.win.show_hidden
        self.win.handle_key(ord('h'))
        self.assertNotEqual(self.win.show_hidden, prev)


if __name__ == '__main__':
    unittest.main()
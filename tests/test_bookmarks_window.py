import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).parent))
from _support import make_fake_curses

sys.modules['curses'] = make_fake_curses()

from retrotui.apps.retronet import BookmarksWindow, RetroNetWindow
from retrotui.core.actions import ActionResult, ActionType, AppAction
from retrotui.core import bookmarks as bookmarks_core


def _make_windows():
    with mock.patch('retrotui.apps.retronet.theme_attr', return_value=0):
        with mock.patch('retrotui.apps.retronet.threading.Thread'):
            src = RetroNetWindow(0, 0, 80, 24)
            bm_win = BookmarksWindow(2, 2, 60, 18, source_win=src)
    return src, bm_win


class BookmarksWindowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = mock.patch.object(bookmarks_core, 'default_bookmarks_path',
                                        return_value=Path(self._tmp.name) / "bookmarks.toml")
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_empty_state_lists_zero(self):
        _, bm_win = _make_windows()
        self.assertEqual(bm_win.bookmarks, [])
        self.assertEqual(bm_win.selected_idx, 0)

    def test_loads_existing_bookmarks(self):
        bookmarks_core.add_bookmark("A", "http://a.com")
        bookmarks_core.add_bookmark("B", "http://b.com")
        _, bm_win = _make_windows()
        self.assertEqual([b.title for b in bm_win.bookmarks], ["A", "B"])

    def test_navigation_keys(self):
        bookmarks_core.add_bookmark("A", "http://a.com")
        bookmarks_core.add_bookmark("B", "http://b.com")
        bookmarks_core.add_bookmark("C", "http://c.com")
        _, bm_win = _make_windows()
        self.assertEqual(bm_win.selected_idx, 0)
        bm_win.handle_key(ord('j'))
        self.assertEqual(bm_win.selected_idx, 1)
        bm_win.handle_key(ord('k'))
        self.assertEqual(bm_win.selected_idx, 0)
        bm_win.handle_key(curses_mock.KEY_END)
        self.assertEqual(bm_win.selected_idx, 2)
        bm_win.handle_key(curses_mock.KEY_HOME)
        self.assertEqual(bm_win.selected_idx, 0)

    def test_activate_navigates_source_and_closes(self):
        bookmarks_core.add_bookmark("NPR", "http://text.npr.org")
        src, bm_win = _make_windows()
        with mock.patch.object(src, '_load_url') as mock_load:
            res = bm_win.handle_key(10)  # Enter
        mock_load.assert_called_once_with("http://text.npr.org")
        self.assertEqual(res.type, ActionType.EXECUTE)
        self.assertEqual(res.payload, AppAction.CLOSE_WINDOW)

    def test_delete_removes_bookmark(self):
        bookmarks_core.add_bookmark("A", "http://a.com")
        bookmarks_core.add_bookmark("B", "http://b.com")
        _, bm_win = _make_windows()
        bm_win.selected_idx = 0
        bm_win.handle_key(ord('d'))
        titles = [b.title for b in bookmarks_core.load_bookmarks()]
        self.assertEqual(titles, ["B"])

    def test_esc_closes_window(self):
        _, bm_win = _make_windows()
        res = bm_win.handle_key(27)  # Esc
        self.assertEqual(res.type, ActionType.EXECUTE)
        self.assertEqual(res.payload, AppAction.CLOSE_WINDOW)

    def test_empty_list_activate_is_noop(self):
        _, bm_win = _make_windows()
        res = bm_win.handle_key(10)
        self.assertEqual(res.type, ActionType.REFRESH)


import curses as curses_mock  # imported at module scope so handle_key constants resolve


if __name__ == "__main__":
    unittest.main()

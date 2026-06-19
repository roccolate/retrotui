import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).parent))
from _support import make_fake_curses

sys.modules['curses'] = make_fake_curses()

from retrotui.core.bookmarks import (
    Bookmark,
    add_bookmark,
    default_bookmarks_path,
    load_bookmarks,
    remove_bookmark,
    save_bookmarks,
)


class BookmarksCoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "bookmarks.toml"

    def tearDown(self):
        self._tmp.cleanup()

    def test_load_missing_returns_empty(self):
        self.assertEqual(load_bookmarks(self.path), [])

    def test_save_and_load_roundtrip(self):
        save_bookmarks(
            [
                Bookmark(title="NPR", url="http://text.npr.org"),
                Bookmark(title="DuckDuckGo", url="https://duckduckgo.com/html/"),
            ],
            self.path,
        )
        loaded = load_bookmarks(self.path)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].title, "NPR")
        self.assertEqual(loaded[0].url, "http://text.npr.org")
        self.assertEqual(loaded[1].title, "DuckDuckGo")

    def test_add_new(self):
        add_bookmark("A", "http://a.com", self.path)
        self.assertEqual(load_bookmarks(self.path), [Bookmark("A", "http://a.com")])

    def test_add_replaces_same_title(self):
        add_bookmark("A", "http://a.com", self.path)
        add_bookmark("A", "http://a-updated.com", self.path)
        loaded = load_bookmarks(self.path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].url, "http://a-updated.com")

    def test_add_blank_url_is_skipped(self):
        add_bookmark("A", "   ", self.path)
        self.assertEqual(load_bookmarks(self.path), [])

    def test_remove(self):
        add_bookmark("A", "http://a.com", self.path)
        add_bookmark("B", "http://b.com", self.path)
        remove_bookmark("A", self.path)
        self.assertEqual(load_bookmarks(self.path), [Bookmark("B", "http://b.com")])

    def test_remove_missing_is_noop(self):
        add_bookmark("A", "http://a.com", self.path)
        remove_bookmark("nonexistent", self.path)
        self.assertEqual(len(load_bookmarks(self.path)), 1)

    def test_title_with_spaces_roundtrip(self):
        add_bookmark("My Site", "http://mine.com", self.path)
        loaded = load_bookmarks(self.path)
        self.assertEqual(loaded[0].title, "My Site")
        self.assertEqual(loaded[0].url, "http://mine.com")

    def test_escaped_title_and_url_roundtrip(self):
        save_bookmarks(
            [
                Bookmark(
                    title='Line "One"\nTwo',
                    url="https://example.com/#frag\nnext",
                )
            ],
            self.path,
        )

        loaded = load_bookmarks(self.path)

        self.assertEqual(loaded, [Bookmark('Line "One"\nTwo', "https://example.com/#frag\nnext")])

    def test_default_path_under_retrotui_config(self):
        p = default_bookmarks_path()
        self.assertEqual(p.parent.name, "retrotui")
        self.assertEqual(p.name, "bookmarks.toml")


if __name__ == "__main__":
    unittest.main()

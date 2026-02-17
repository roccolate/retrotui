"""More LogViewer tests covering search navigation and selection mapping."""

from __future__ import annotations

import importlib
import os
import sys
import unittest
from unittest import mock

from _support import make_fake_curses, make_repo_tmpdir


class LogViewerMoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = make_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.theme",
            "retrotui.utils",
            "retrotui.ui.dialog",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.actions",
            "retrotui.apps.logviewer",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.log_mod = importlib.import_module("retrotui.apps.logviewer")
        cls.LogViewerWindow = cls.log_mod.LogViewerWindow
        cls.ActionType = cls.actions_mod.ActionType

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.logviewer",
            "retrotui.core.actions",
            "retrotui.ui.window",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
            "retrotui.utils",
            "retrotui.theme",
            "retrotui.constants",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def setUp(self):
        self.win = self.LogViewerWindow(0, 0, 80, 20)

    def test_rebuild_search_matches_and_navigation(self):
        self.win.lines = ["First line", "Second ERROR line", "Third info", "Another error"]
        self.win.search_query = "error"
        self.win._rebuild_search_matches()
        self.assertEqual(self.win.search_matches, [1, 3])
        self.assertEqual(self.win.search_index, 0)

        # next wraps around
        self.win._jump_search_match(1)
        self.assertEqual(self.win.search_index, 1)
        self.win._jump_search_match(1)
        self.assertEqual(self.win.search_index, 0)

        # prev wraps backwards
        self.win._jump_search_match(-1)
        self.assertEqual(self.win.search_index, 1)

    def test_selection_bounds_and_line_span(self):
        self.win.lines = ["012345", "abcdef", "ghijkl"]

        self.win.selection_anchor = (0, 1)
        self.win.selection_cursor = (0, 4)
        self.assertEqual(self.win._line_selection_span(0, 6), (1, 4))

        self.win.selection_anchor = (0, 4)
        self.win.selection_cursor = (2, 2)
        self.assertEqual(self.win._line_selection_span(0, 6), (4, 6))
        self.assertEqual(self.win._line_selection_span(1, 6), (0, 6))
        self.assertEqual(self.win._line_selection_span(2, 6), (0, 2))

    def test_cursor_from_screen_maps_correctly(self):
        self.win.lines = ["one", "two", "three", "four"]
        self.win.scroll_offset = 1

        with mock.patch.object(self.win, "body_rect", return_value=(5, 2, 10, 6)):
            result = self.win._cursor_from_screen(6, 3)

        self.assertEqual(result, (1, 1))

    def test_ensure_log_colors_no_callable_init(self):
        # Remove init_pair to simulate environment without color support.
        lv = importlib.import_module("retrotui.apps.logviewer")
        had = hasattr(lv.curses, "init_pair")
        orig = getattr(lv.curses, "init_pair", None)
        try:
            lv.curses.init_pair = None
            self.LogViewerWindow._log_colors_ready = False
            self.LogViewerWindow._ensure_log_colors()
            self.assertTrue(self.LogViewerWindow._log_colors_ready)
        finally:
            if had:
                lv.curses.init_pair = orig
            else:
                try:
                    delattr(lv.curses, "init_pair")
                except Exception:
                    pass

    def test_open_path_error_and_success(self):
        res = self.win.open_path("/no/such/file")
        self.assertEqual(res.type, self.ActionType.ERROR)

        tmpdir = make_repo_tmpdir()
        self.addCleanup(tmpdir.cleanup)
        path = os.path.join(tmpdir.name, "a.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("one\n")

        out = self.win.open_path(path)
        self.assertIsNone(out)
        self.assertEqual(self.win.filepath, os.path.abspath(path))


if __name__ == "__main__":
    unittest.main()


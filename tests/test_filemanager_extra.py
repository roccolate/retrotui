"""Extra FileManager tests.

These tests exercise small helpers and edge-case branches that are easy to miss
in higher-level component tests.
"""

from __future__ import annotations

import importlib
import os
import shutil
import sys
import unittest

from _support import make_fake_curses, make_repo_tmpdir


class FileManagerExtraTests(unittest.TestCase):
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
            "retrotui.apps.filemanager",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.fm_mod = importlib.import_module("retrotui.apps.filemanager")

        cls.ActionType = cls.actions_mod.ActionType
        cls.FileEntry = cls.fm_mod.FileEntry
        cls.FileManagerWindow = cls.fm_mod.FileManagerWindow
        # Prevent function attributes from becoming bound methods when accessed
        # via `self.*` on the testcase instance.
        cls._cell_width = staticmethod(cls.fm_mod._cell_width)
        cls._fit_text_to_cells = staticmethod(cls.fm_mod._fit_text_to_cells)

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.filemanager",
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
        self.tmpdir = make_repo_tmpdir()
        self.addCleanup(self.tmpdir.cleanup)
        self.win = self.FileManagerWindow(0, 0, 80, 20, start_path=self.tmpdir.name)

        # Avoid touching user/system trash outside the workspace.
        self.win._trash_base_dir = lambda: os.path.join(self.tmpdir.name, "_trash")

    def test_cell_width_and_fit_text(self):
        self.assertEqual(self._cell_width("a"), 1)
        self.assertEqual(self._cell_width(""), 0)

        # Combining mark has width 0.
        comb = "\u0301"
        self.assertEqual(self._cell_width(comb), 0)

        out = self._fit_text_to_cells("abc", 2)
        self.assertIsInstance(out, str)
        self.assertTrue(out)

    def test_fileentry_format_size(self):
        entry = self.FileEntry("f.txt", False, os.path.join(self.tmpdir.name, "f.txt"), size=500)
        self.assertIn("B", entry._format_size())

        entry.size = 4096
        self.assertIn("K", entry._format_size())

        entry.size = 2 * 1024 * 1024
        self.assertIn("M", entry._format_size())

    def test_read_text_preview_text_and_binary(self):
        text_path = os.path.join(self.tmpdir.name, "t.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write("line1\nline2\n")

        lines = self.win._read_text_preview(text_path, max_lines=5)
        self.assertTrue(any("line1" in line for line in lines))

        bin_path = os.path.join(self.tmpdir.name, "bin.dat")
        with open(bin_path, "wb") as f:
            f.write(b"\x00\x01\x02")

        bin_lines = self.win._read_text_preview(bin_path, max_lines=5)
        self.assertEqual(bin_lines, ["[binary file]"])

    def test_entry_preview_lines_directory_and_unreadable(self):
        empty_dir = os.path.join(self.tmpdir.name, "empt")
        os.mkdir(empty_dir)

        entry = self.FileEntry("empt", True, empty_dir)
        lines = self.win._entry_preview_lines(entry, max_lines=5)
        self.assertEqual(lines, ["[empty directory]"])

        missing = os.path.join(self.tmpdir.name, "noexist")
        entry2 = self.FileEntry("noexist", True, missing)
        lines2 = self.win._entry_preview_lines(entry2, max_lines=5)
        self.assertEqual(lines2, ["[directory not readable]"])

    def test_next_trash_path_and_undo(self):
        src = os.path.join(self.tmpdir.name, "afile.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("x")

        candidate = self.win._next_trash_path(src)
        self.assertTrue(candidate.startswith(self.win._trash_base_dir()))

        os.makedirs(os.path.dirname(candidate), exist_ok=True)
        shutil.move(src, candidate)
        self.win._last_trash_move = {"source": src, "trash": candidate}

        out = self.win.undo_last_delete()
        self.assertEqual(out.type, self.ActionType.REFRESH)
        self.assertTrue(os.path.exists(src))
        self.assertFalse(os.path.exists(candidate))

    def test_bookmarks_invalid(self):
        res = self.win.set_bookmark(9)
        self.assertEqual(res.type, self.ActionType.ERROR)

        res2 = self.win.navigate_bookmark(99)
        self.assertEqual(res2.type, self.ActionType.ERROR)

    def test_normalize_and_create(self):
        name, err = self.win._normalize_new_name("")
        self.assertIsNone(name)
        self.assertEqual(err.type, self.ActionType.ERROR)

        out = self.win.create_directory("newdir")
        self.assertEqual(out.type, self.ActionType.REFRESH)
        self.assertTrue(os.path.isdir(os.path.join(self.tmpdir.name, "newdir")))

        out2 = self.win.create_file("newfile.txt")
        self.assertEqual(out2.type, self.ActionType.REFRESH)
        self.assertTrue(os.path.isfile(os.path.join(self.tmpdir.name, "newfile.txt")))

    def test_copy_move_rename_delete_errors_without_selection(self):
        self.win.entries = []
        self.win.selected_index = 0

        res = self.win.copy_selected("/nonexistent")
        self.assertEqual(res.type, self.ActionType.ERROR)

        res2 = self.win.move_selected("/nonexistent")
        self.assertEqual(res2.type, self.ActionType.ERROR)

        res3 = self.win.rename_selected("x")
        self.assertEqual(res3.type, self.ActionType.ERROR)

        res4 = self.win.delete_selected()
        self.assertEqual(res4.type, self.ActionType.ERROR)


if __name__ == "__main__":
    unittest.main()

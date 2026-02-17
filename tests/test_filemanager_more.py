"""More FileManager tests covering additional branches."""

from __future__ import annotations

import importlib
import os
import sys
import unittest
from unittest import mock

from _support import make_fake_curses, make_repo_tmpdir


class FileManagerMoreTests(unittest.TestCase):
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
        cls.curses = sys.modules["curses"]

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
        self.win = self.FileManagerWindow(0, 0, 100, 20, start_path=self.tmpdir.name)

        # Keep trash operations inside the workspace.
        self.win._trash_base_dir = lambda: os.path.join(self.tmpdir.name, "_trash")

    def test_dual_pane_toggle_and_min_width(self):
        # Start with width >= 92 -> dual pane enabled.
        self.assertTrue(self.win.dual_pane_enabled)

        # Toggle off.
        self.assertIsNone(self.win.toggle_dual_pane())
        self.assertFalse(self.win.dual_pane_enabled)

        # Small width cannot enable.
        self.win.w = 80
        res = self.win.toggle_dual_pane()
        self.assertEqual(res.type, self.ActionType.ERROR)

    def test_drag_payload_and_consume(self):
        fpath = os.path.join(self.tmpdir.name, "a.txt")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("x")

        file_entry = self.FileEntry("a.txt", False, fpath)
        dir_entry = self.FileEntry("d", True, self.tmpdir.name)
        parent_entry = self.FileEntry("..", True, os.path.dirname(self.tmpdir.name))

        self.assertIsNotNone(self.win._drag_payload_for_entry(file_entry))
        self.assertIsNone(self.win._drag_payload_for_entry(dir_entry))
        self.assertIsNone(self.win._drag_payload_for_entry(parent_entry))

        payload = {"type": "file_path", "path": fpath, "name": "a.txt"}
        self.win._set_pending_drag(payload, 1, 1)

        bstate = self.curses.BUTTON1_PRESSED | self.curses.REPORT_MOUSE_POSITION
        out = self.win.consume_pending_drag(2, 2, bstate=bstate)
        self.assertEqual(out, payload)

    def test_panel_layout_and_preview_key(self):
        list_w, sep_x, preview_x, preview_w = self.win._panel_layout()
        self.assertIsInstance(list_w, int)
        self.assertTrue(preview_w >= 0)

        p = os.path.join(self.tmpdir.name, "f.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("hello")

        key = self.win._preview_stat_key(p)
        self.assertEqual(key[0], p)
        self.assertIsInstance(key[1], int)
        self.assertIsInstance(key[2], int)

    def test_entry_info_lines_and_preview_text(self):
        p = os.path.join(self.tmpdir.name, "f1.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("one\n")

        entry = self.FileEntry("f1.txt", False, p, size=10)
        info = self.win._entry_info_lines(entry)
        self.assertTrue(any(line.startswith("Name:") for line in info))

        lines = self.win._entry_preview_lines(entry, max_lines=5, max_cols=40)
        self.assertTrue(any("one" in line for line in lines))

    def test_read_image_preview_backend_and_errors(self):
        # Force backend detection path and simulate subprocess failures.
        with mock.patch.object(self.fm_mod.shutil, "which", return_value="chafa"):
            mock_completed = mock.Mock(returncode=1, stdout="", stderr="")
            with mock.patch.object(self.fm_mod.subprocess, "run", return_value=mock_completed):
                res = self.win._read_image_preview("/nonexistent.png", max_lines=5, max_cols=20)
        self.assertEqual(res, ["[image preview failed via chafa]"])

    def test_next_trash_path_and_resolve_destination(self):
        src = os.path.join(self.tmpdir.name, "to_delete")
        with open(src, "w", encoding="utf-8") as f:
            f.write("x")

        candidate = self.win._next_trash_path(src)
        self.assertTrue(candidate.startswith(self.win._trash_base_dir()))

        entry = self.FileEntry("nofile", False, src)
        tgt, err = self.win._resolve_destination_path(entry, "")
        self.assertIsNone(tgt)
        self.assertEqual(err.type, self.ActionType.ERROR)

    def test_copy_move_selected_success(self):
        fname = "sfile.txt"
        fpath = os.path.join(self.tmpdir.name, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("data")

        self.win._rebuild_content()
        idx = next((i for i, entry in enumerate(self.win.entries) if entry.name == fname), None)
        self.assertIsNotNone(idx)
        self.win.selected_index = idx

        destdir = os.path.join(self.tmpdir.name, "dest")
        os.mkdir(destdir)
        self.assertIsNone(self.win.copy_selected(destdir))
        self.assertTrue(os.path.exists(os.path.join(destdir, fname)))

        dest2 = os.path.join(self.tmpdir.name, "dest2")
        os.mkdir(dest2)
        self.win._rebuild_content()
        idx2 = next((i for i, entry in enumerate(self.win.entries) if entry.name == fname), None)
        self.assertIsNotNone(idx2)
        self.win.selected_index = idx2

        self.assertIsNone(self.win.move_selected(dest2))
        self.assertTrue(os.path.exists(os.path.join(dest2, fname)))


if __name__ == "__main__":
    unittest.main()


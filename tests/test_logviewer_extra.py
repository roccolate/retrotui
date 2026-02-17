"""Extra LogViewer tests for normalization, selection and file tailing."""

from __future__ import annotations

import importlib
import os
import sys
import unittest
from unittest import mock

from _support import make_fake_curses, make_repo_tmpdir


class LogViewerExtraTests(unittest.TestCase):
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
            "retrotui.core.clipboard",
            "retrotui.apps.logviewer",
        ):
            sys.modules.pop(mod_name, None)

        cls.clipboard_mod = importlib.import_module("retrotui.core.clipboard")
        cls.log_mod = importlib.import_module("retrotui.apps.logviewer")
        cls.LogViewerWindow = cls.log_mod.LogViewerWindow
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.logviewer",
            "retrotui.core.clipboard",
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

    def test_normalize_and_severity_attr(self):
        s = "line1\r\nline2\rline3\n"
        self.assertEqual(self.win._normalize_text(s), "line1\nline2\nline3\n")

        base = 0
        expected_err = self.curses.color_pair(self.win.COLOR_ERROR_PAIR) | self.curses.A_BOLD
        expected_warn = self.curses.color_pair(self.win.COLOR_WARN_PAIR) | self.curses.A_BOLD
        expected_info = self.curses.color_pair(self.win.COLOR_INFO_PAIR) | self.curses.A_BOLD

        self.assertEqual(self.win._severity_attr("some ERROR occurred", base), expected_err)
        self.assertEqual(self.win._severity_attr("a warn message", base), expected_warn)
        self.assertEqual(self.win._severity_attr("info here", base), expected_info)
        self.assertEqual(self.win._severity_attr("plain", base), base)

    def test_selection_and_copy(self):
        self.win.lines = ["one", "two", "three"]

        self.assertFalse(self.win.has_selection())
        self.win.selection_anchor = (0, 1)
        self.win.selection_cursor = (0, 3)
        self.assertTrue(self.win.has_selection())
        self.assertEqual(self.win._selected_text(), "ne")

        # Multi-line selection returns newline-joined chunks.
        self.win.selection_anchor = (0, 2)
        self.win.selection_cursor = (2, 2)
        text = self.win._selected_text()
        self.assertEqual(text, "e\ntwo\nth")

        # _copy_selection falls back to current visible line when selection is empty.
        self.win.clear_selection()
        self.win.scroll_offset = 1
        with mock.patch.object(self.log_mod, "copy_text") as fake_copy:
            self.win._copy_selection()
            fake_copy.assert_called_once_with("two")

    def test_reload_and_poll_file(self):
        tmpdir = make_repo_tmpdir()
        self.addCleanup(tmpdir.cleanup)

        path = os.path.join(tmpdir.name, "log.txt")
        with open(path, "wb") as f:
            f.write(b"line1\nline2\n")

        out = self.win.open_path(path)
        self.assertIsNone(out)
        self.assertEqual(self.win.filepath, os.path.abspath(path))
        self.assertGreaterEqual(len(self.win.lines), 2)

        # Append lines and force poll.
        with open(path, "a", encoding="utf-8") as f:
            f.write("added1\nadded2\n")
        self.win._poll_for_updates(force=True)
        self.assertTrue(any("added1" in line for line in self.win.lines))

        # Simulate truncation (position beyond file size triggers reload path).
        with open(path, "wb") as f:
            f.write(b"short\n")
        self.win.file_position = 1000
        self.win._poll_for_updates(force=True)
        self.assertGreaterEqual(self.win.file_position, 0)

    def test_init_with_filepath_calls_open_path(self):
        tmpdir = make_repo_tmpdir()
        self.addCleanup(tmpdir.cleanup)
        path = os.path.join(tmpdir.name, "init.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("hello\n")

        with mock.patch.object(self.LogViewerWindow, "open_path", return_value=None) as fake_open:
            self.LogViewerWindow(0, 0, 80, 20, filepath=path)
        fake_open.assert_called_once()

    def test_line_selection_span_none_branches(self):
        # Same-line selection with an empty line length collapses the span.
        self.win.selection_anchor = (0, 0)
        self.win.selection_cursor = (0, 1)
        self.assertIsNone(self.win._line_selection_span(0, 0))

        # Start-line selection where start clamps to line length returns None.
        self.win.selection_anchor = (0, 99)
        self.win.selection_cursor = (1, 0)
        self.assertIsNone(self.win._line_selection_span(0, 3))

        # End-line selection where end clamps to 0 returns None.
        self.win.selection_anchor = (0, 0)
        self.win.selection_cursor = (1, 0)
        self.assertIsNone(self.win._line_selection_span(1, 3))

    def test_selected_text_defensive_bounds(self):
        self.win.lines = ["a", "b", "c"]
        with mock.patch.object(self.win, "_selection_bounds", return_value=((2, 0), (1, 0))):
            self.assertEqual(self.win._selected_text(), "")

    def test_cursor_from_screen_bad_rect_and_out_of_range(self):
        with mock.patch.object(self.win, "body_rect", return_value=(0, 0, 0, 0)):
            self.assertIsNone(self.win._cursor_from_screen(1, 1))

        self.win.lines = ["x"]
        self.win.scroll_offset = 5
        with mock.patch.object(self.win, "body_rect", return_value=(0, 0, 10, 5)):
            self.assertIsNone(self.win._cursor_from_screen(1, 1))

    def test_ensure_log_colors_and_color_pair_fallbacks(self):
        lv = self.log_mod

        # init_pair raising should be swallowed.
        orig_init = getattr(lv.curses, "init_pair", None)
        try:
            def boom_init(*_a, **_k):
                raise Exception("boom")

            lv.curses.init_pair = boom_init
            self.LogViewerWindow._log_colors_ready = False
            self.LogViewerWindow._ensure_log_colors()
            self.assertTrue(self.LogViewerWindow._log_colors_ready)
        finally:
            lv.curses.init_pair = orig_init

        base = 0
        orig_color_pair = getattr(lv.curses, "color_pair", None)
        try:
            def boom_pair(_value):
                raise Exception("boom")

            lv.curses.color_pair = boom_pair
            self.assertEqual(
                self.win._severity_attr("ERROR!", base),
                base | self.curses.A_BOLD,
            )

            lv.curses.color_pair = None
            self.assertEqual(
                self.win._severity_attr("ERROR!", base),
                base | self.curses.A_BOLD,
            )
        finally:
            lv.curses.color_pair = orig_color_pair

    def test_trim_append_reload_poll_search_and_keys(self):
        tmpdir = make_repo_tmpdir()
        self.addCleanup(tmpdir.cleanup)

        # open_path returns None on empty input.
        self.assertIsNone(self.win.open_path("   "))

        # _trim_lines_if_needed trims and rebuilds matches when search is active.
        self.win.MAX_LINES = 3
        self.win.lines = ["a", "b", "c", "d", "e"]
        self.win.scroll_offset = 2
        self.win.search_query = "a"
        with mock.patch.object(self.win, "_rebuild_search_matches") as rebuild:
            self.win._trim_lines_if_needed()
            rebuild.assert_called()

        # _append_lines early return on empty.
        self.win._append_lines([])

        # _append_lines triggers search rebuild when query is set.
        self.win.search_query = "x"
        with mock.patch.object(self.win, "_rebuild_search_matches") as rebuild2:
            self.win._append_lines(["x"])
            rebuild2.assert_called()

        # _append_lines clamps scroll offset when follow is disabled/frozen.
        self.win.follow_mode = True
        self.win.freeze_scroll = True
        self.win.scroll_offset = 999
        with mock.patch.object(self.win, "_max_scroll", return_value=0):
            self.win._append_lines(["y"])
        self.assertEqual(self.win.scroll_offset, 0)

        # _reload_file returns None when filepath is not set.
        self.win.filepath = None
        self.assertIsNone(self.win._reload_file())

        # _reload_file split-at-newline branch (start > 0).
        path = os.path.join(tmpdir.name, "tail.log")
        with open(path, "wb") as f:
            f.write(b"012345\nabc\n")
        self.win.filepath = path
        self.win.READ_TAIL_BYTES = 5
        self.win.follow_mode = True
        self.win.freeze_scroll = True
        self.win.scroll_offset = 999
        out = self.win._reload_file()
        self.assertIsNone(out)

        # _reload_file OSError path.
        self.win.filepath = os.path.join(tmpdir.name, "missing.log")
        err = self.win._reload_file()
        self.assertEqual(err.type, self.log_mod.ActionType.ERROR)

        # _poll_for_updates no-op without filepath.
        self.win.filepath = None
        self.win._poll_for_updates(force=True)

        # _poll_for_updates interval early-return.
        self.win.filepath = path
        self.win._last_poll = 100.0
        with mock.patch.object(self.log_mod.time, "monotonic", return_value=100.0):
            self.win._poll_for_updates(force=False)

        # _poll_for_updates OSError path (getsize fails).
        with mock.patch.object(self.log_mod.os.path, "getsize", side_effect=OSError("nope")):
            self.win._poll_for_updates(force=True)

        # _poll_for_updates returns early when no new chunk.
        size = os.path.getsize(path)
        self.win.filepath = path
        self.win.file_position = size
        self.win._poll_for_updates(force=True)

        # _poll_for_updates remainder branch when chunk does not end with newline.
        path2 = os.path.join(tmpdir.name, "partial.log")
        with open(path2, "w", encoding="utf-8", newline="") as f:
            f.write("partial")
        self.win.filepath = path2
        self.win.file_position = 0
        self.win._tail_remainder = ""
        self.win._poll_for_updates(force=True)
        self.assertEqual(self.win._tail_remainder, "partial")

        # _rebuild_search_matches "no matches" and clamp branch.
        self.win.lines = ["one", "two"]
        self.win.search_query = "zzz"
        self.win.search_index = 0
        self.win._rebuild_search_matches()
        self.assertEqual(self.win.search_index, -1)

        self.win.lines = ["error one", "error two"]
        self.win.search_query = "error"
        self.win.search_index = 999
        self.win._rebuild_search_matches()
        self.assertEqual(self.win.search_index, 1)

        # _jump_search_match early return and search_index < 0 behavior.
        self.win.search_matches = []
        self.win.search_index = -1
        self.win._jump_search_match(1)

        self.win.search_matches = [0]
        self.win.search_index = -1
        with mock.patch.object(self.win, "_scroll_to_line") as scroll_to:
            self.win._jump_search_match(1)
            scroll_to.assert_called_once()

        # _execute_menu_action coverage for supported actions.
        self.win.search_query = "abc"
        with mock.patch.object(self.win, "_reload_file", return_value="reloaded") as reload_file:
            self.assertEqual(self.win._execute_menu_action("lv_reload"), "reloaded")
            reload_file.assert_called_once()

        with mock.patch.object(self.win, "_scroll_to_bottom") as scroll_bottom:
            self.win.follow_mode = False
            self.win.freeze_scroll = False
            self.assertIsNone(self.win._execute_menu_action("lv_follow"))
            scroll_bottom.assert_called_once()

        with mock.patch.object(self.win, "_copy_selection") as copy_sel:
            self.assertIsNone(self.win._execute_menu_action("lv_copy"))
            copy_sel.assert_called_once()

        self.assertIsNotNone(self.win._execute_menu_action("lv_open"))
        self.assertIsNotNone(self.win._execute_menu_action("lv_close"))

        self.assertIsNone(self.win._execute_menu_action("lv_freeze"))

        out = self.win._execute_menu_action("lv_search")
        self.assertIsNone(out)
        self.assertTrue(self.win.search_input_mode)
        self.assertEqual(self.win.search_input, "abc")

        with mock.patch.object(self.win, "_jump_search_match") as jump:
            self.assertIsNone(self.win._execute_menu_action("lv_next"))
            self.assertIsNone(self.win._execute_menu_action("lv_prev"))
            self.assertGreaterEqual(jump.call_count, 2)

        self.assertIsNone(self.win._execute_menu_action("lv_unknown"))

        # draw() early returns and status variants.
        with mock.patch.object(self.log_mod, "safe_addstr") as safe_addstr:
            safe_addstr.side_effect = lambda *_a, **_k: None

            self.win.visible = False
            self.win.draw(None)

            self.win.visible = True
            with mock.patch.object(self.win, "_poll_for_updates") as poll:
                poll.side_effect = lambda *_a, **_k: None
                with mock.patch.object(self.win, "draw_frame", return_value=0):
                    with mock.patch.object(self.win, "body_rect", return_value=(0, 0, 0, 0)):
                        self.win.draw(None)

                    with mock.patch.object(self.win, "body_rect", return_value=(0, 0, 20, 4)):
                        self.win.lines = []
                        self.win.search_input_mode = True
                        self.win.search_input = "q"
                        self.win.draw(None)

                        self.win.search_input_mode = False
                        self.win.search_query = "nope"
                        self.win.search_matches = []
                        self.win.draw(None)

        # handle_click() menu paths and scroll-to-line fallback.
        class DummyMenu:
            def __init__(self, action):
                self.active = False
                self._action = action

            def on_menu_bar(self, *_a, **_k):
                return True

            def handle_click(self, *_a, **_k):
                return self._action

        self.win.window_menu = DummyMenu("lv_open")
        with mock.patch.object(self.win, "_execute_menu_action", return_value="ok") as exec_menu:
            self.assertEqual(self.win.handle_click(1, 1), "ok")
            exec_menu.assert_called_once()

        self.win.window_menu = DummyMenu(None)
        self.assertIsNone(self.win.handle_click(1, 1))

        self.win.window_menu = None
        with mock.patch.object(self.win, "_cursor_from_screen", return_value=(2, 3)):
            with mock.patch.object(self.win, "_scroll_to_line") as scroll_to_line:
                self.win.handle_click(1, 1, bstate=0)
                scroll_to_line.assert_called_once_with(2)

        # handle_mouse_drag() edge paths.
        self.win._mouse_selecting = True
        self.win.handle_mouse_drag(1, 1, bstate=0)
        self.assertFalse(self.win._mouse_selecting)

        with mock.patch.object(self.win, "_cursor_from_screen", return_value=None):
            self.win.handle_mouse_drag(1, 1, bstate=self.curses.BUTTON1_PRESSED)

        self.win.selection_anchor = None
        self.win.selection_cursor = None
        with mock.patch.object(self.win, "_cursor_from_screen", return_value=(0, 0)):
            self.win.handle_mouse_drag(1, 1, bstate=self.curses.BUTTON1_PRESSED)
        self.assertEqual(self.win.selection_anchor, (0, 0))

        # _handle_search_input_key() branches.
        self.win.search_input_mode = True
        self.win.search_input = "abc"
        self.assertIsNone(self.win._handle_search_input_key("x", 27))  # Esc

        self.win.search_input_mode = True
        self.win.search_input = "abc"
        with mock.patch.object(self.win, "_rebuild_search_matches") as rebuild3:
            with mock.patch.object(self.win, "_jump_search_match") as jump3:
                self.assertIsNone(self.win._handle_search_input_key("\n", 10))
                rebuild3.assert_called()
                jump3.assert_called()

        self.win.search_input_mode = True
        self.win.search_input = "abc"
        self.assertIsNone(self.win._handle_search_input_key("\b", self.curses.KEY_BACKSPACE))
        self.assertEqual(self.win.search_input, "ab")

        self.win.search_input_mode = True
        self.win.search_input = ""
        self.assertIsNone(self.win._handle_search_input_key("x", ord("x")))
        self.assertEqual(self.win.search_input, "x")

        self.win.search_input_mode = True
        self.win.search_input = ""
        self.assertIsNone(self.win._handle_search_input_key(ord("y"), ord("y")))
        self.assertEqual(self.win.search_input, "y")

        self.win.search_input_mode = True
        self.win.search_input = ""
        self.assertIsNone(self.win._handle_search_input_key(object(), None))

        # handle_key() menu-active and key branch coverage.
        class DummyKeyMenu:
            def __init__(self, action):
                self.active = True
                self._action = action

            def handle_key(self, *_a, **_k):
                return self._action

        self.win.window_menu = DummyKeyMenu("lv_open")
        with mock.patch.object(self.win, "_execute_menu_action", return_value="menu") as exec_menu2:
            self.assertEqual(self.win.handle_key(1), "menu")
            exec_menu2.assert_called_once()

        self.win.window_menu = DummyKeyMenu(None)
        self.assertIsNone(self.win.handle_key(1))

        self.win.window_menu = None
        self.win.search_input_mode = True
        with mock.patch.object(self.win, "_handle_search_input_key", return_value="search") as hsearch:
            self.assertEqual(self.win.handle_key(ord("a")), "search")
            hsearch.assert_called_once()

        self.win.search_input_mode = False
        self.win.scroll_offset = 5
        self.win.follow_mode = True
        with mock.patch.object(self.win, "_max_scroll", return_value=10):
            self.win.handle_key(self.curses.KEY_UP)
            self.win.handle_key(self.curses.KEY_DOWN)

        with mock.patch.object(self.win, "_visible_line_rows", return_value=3):
            self.win.handle_key(self.curses.KEY_PPAGE)
            self.win.handle_key(self.curses.KEY_NPAGE)

        self.win.handle_key(self.curses.KEY_HOME)

        with mock.patch.object(self.win, "_scroll_to_bottom") as sbottom:
            self.win.freeze_scroll = False
            self.win.handle_key(self.curses.KEY_END)
            sbottom.assert_called()

        with mock.patch.object(self.win, "_scroll_to_bottom") as sbottom2:
            self.win.freeze_scroll = False
            self.win.follow_mode = False
            self.win.handle_key(ord("f"))
            sbottom2.assert_called()

        with mock.patch.object(self.win, "_copy_selection") as csel:
            self.win.handle_key(getattr(self.curses, "KEY_F6", -1))
            csel.assert_called_once()

        self.win.handle_key(ord(" "))
        self.win.search_query = "hey"
        self.win.handle_key(ord("/"))
        self.win.search_input_mode = False

        with mock.patch.object(self.win, "_jump_search_match") as jumpx:
            self.win.handle_key(ord("n"))
            self.win.handle_key(ord("N"))
            self.assertGreaterEqual(jumpx.call_count, 2)

        with mock.patch.object(self.win, "_reload_file", return_value="reloaded2") as rld:
            self.assertEqual(self.win.handle_key(ord("r")), "reloaded2")
            rld.assert_called_once()


if __name__ == "__main__":
    unittest.main()

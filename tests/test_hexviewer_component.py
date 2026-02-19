import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_F6 = 270
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_PPAGE = 339
    fake.KEY_NPAGE = 338
    fake.KEY_HOME = 262
    fake.KEY_END = 360
    fake.KEY_ENTER = 343
    fake.KEY_BACKSPACE = 263
    fake.KEY_IC = 331
    fake.BUTTON1_CLICKED = 0x1
    fake.BUTTON1_PRESSED = 0x2
    fake.BUTTON1_DOUBLE_CLICKED = 0x4
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.error = Exception
    fake.color_pair = lambda value: value * 10
    fake.init_pair = lambda *_: None
    return fake


class HexViewerComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.window",
            "retrotui.ui.menu",
            "retrotui.core.actions",
            "retrotui.apps.hexviewer",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.hex_mod = importlib.import_module("retrotui.apps.hexviewer")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.window",
            "retrotui.ui.menu",
            "retrotui.core.actions",
            "retrotui.apps.hexviewer",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _temp_bin(self, payload):
        handle = tempfile.NamedTemporaryFile("wb", delete=False)
        handle.write(payload)
        handle.flush()
        handle.close()
        return handle.name

    def _make_window(self, path=None):
        return self.hex_mod.HexViewerWindow(0, 0, 90, 14, filepath=path)

    def test_open_path_and_format_helpers(self):
        data = bytes(range(64))
        path = self._temp_bin(data)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window()

        result = win.open_path(path)

        self.assertIsNone(result)
        self.assertEqual(win.filepath, path)
        self.assertEqual(win.file_size, 64)
        self.assertIn("Hex Viewer -", win.title)
        row_text = win._format_row(0, data[:16])
        self.assertIn("00000000", row_text)
        self.assertIn("00 01 02", row_text)
        self.assertIn("| ................", row_text)
        self.assertEqual(win._format_header().split("|")[0].strip(), "OFFSET(h)")

    def test_open_path_errors_and_read_slice_error(self):
        win = self._make_window()

        missing = win.open_path("/tmp/does-not-exist.bin")
        self.assertEqual(missing.type, self.actions_mod.ActionType.ERROR)

        path = self._temp_bin(b"abc")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win.open_path(path)
        with mock.patch("builtins.open", side_effect=OSError("blocked")):
            payload = win._read_slice(0, 8)
        self.assertEqual(payload, b"")
        self.assertIn("Read error", win.status_message)

    def test_parse_helpers_and_find_methods(self):
        self.assertEqual(self.hex_mod._ascii_column(b"A\x00~"), "A.~")
        self.assertEqual(self.hex_mod.HexViewerWindow._parse_goto_value("0x10"), 16)
        self.assertEqual(self.hex_mod.HexViewerWindow._parse_goto_value("10h"), 16)
        self.assertEqual(self.hex_mod.HexViewerWindow._parse_goto_value("15"), 15)
        self.assertIsNone(self.hex_mod.HexViewerWindow._parse_goto_value(""))
        self.assertIsNone(self.hex_mod.HexViewerWindow._parse_goto_value("bad"))

        self.assertEqual(self.hex_mod.HexViewerWindow._parse_search_query("0x4142"), b"AB")
        self.assertEqual(self.hex_mod.HexViewerWindow._parse_search_query("41 42"), b"AB")
        self.assertEqual(self.hex_mod.HexViewerWindow._parse_search_query("AB"), b"AB")
        self.assertIsNone(self.hex_mod.HexViewerWindow._parse_search_query("0x1"))
        self.assertIsNone(self.hex_mod.HexViewerWindow._parse_search_query(""))
        self.assertIsNone(self.hex_mod.HexViewerWindow._parse_search_query("0xGG"))

        path = self._temp_bin(b"abc--abc")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window(path)
        self.assertEqual(win._find_bytes(b"abc", 0), 0)
        self.assertEqual(win._find_with_wrap(b"abc", 4), 5)
        self.assertIsNone(win._find_with_wrap(b"xyz", 0))

        with mock.patch("builtins.open", side_effect=OSError("nope")):
            self.assertIsNone(win._find_bytes(b"a", 0))
        self.assertIn("Search error", win.status_message)

    def test_update_title_and_guard_helpers(self):
        win = self._make_window()
        win.filepath = None
        win.file_size = 123
        win._update_title()
        self.assertEqual(win.title, "Hex Viewer")

        win.file_size = 0
        self.assertEqual(win._max_top_offset(), 0)
        self.assertEqual(win._read_slice(0, 0), b"")
        self.assertIsNone(win._find_bytes(b"", 0))
        self.assertIsNone(win._find_with_wrap(b"X", 0))

        self.assertIn("01 02", win._format_row(0, b"\x01\x02"))

    def test_open_path_os_stat_error(self):
        win = self._make_window()

        with (
            mock.patch.object(self.hex_mod.os.path, "isfile", return_value=True),
            mock.patch.object(self.hex_mod.os, "stat", side_effect=OSError("stat blocked")),
        ):
            result = win.open_path("/tmp/f.bin")

        self.assertEqual(result.type, self.actions_mod.ActionType.ERROR)
        self.assertIn("stat blocked", result.payload)

    def test_prompt_apply_invalid_and_not_found_paths(self):
        path = self._temp_bin(b"abc")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window(path)

        win.prompt_mode = "goto"
        win.prompt_value = ""
        win._apply_prompt()
        self.assertIn("Invalid offset", win.status_message)

        win.prompt_mode = "search"
        win.prompt_value = "0x1"
        win._apply_prompt()
        self.assertIn("Invalid search query", win.status_message)

        win.prompt_mode = "search"
        win.prompt_value = "needle"
        with mock.patch.object(win, "_find_with_wrap", return_value=None):
            win._apply_prompt()
        self.assertEqual(win.status_message, "Pattern not found.")

        win.last_query_bytes = b"zzz"
        with mock.patch.object(win, "_find_with_wrap", return_value=None):
            win.find_next()
        self.assertEqual(win.status_message, "Pattern not found.")

    def test_row_mapping_and_selected_text_edge_cases(self):
        win = self._make_window()
        win.filepath = None
        win.selection_anchor = 10
        win.selection_cursor = 12
        self.assertEqual(win._selected_text(), "")

        with mock.patch.object(win, "_selected_row_bounds", return_value=(1, 1)):
            win.filepath = "x"
            self.assertEqual(win._selected_text(), "")

        win.selection_anchor = 5
        win.selection_cursor = 1
        self.assertEqual(win._selected_row_bounds(), (1, 5))

        win.body_rect = mock.Mock(return_value=(0, 0, 0, 1))
        self.assertIsNone(win._row_from_screen(0, 0))

        win.body_rect = mock.Mock(return_value=(0, 0, 80, 6))
        win.filepath = "x"
        win.file_size = 10
        win.top_offset = -16
        self.assertIsNone(win._row_from_screen(1, 1))

        win.body_rect = mock.Mock(return_value=(0, 0, 80, 10))
        win.top_offset = 0
        self.assertIsNone(win._row_from_screen(1, 1 + 5))

    def test_selected_text_breaks_when_selection_exceeds_file(self):
        path = self._temp_bin(b"0123456789")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window(path)
        win.selection_anchor = 0
        win.selection_cursor = 3
        text = win._selected_text()
        self.assertIn("00000000", text)
        self.assertNotIn("00000010", text)

    def test_copy_selection_fallback_and_menu_and_key_branches(self):
        path = self._temp_bin(bytes(range(32)))
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window(path)
        win.body_rect = mock.Mock(return_value=(1, 1, 80, 10))
        win.cursor_offset = 0
        win.clear_selection()

        with mock.patch.object(self.hex_mod, "copy_text") as copy_text:
            win._copy_selection()
        copy_text.assert_called_once()

        win.filepath = None
        self.assertIsNone(win.execute_action("hx_reload"))
        self.assertIn("No file opened", win.status_message)

        win = self._make_window(path)
        with mock.patch.object(win, "_copy_selection") as copy_selection:
            self.assertIsNone(win.execute_action("hx_copy"))
        copy_selection.assert_called_once_with()

        # Menu active but no action branch.
        win.window_menu.active = True
        win.window_menu.handle_key = mock.Mock(return_value=None)
        self.assertIsNone(win.handle_key(ord("x")))

        # Prompt-mode handle_key delegates to _handle_prompt_key.
        win.window_menu.active = False
        win.prompt_mode = "search"
        with mock.patch.object(win, "_handle_prompt_key", return_value=None) as prompt_key:
            self.assertIsNone(win.handle_key(ord("a")))
        prompt_key.assert_called_once()

        # Final fallthrough returns None.
        win.prompt_mode = None
        self.assertIsNone(win.handle_key(ord("z")))

    def test_prompt_key_accepts_int_key_codes(self):
        path = self._temp_bin(b"abc")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window(path)

        win.prompt_mode = "search"
        win.prompt_value = ""
        win._handle_prompt_key(None, ord("b"))
        self.assertEqual(win.prompt_value, "b")

    def test_draw_returns_early_and_renders_prompt_modes(self):
        path = self._temp_bin(bytes(range(48)))
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window(path)

        win.visible = False
        with mock.patch.object(self.hex_mod, "safe_addstr") as safe_addstr:
            win.draw(types.SimpleNamespace())
        safe_addstr.assert_not_called()

        win.visible = True
        win.body_rect = mock.Mock(return_value=(1, 2, 0, 8))
        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.hex_mod, "safe_addstr") as safe_addstr,
        ):
            win.draw(types.SimpleNamespace())
        safe_addstr.assert_not_called()

        win.body_rect = mock.Mock(return_value=(1, 2, 80, 8))
        win.prompt_mode = "search"
        win.prompt_value = "AA"
        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.hex_mod, "theme_attr", return_value=0),
            mock.patch.object(self.hex_mod, "safe_addstr") as safe_addstr,
        ):
            win.draw(types.SimpleNamespace())
        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("SEARCH>" in text for text in rendered))

        win.prompt_mode = "goto"
        win.prompt_value = "10"
        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.hex_mod, "theme_attr", return_value=0),
            mock.patch.object(self.hex_mod, "safe_addstr") as safe_addstr,
        ):
            win.draw(types.SimpleNamespace())
        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("GOTO>" in text for text in rendered))

    def test_draw_renders_header_rows_and_status(self):
        path = self._temp_bin(bytes(range(48)))
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window(path)
        win.body_rect = mock.Mock(return_value=(1, 2, 80, 8))
        win.status_message = ""

        class _Dummy:
            def getmaxyx(self):
                return (30, 120)

            def addnstr(self, *_args, **_kwargs):
                return None

        screen = _Dummy()

        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.hex_mod, "theme_attr", return_value=0),
            mock.patch.object(self.hex_mod, "safe_addstr") as safe_addstr,
        ):
            win.draw(screen)

        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("OFFSET(h)" in text for text in rendered))
        self.assertTrue(any("00000000" in text for text in rendered))
        self.assertTrue(any("close" in text.lower() for text in rendered))

        win.filepath = None
        win.status_message = "hello"
        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.hex_mod, "theme_attr", return_value=0),
            mock.patch.object(self.hex_mod, "safe_addstr") as safe_addstr,
        ):
            win.draw(screen)
        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("No file opened" in text for text in rendered))
        self.assertTrue(any("hello" in text for text in rendered))

    def test_menu_actions_prompt_and_key_paths(self):
        path = self._temp_bin(b"start-needle-end-needle")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window(path)
        win.body_rect = mock.Mock(return_value=(1, 1, 80, 10))

        self.assertEqual(
            win.execute_action("hx_open").type,
            self.actions_mod.ActionType.REQUEST_OPEN_PATH,
        )
        self.assertIsNone(win.execute_action("hx_reload"))
        self.assertIsNone(win.execute_action("hx_search"))
        self.assertEqual(win.prompt_mode, "search")
        self.assertIsNone(win.execute_action("hx_goto"))
        self.assertEqual(win.prompt_mode, "goto")
        self.assertIsNone(win.execute_action("hx_next"))
        self.assertIsNone(win.execute_action("unknown"))
        close = win.execute_action("hx_close")
        self.assertEqual(close.type, self.actions_mod.ActionType.EXECUTE)

        # Prompt key flow: write, backspace, enter, escape.
        win.prompt_mode = "goto"
        win.prompt_value = "10"
        win._handle_prompt_key("\n", 10)
        self.assertIsNone(win.prompt_mode)
        self.assertIn("Jumped", win.status_message)

        win.prompt_mode = "search"
        win.prompt_value = "needle"
        win._handle_prompt_key("\n", 10)
        self.assertIn("Found", win.status_message)

        win.prompt_mode = "search"
        win.prompt_value = "x"
        win._handle_prompt_key("", 8)
        self.assertEqual(win.prompt_value, "")
        win._handle_prompt_key("a", ord("a"))
        self.assertEqual(win.prompt_value, "a")
        win._handle_prompt_key("", 27)
        self.assertIsNone(win.prompt_mode)
        self.assertIn("cancelled", win.status_message.lower())

        win.last_query_bytes = b"needle"
        win.find_next()
        self.assertIn("Found", win.status_message)
        win.last_query_bytes = None
        win.find_next()
        self.assertIn("Press / first", win.status_message)

        # Scrolling keys and command shortcuts.
        win.handle_key(self.curses.KEY_DOWN)
        win.handle_key(self.curses.KEY_UP)
        win.handle_key(self.curses.KEY_PPAGE)
        win.handle_key(self.curses.KEY_NPAGE)
        win.handle_key(self.curses.KEY_HOME)
        win.handle_key(self.curses.KEY_END)
        self.assertIsNone(win.handle_key(ord("/")))
        self.assertEqual(win.prompt_mode, "search")
        win.prompt_mode = None
        self.assertIsNone(win.handle_key(ord("n")))
        self.assertIsNone(win.handle_key(ord("g")))
        win.prompt_mode = None
        self.assertIsNone(win.handle_key(ord("r")))
        self.assertEqual(
            win.handle_key(ord("o")).type,
            self.actions_mod.ActionType.REQUEST_OPEN_PATH,
        )
        self.assertEqual(
            win.handle_key(ord("q")).payload,
            self.actions_mod.AppAction.CLOSE_WINDOW,
        )

        # Menu active branch.
        win.window_menu.active = True
        win.window_menu.handle_key = mock.Mock(return_value="hx_open")
        action = win.handle_key(ord("x"))
        self.assertEqual(action.type, self.actions_mod.ActionType.REQUEST_OPEN_PATH)

        # No file reload branch.
        empty = self._make_window()
        empty.handle_key(ord("r"))
        self.assertIn("No file opened", empty.status_message)

    def test_handle_click_and_zero_size_goto(self):
        win = self._make_window()
        win.window_menu.handle_click = mock.Mock(return_value="hx_close")
        win.window_menu.on_menu_bar = mock.Mock(return_value=True)
        action = win.handle_click(1, 1)
        self.assertEqual(action.payload, self.actions_mod.AppAction.CLOSE_WINDOW)

        # Empty-file cursor path.
        path = self._temp_bin(b"")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win.open_path(path)
        win._goto_offset(10)
        self.assertIsNone(win.cursor_offset)
        self.assertEqual(win.top_offset, 0)

    def test_hex_selection_drag_copy_and_draw_highlight(self):
        path = self._temp_bin(bytes(range(96)))
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window(path)
        win.body_rect = mock.Mock(return_value=(1, 2, 80, 10))

        # Start selection and extend by drag to next row.
        self.assertIsNone(win.handle_click(2, 3, self.curses.BUTTON1_PRESSED))
        self.assertIsNone(win.handle_mouse_drag(2, 4, self.curses.BUTTON1_PRESSED))
        self.assertTrue(win.has_selection())
        selected = win._selected_text()
        self.assertIn("\n", selected)
        self.assertIn("00000000", selected)

        with mock.patch.object(self.hex_mod, "copy_text") as copy_text:
            self.assertIsNone(win.handle_key(self.curses.KEY_F6))
        copy_text.assert_called_once()

        with mock.patch.object(self.hex_mod, "copy_text") as copy_text:
            self.assertIsNone(win.handle_key(self.curses.KEY_IC))
        copy_text.assert_called_once()

        class _Dummy:
            def getmaxyx(self):
                return (40, 120)

            def addnstr(self, *_args, **_kwargs):
                return None

        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.hex_mod, "theme_attr", return_value=0),
            mock.patch.object(self.hex_mod, "safe_addstr") as safe_addstr,
        ):
            win.draw(_Dummy())
        self.assertTrue(
            any(
                len(call.args) >= 5 and (call.args[4] & self.curses.A_REVERSE)
                for call in safe_addstr.call_args_list
            )
        )

        # Click outside selection clears.
        self.assertIsNone(win.handle_click(0, 0, self.curses.BUTTON1_CLICKED))
        self.assertFalse(win.has_selection())

    def test_mouse_drag_paths_when_not_pressed_or_outside(self):
        path = self._temp_bin(bytes(range(48)))
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window(path)
        win.body_rect = mock.Mock(return_value=(1, 2, 80, 10))

        win._mouse_selecting = True
        self.assertIsNone(win.handle_mouse_drag(2, 3, 0))
        self.assertFalse(win._mouse_selecting)

        with mock.patch.object(win, "_row_from_screen", return_value=None):
            self.assertIsNone(win.handle_mouse_drag(2, 3, self.curses.BUTTON1_PRESSED))

        win.clear_selection()
        with mock.patch.object(win, "_row_from_screen", return_value=1):
            self.assertIsNone(win.handle_mouse_drag(2, 3, self.curses.BUTTON1_PRESSED))
        self.assertEqual(win.selection_anchor, 1)


if __name__ == "__main__":
    unittest.main()

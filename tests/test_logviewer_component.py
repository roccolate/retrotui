import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_PPAGE = 339
    fake.KEY_NPAGE = 338
    fake.KEY_HOME = 262
    fake.KEY_END = 360
    fake.KEY_ENTER = 343
    fake.KEY_BACKSPACE = 263
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.COLOR_RED = 1
    fake.COLOR_YELLOW = 3
    fake.COLOR_GREEN = 2
    fake.error = Exception
    fake.color_pair = lambda value: value * 10
    fake.init_pair = lambda *_: None
    return fake


class LogViewerComponentTests(unittest.TestCase):
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
            "retrotui.apps.logviewer",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.log_mod = importlib.import_module("retrotui.apps.logviewer")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.window",
            "retrotui.ui.menu",
            "retrotui.core.actions",
            "retrotui.apps.logviewer",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_window(self):
        return self.log_mod.LogViewerWindow(0, 0, 72, 20)

    def _temp_log(self, content):
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        handle.write(content)
        handle.flush()
        handle.close()
        return handle.name

    def test_open_path_loads_file_and_sets_title(self):
        path = self._temp_log("INFO one\nWARN two\nERROR three\n")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window()

        result = win.open_path(path)

        self.assertIsNone(result)
        self.assertEqual(win.filepath, path)
        self.assertIn("Log Viewer -", win.title)
        self.assertEqual(len(win.lines), 3)
        self.assertEqual(win.lines[-1], "ERROR three")

    def test_poll_for_updates_appends_tail_lines(self):
        path = self._temp_log("INFO start\n")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        win = self._make_window()
        win.open_path(path)

        with open(path, "a", encoding="utf-8") as stream:
            stream.write("WARN next\nERROR final\n")

        win._poll_for_updates(force=True)

        self.assertTrue(any("WARN next" in line for line in win.lines))
        self.assertTrue(any("ERROR final" in line for line in win.lines))

    def test_search_build_and_navigation(self):
        win = self._make_window()
        win.lines = ["INFO first", "WARN alpha", "ERROR alpha", "INFO omega"]
        win.search_query = "alpha"
        win._rebuild_search_matches()

        self.assertEqual(win.search_matches, [1, 2])
        self.assertEqual(win.search_index, 0)

        win._jump_search_match(1)
        self.assertEqual(win.search_index, 1)
        win._jump_search_match(1)
        self.assertEqual(win.search_index, 0)
        win._jump_search_match(-1)
        self.assertEqual(win.search_index, 1)

    def test_handle_key_open_and_close_actions(self):
        win = self._make_window()

        open_result = win.handle_key(ord("o"))
        close_result = win.handle_key(ord("q"))

        self.assertEqual(open_result.type, self.actions_mod.ActionType.REQUEST_OPEN_PATH)
        self.assertEqual(close_result.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(close_result.payload, self.actions_mod.AppAction.CLOSE_WINDOW)

    def test_draw_renders_header_status_and_lines(self):
        win = self._make_window()
        win.lines = ["INFO hello", "WARN world", "ERROR fail"]
        win.filepath = "/tmp/demo.log"
        win.search_query = "world"
        win._rebuild_search_matches()

        with (
            mock.patch.object(win, "_poll_for_updates", return_value=None),
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.log_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(self.log_mod, "theme_attr", return_value=0),
        ):
            win.draw(None)

        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("TAIL" in text or "VIEW" in text for text in rendered))
        self.assertTrue(any("INFO hello" in text for text in rendered))
        self.assertTrue(any("WARN world" in text for text in rendered))
        self.assertTrue(any("Arrows/PgUp/PgDn" in text or "/world" in text for text in rendered))


if __name__ == "__main__":
    unittest.main()


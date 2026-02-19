import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_PPAGE = 339
    fake.KEY_NPAGE = 338
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.error = Exception
    fake.color_pair = lambda value: value * 10
    fake.init_pair = lambda *_: None
    return fake


class ImageViewerComponentTests(unittest.TestCase):
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
            "retrotui.apps.image_viewer",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.image_mod = importlib.import_module("retrotui.apps.image_viewer")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.window",
            "retrotui.ui.menu",
            "retrotui.core.actions",
            "retrotui.apps.image_viewer",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _temp_file(self, suffix, payload=b"data"):
        handle = tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False)
        handle.write(payload)
        handle.flush()
        handle.close()
        return handle.name

    def _make_window(self, path=None):
        return self.image_mod.ImageViewerWindow(0, 0, 80, 20, filepath=path)

    def test_strip_ansi_and_backend_detection(self):
        text = "A\x1b[31mB\x1b]0;title\x07C"
        self.assertEqual(self.image_mod._strip_ansi(text), "ABC")

        win = self._make_window()
        with mock.patch.object(self.image_mod.shutil, "which", side_effect=["/bin/chafa"]):
            self.assertEqual(win._detect_backend(), "chafa")
        # Cached backend path should not re-check shutil.which.
        with mock.patch.object(self.image_mod.shutil, "which", side_effect=AssertionError("should not call")):
            self.assertEqual(win._detect_backend(), "chafa")

    def test_open_path_errors_and_success(self):
        win = self._make_window()
        missing = win.open_path("/tmp/missing.png")
        self.assertEqual(missing.type, self.actions_mod.ActionType.ERROR)

        wrong = self._temp_file(".txt")
        self.addCleanup(lambda: os.path.exists(wrong) and os.unlink(wrong))
        not_image = win.open_path(wrong)
        self.assertEqual(not_image.type, self.actions_mod.ActionType.ERROR)
        self.assertIn("Not a supported media file", not_image.payload)

        image = self._temp_file(".png")
        self.addCleanup(lambda: os.path.exists(image) and os.unlink(image))
        result = win.open_path(image)
        self.assertIsNone(result)
        self.assertEqual(win.filepath, os.path.realpath(image))
        self.assertIn("Image Viewer -", win.title)

    def test_render_image_backend_paths(self):
        image = self._temp_file(".png")
        self.addCleanup(lambda: os.path.exists(image) and os.unlink(image))
        win = self._make_window(image)

        # Missing backend.
        with mock.patch.object(win, "_detect_backend", return_value=""):
            lines = win._render_image(30, 10)
        self.assertTrue(lines[0].startswith("[image backend missing"))

        # Backend failure.
        with (
            mock.patch.object(win, "_detect_backend", return_value="chafa"),
            mock.patch.object(self.image_mod.subprocess, "run", side_effect=OSError("boom")),
        ):
            lines = win._render_image(30, 10)
        self.assertEqual(lines, ["[image render failed via chafa]"])

        # Non-zero return code.
        failed = types.SimpleNamespace(returncode=1, stdout="", stderr="nope")
        with (
            mock.patch.object(win, "_detect_backend", return_value="timg"),
            mock.patch.object(self.image_mod.subprocess, "run", return_value=failed),
        ):
            lines = win._render_image(30, 10)
        self.assertEqual(lines, ["[image render failed via timg]"])

        # Empty output.
        empty = types.SimpleNamespace(returncode=0, stdout="", stderr="")
        with (
            mock.patch.object(win, "_detect_backend", return_value="catimg"),
            mock.patch.object(self.image_mod.subprocess, "run", return_value=empty),
        ):
            lines = win._render_image(30, 10)
        self.assertEqual(lines, ["[empty image output]"])

        # Success output with ANSI text.
        ok = types.SimpleNamespace(returncode=0, stdout="A\x1b[31mB\nC", stderr="")
        with (
            mock.patch.object(win, "_detect_backend", return_value="chafa"),
            mock.patch.object(self.image_mod.subprocess, "run", return_value=ok),
        ):
            lines = win._render_image(30, 10)
        self.assertEqual(lines[:2], ["AB", "C"])

    def test_cached_render_lines_and_zoom(self):
        image = self._temp_file(".png")
        self.addCleanup(lambda: os.path.exists(image) and os.unlink(image))
        win = self._make_window(image)

        with mock.patch.object(win, "_render_image", return_value=["one"]) as render:
            first = win._cached_render_lines(20, 8)
            second = win._cached_render_lines(20, 8)
        self.assertEqual(first, ["one"])
        self.assertEqual(second, ["one"])
        render.assert_called_once()

        with (
            mock.patch.object(self.image_mod.os, "stat", side_effect=OSError("oops")),
            mock.patch.object(win, "_render_image", return_value=["two"]) as render,
        ):
            lines = win._cached_render_lines(21, 8)
        self.assertEqual(lines, ["two"])
        render.assert_called_once()

        win.zoom_index = 2
        win._set_zoom(1)
        self.assertEqual(win.zoom_index, 3)
        win._set_zoom(-99)
        self.assertEqual(win.zoom_index, 0)
        win._set_zoom(99)
        self.assertEqual(win.zoom_index, len(win.ZOOM_LEVELS) - 1)

    def test_draw_and_status_paths(self):
        image = self._temp_file(".png")
        self.addCleanup(lambda: os.path.exists(image) and os.unlink(image))
        win = self._make_window(image)
        win.body_rect = mock.Mock(return_value=(2, 3, 80, 6))
        win.status_message = "Loaded"

        class _Dummy:
            def getmaxyx(self):
                return (30, 120)

            def addnstr(self, *_args, **_kwargs):
                return None

        screen = _Dummy()

        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(win, "_cached_render_lines", return_value=["x", "y"]),
            mock.patch.object(self.image_mod, "theme_attr", return_value=0),
            mock.patch.object(self.image_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(win, "_detect_backend", return_value="chafa"),
        ):
            win.draw(screen)
        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("x" in text for text in rendered))
        self.assertTrue(any("Loaded" in text for text in rendered))
        self.assertEqual(win.status_message, "")

        # Default status branch
        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(win, "_cached_render_lines", return_value=["x"]),
            mock.patch.object(self.image_mod, "theme_attr", return_value=0),
            mock.patch.object(self.image_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(win, "_detect_backend", return_value=""),
        ):
            win.draw(screen)
        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("backend:none" in text for text in rendered))

    def test_execute_action_key_and_click_paths(self):
        win = self._make_window()

        self.assertEqual(
            win.execute_action("iv_open").type,
            self.actions_mod.ActionType.REQUEST_OPEN_PATH,
        )
        self.assertIsNone(win.execute_action("iv_reload"))
        self.assertIn("No media opened.", win.status_message)
        self.assertIsNone(win.execute_action("iv_zoom_in"))
        self.assertIsNone(win.execute_action("iv_zoom_out"))
        self.assertIsNone(win.execute_action("iv_zoom_reset"))
        self.assertIsNone(win.execute_action("unknown"))
        close = win.execute_action("iv_close")
        self.assertEqual(close.payload, self.actions_mod.AppAction.CLOSE_WINDOW)

        # Key shortcuts
        self.assertEqual(win.handle_key(ord("o")).type, self.actions_mod.ActionType.REQUEST_OPEN_PATH)
        self.assertEqual(win.handle_key(ord("q")).payload, self.actions_mod.AppAction.CLOSE_WINDOW)
        self.assertIsNone(win.handle_key(ord("r")))
        self.assertIsNone(win.handle_key(ord("+")))
        self.assertIsNone(win.handle_key(ord("-")))
        self.assertIsNone(win.handle_key(ord("0")))
        self.assertIsNone(win.handle_key(self.curses.KEY_PPAGE))
        self.assertIsNone(win.handle_key(self.curses.KEY_NPAGE))

        # Menu-active branch
        win.window_menu.active = True
        win.window_menu.handle_key = mock.Mock(return_value="iv_open")
        action = win.handle_key(ord("x"))
        self.assertEqual(action.type, self.actions_mod.ActionType.REQUEST_OPEN_PATH)

        # Click path
        win.window_menu.on_menu_bar = mock.Mock(return_value=True)
        win.window_menu.handle_click = mock.Mock(return_value="iv_close")
        action = win.handle_click(1, 1)
        self.assertEqual(action.payload, self.actions_mod.AppAction.CLOSE_WINDOW)

    def test_missing_branches_for_coverage(self):
        win = self._make_window()

        # _update_title() sets default title when no filepath is open.
        win.filepath = None
        win._update_title()
        self.assertEqual(win.title, "Media Viewer")

        # _detect_backend() timg/catimg branches.
        win2 = self._make_window()
        with mock.patch.object(self.image_mod.shutil, "which", side_effect=[None, "/bin/timg"]):
            self.assertEqual(win2._detect_backend(), "timg")

        win3 = self._make_window()
        with mock.patch.object(self.image_mod.shutil, "which", side_effect=[None, None, "/bin/catimg"]):
            self.assertEqual(win3._detect_backend(), "catimg")

        # _cached_render_lines() early return when no file is open.
        self.assertTrue(any("No media opened." in line for line in win._cached_render_lines(10, 3)))

        # iv_reload sets status depending on whether a file is open.
        win.filepath = "/tmp/fake.png"
        self.assertIsNone(win.execute_action("iv_reload"))
        self.assertEqual(win.status_message, "Reloaded.")

        # draw() early returns for invisible or invalid body rect.
        win.visible = False
        with mock.patch.object(win, "draw_frame") as draw_frame:
            win.draw(None)
        draw_frame.assert_not_called()

        win.visible = True
        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(win, "body_rect", return_value=(0, 0, 0, 0)),
        ):
            win.draw(None)

        # handle_click() returns None when menu yields no action.
        fake_menu = mock.Mock()
        fake_menu.active = True
        fake_menu.on_menu_bar.return_value = True
        fake_menu.handle_click.return_value = None
        win.window_menu = fake_menu
        self.assertIsNone(win.handle_click(0, 0))

        # handle_key() returns None when menu yields no action.
        fake_menu.handle_key.return_value = None
        self.assertIsNone(win.handle_key(ord("x")))

        # handle_key() final fall-through returns None for unhandled keys.
        win.window_menu.active = False
        self.assertIsNone(win.handle_key(ord("x")))


if __name__ == "__main__":
    unittest.main()

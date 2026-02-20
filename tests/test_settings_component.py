import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_LEFT = 260
    fake.KEY_RIGHT = 261
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_ENTER = 343
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.COLOR_BLACK = 0
    fake.COLOR_BLUE = 4
    fake.COLOR_CYAN = 6
    fake.COLOR_GREEN = 2
    fake.COLOR_WHITE = 7
    fake.COLOR_YELLOW = 3
    fake.error = Exception
    fake.color_pair = lambda value: value * 10
    return fake


class SettingsComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.theme",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.actions",
            "retrotui.apps.settings",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.settings_mod = importlib.import_module("retrotui.apps.settings")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.theme",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.actions",
            "retrotui.apps.settings",
        ):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_app(self):
        app = types.SimpleNamespace(
            theme_name="win31",
            default_show_hidden=False,
            default_word_wrap=False,
            config=types.SimpleNamespace(
                sunday_first=False,
                show_welcome=True,
                hidden_icons="",
            ),
            windows=[],
        )
        app.apply_theme = mock.Mock(side_effect=lambda name: setattr(app, "theme_name", name))

        def _apply_preferences(*, show_hidden=None, word_wrap_default=None, sunday_first=None, apply_to_open_windows=False):
            if show_hidden is not None:
                app.default_show_hidden = bool(show_hidden)
            if word_wrap_default is not None:
                app.default_word_wrap = bool(word_wrap_default)
            if sunday_first is not None:
                app.config.sunday_first = bool(sunday_first)
            app._last_apply_to_open = apply_to_open_windows

        app.apply_preferences = mock.Mock(side_effect=_apply_preferences)
        app.persist_config = mock.Mock(return_value=None)
        app.refresh_icons = mock.Mock()
        return app

    def _make_window(self):
        return self.settings_mod.SettingsWindow(1, 1, 56, 18, self._make_app())

    def test_constructor_indices_and_activate_basic_paths(self):
        win = self._make_window()

        self.assertGreaterEqual(win._theme_count(), 5)
        self.assertEqual(win._controls_count(), win._theme_count() + 7)
        self.assertEqual(win._toggle_show_hidden_index(), win._theme_count())
        self.assertEqual(win._toggle_wrap_index(), win._theme_count() + 1)
        self.assertEqual(win._toggle_sunday_first_index(), win._theme_count() + 2)
        self.assertEqual(win._toggle_show_welcome_index(), win._theme_count() + 3)
        self.assertEqual(win._edit_hidden_icons_index(), win._theme_count() + 4)
        self.assertEqual(win._save_index(), win._theme_count() + 5)
        self.assertEqual(win._cancel_index(), win._theme_count() + 6)

        win._selection = 1
        self.assertIsNone(win._activate_selection())
        self.assertEqual(win.theme_name, win._themes[1].key)
        win.app.apply_theme.assert_called()

        win._selection = win._toggle_show_hidden_index()
        self.assertIsNone(win._activate_selection())
        self.assertTrue(win.show_hidden)

        win._selection = win._toggle_wrap_index()
        self.assertIsNone(win._activate_selection())
        self.assertTrue(win.word_wrap_default)

    def test_activate_save_and_cancel_paths(self):
        win = self._make_window()
        win.theme_name = "hacker"
        win.show_hidden = True
        win.word_wrap_default = True
        win._selection = win._save_index()
        save_result = win._activate_selection()
        self.assertEqual(save_result.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(save_result.payload, self.actions_mod.AppAction.CLOSE_WINDOW)
        win.app.persist_config.assert_called_once_with()

        win2 = self._make_window()
        win2.theme_name = "amiga"
        win2.show_hidden = True
        win2.word_wrap_default = True
        win2._selection = win2._cancel_index()
        cancel_result = win2._activate_selection()
        self.assertEqual(cancel_result.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(cancel_result.payload, self.actions_mod.AppAction.CLOSE_WINDOW)
        self.assertEqual(win2.theme_name, "win31")
        self.assertFalse(win2.show_hidden)
        self.assertFalse(win2.word_wrap_default)

    def test_activate_save_failure_and_fallback_branch(self):
        win = self._make_window()
        win.app.persist_config = mock.Mock(side_effect=OSError("disk full"))
        win._selection = win._save_index()
        result = win._activate_selection()
        self.assertEqual(result.type, self.actions_mod.ActionType.SAVE_ERROR)
        self.assertIn("disk full", result.payload)
        self.assertFalse(win._committed)

        win._selection = 999
        self.assertIsNone(win._activate_selection())

    def test_apply_runtime_and_revert_runtime(self):
        win = self._make_window()
        win.theme_name = "hacker"
        win.show_hidden = True
        win.word_wrap_default = True

        win._apply_runtime()
        self.assertEqual(win.app.theme_name, "hacker")
        self.assertTrue(win.app.default_show_hidden)
        self.assertTrue(win.app.default_word_wrap)

        win._revert_runtime()
        self.assertEqual(win.theme_name, "win31")
        self.assertFalse(win.show_hidden)
        self.assertFalse(win.word_wrap_default)

    def test_draw_visibility_and_state_layout(self):
        win = self._make_window()
        win.visible = False
        with mock.patch.object(self.settings_mod, "safe_addstr") as safe_addstr:
            win.draw(None)
        safe_addstr.assert_not_called()

        win.visible = True
        win.draw_frame = mock.Mock(return_value=7)
        with mock.patch.object(self.settings_mod, "safe_addstr") as safe_addstr:
            win.draw(types.SimpleNamespace())
        self.assertGreater(safe_addstr.call_count, 0)
        self.assertEqual(len(win._control_rows), win._controls_count())
        self.assertIn(win._save_index(), win._button_bounds)
        self.assertIn(win._cancel_index(), win._button_bounds)

    def test_handle_key_paths(self):
        win = self._make_window()

        self.assertIsNone(win.handle_key("xx"))  # normalize_key_code -> None

        win._selection = 0
        self.assertIsNone(win.handle_key(self.curses.KEY_UP))
        self.assertEqual(win._selection, win._controls_count() - 1)

        self.assertIsNone(win.handle_key(self.curses.KEY_DOWN))
        self.assertEqual(win._selection, 0)

        win._selection = 1
        with mock.patch.object(win, "_activate_selection", return_value="theme-left") as activate:
            self.assertEqual(win.handle_key(self.curses.KEY_LEFT), "theme-left")
        activate.assert_called_once_with()

        win._selection = win._toggle_show_hidden_index()
        win.show_hidden = True
        self.assertIsNone(win.handle_key(self.curses.KEY_LEFT))
        self.assertFalse(win.show_hidden)

        win._selection = win._toggle_wrap_index()
        win.word_wrap_default = True
        self.assertIsNone(win.handle_key(self.curses.KEY_LEFT))
        self.assertFalse(win.word_wrap_default)

        win._selection = 0
        with mock.patch.object(win, "_activate_selection", return_value="theme-right") as activate:
            self.assertEqual(win.handle_key(self.curses.KEY_RIGHT), "theme-right")
        activate.assert_called_once_with()

        win._selection = win._toggle_show_hidden_index()
        win.show_hidden = False
        self.assertIsNone(win.handle_key(self.curses.KEY_RIGHT))
        self.assertTrue(win.show_hidden)

        win._selection = win._toggle_wrap_index()
        win.word_wrap_default = False
        self.assertIsNone(win.handle_key(self.curses.KEY_RIGHT))
        self.assertTrue(win.word_wrap_default)

        with mock.patch.object(win, "_activate_selection", return_value="enter") as activate:
            self.assertEqual(win.handle_key(10), "enter")
        activate.assert_called_once_with()

        self.assertIsNone(win.handle_key(ord("a")))

    def test_handle_click_and_close_paths(self):
        win = self._make_window()
        win.draw_frame = mock.Mock(return_value=3)
        with mock.patch.object(self.settings_mod, "safe_addstr"):
            win.draw(types.SimpleNamespace())

        any_control_idx, any_row = next(iter(win._control_rows.items()))
        with mock.patch.object(win, "_activate_selection", return_value="row-hit") as activate:
            result = win.handle_click(5, any_row)
        self.assertEqual(result, "row-hit")
        self.assertEqual(win._selection, any_control_idx)
        activate.assert_called_once_with()

        save_idx = win._save_index()
        x0, _, row = win._button_bounds[save_idx]
        with mock.patch.object(win, "_activate_selection", return_value="button-hit") as activate:
            result = win.handle_click(x0, row)
        self.assertEqual(result, "button-hit")
        self.assertEqual(win._selection, save_idx)
        activate.assert_called_once_with()

        self.assertIsNone(win.handle_click(-1, -1))

        win2 = self._make_window()
        with mock.patch.object(win2, "_revert_runtime") as revert:
            win2.close()
        revert.assert_called_once_with()
        self.assertTrue(win2._committed)

        win3 = self._make_window()
        win3._committed = True
        with mock.patch.object(win3, "_revert_runtime") as revert:
            win3.close()
        revert.assert_not_called()


if __name__ == "__main__":
    unittest.main()

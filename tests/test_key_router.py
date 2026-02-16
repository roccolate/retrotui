import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_F10 = 266
    return fake


class KeyRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.utils",
            "retrotui.core.actions",
            "retrotui.core.key_router",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.key_router = importlib.import_module("retrotui.core.key_router")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.utils",
            "retrotui.core.actions",
            "retrotui.core.key_router",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_app(self):
        return types.SimpleNamespace(
            menu=types.SimpleNamespace(
                active=False,
                selected_menu=4,
                selected_item=7,
                handle_key=mock.Mock(return_value=None),
            ),
            windows=[],
            get_active_window=mock.Mock(return_value=None),
            execute_action=mock.Mock(),
            _dispatch_window_result=mock.Mock(),
            _handle_dialog_key=mock.Mock(return_value=False),
            _handle_menu_hotkeys=mock.Mock(return_value=False),
            _handle_global_menu_key=mock.Mock(return_value=False),
            _cycle_focus=mock.Mock(),
            _handle_active_window_key=mock.Mock(),
        )

    def test_normalize_app_key_maps_newline_string(self):
        self.assertEqual(self.key_router.normalize_app_key("\n"), 10)

    def test_handle_menu_hotkeys_none_returns_false(self):
        app = self._make_app()
        self.assertFalse(self.key_router.handle_menu_hotkeys(app, None))

    def test_handle_menu_hotkeys_f10_toggles_global_menu(self):
        app = self._make_app()

        handled = self.key_router.handle_menu_hotkeys(app, self.curses.KEY_F10)

        self.assertTrue(handled)
        self.assertTrue(app.menu.active)
        self.assertEqual(app.menu.selected_menu, 0)
        self.assertEqual(app.menu.selected_item, 0)

    def test_handle_menu_hotkeys_f10_closes_global_menu_when_already_active(self):
        app = self._make_app()
        app.menu.active = True

        handled = self.key_router.handle_menu_hotkeys(app, self.curses.KEY_F10)

        self.assertTrue(handled)
        self.assertFalse(app.menu.active)

    def test_handle_menu_hotkeys_f10_toggles_window_menu(self):
        app = self._make_app()
        window_menu = types.SimpleNamespace(active=False, selected_menu=9, selected_item=9)
        app.get_active_window.return_value = types.SimpleNamespace(window_menu=window_menu)

        first = self.key_router.handle_menu_hotkeys(app, self.curses.KEY_F10)
        second = self.key_router.handle_menu_hotkeys(app, self.curses.KEY_F10)

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertFalse(window_menu.active)

    def test_handle_menu_hotkeys_escape_closes_window_menu_first(self):
        app = self._make_app()
        window_menu = types.SimpleNamespace(active=True, selected_menu=2, selected_item=5)
        app.get_active_window.return_value = types.SimpleNamespace(window_menu=window_menu)
        app.menu.active = True

        handled = self.key_router.handle_menu_hotkeys(app, 27)

        self.assertTrue(handled)
        self.assertFalse(window_menu.active)
        self.assertTrue(app.menu.active)

    def test_handle_menu_hotkeys_escape_closes_global_menu(self):
        app = self._make_app()
        app.menu.active = True

        handled = self.key_router.handle_menu_hotkeys(app, 27)

        self.assertTrue(handled)
        self.assertFalse(app.menu.active)

    def test_handle_global_menu_key_executes_selected_action(self):
        app = self._make_app()
        app.menu.active = True
        app.menu.handle_key.return_value = self.actions_mod.AppAction.ABOUT

        handled = self.key_router.handle_global_menu_key(app, 10)

        self.assertTrue(handled)
        app.menu.handle_key.assert_called_once_with(10)
        app.execute_action.assert_called_once_with(self.actions_mod.AppAction.ABOUT)

    def test_handle_global_menu_key_returns_false_when_inactive(self):
        app = self._make_app()
        app.menu.active = False

        handled = self.key_router.handle_global_menu_key(app, 10)

        self.assertFalse(handled)
        app.menu.handle_key.assert_not_called()

    def test_handle_global_menu_key_none_is_consumed(self):
        app = self._make_app()
        app.menu.active = True

        handled = self.key_router.handle_global_menu_key(app, None)

        self.assertTrue(handled)
        app.menu.handle_key.assert_not_called()

    def test_cycle_focus_skips_hidden_windows(self):
        app = self._make_app()
        win_a = types.SimpleNamespace(visible=True, active=True)
        win_b = types.SimpleNamespace(visible=False, active=False)
        win_c = types.SimpleNamespace(visible=True, active=False)
        app.windows = [win_a, win_b, win_c]

        self.key_router.cycle_focus(app)

        self.assertFalse(win_a.active)
        self.assertFalse(win_b.active)
        self.assertTrue(win_c.active)

    def test_cycle_focus_no_visible_windows(self):
        app = self._make_app()
        app.windows = [types.SimpleNamespace(visible=False, active=True)]
        self.key_router.cycle_focus(app)
        self.assertTrue(app.windows[0].active)

    def test_handle_active_window_key_dispatches_result(self):
        app = self._make_app()
        active = types.SimpleNamespace(handle_key=mock.Mock(return_value="result"))
        app.get_active_window.return_value = active

        self.key_router.handle_active_window_key(app, "k")

        active.handle_key.assert_called_once_with("k")
        app._dispatch_window_result.assert_called_once_with("result", active)

    def test_handle_active_window_key_no_active_window(self):
        app = self._make_app()
        app.get_active_window.return_value = None
        self.key_router.handle_active_window_key(app, "x")
        app._dispatch_window_result.assert_not_called()

    def test_handle_key_event_dialog_has_priority(self):
        app = self._make_app()
        app._handle_dialog_key.return_value = True

        self.key_router.handle_key_event(app, "x")

        app.execute_action.assert_not_called()
        app._handle_menu_hotkeys.assert_not_called()
        app._handle_global_menu_key.assert_not_called()
        app._cycle_focus.assert_not_called()
        app._handle_active_window_key.assert_not_called()

    def test_handle_key_event_ctrl_q_exits_early(self):
        app = self._make_app()

        self.key_router.handle_key_event(app, 17)

        app.execute_action.assert_called_once_with(self.actions_mod.AppAction.EXIT)
        app._handle_menu_hotkeys.assert_not_called()
        app._handle_global_menu_key.assert_not_called()
        app._cycle_focus.assert_not_called()
        app._handle_active_window_key.assert_not_called()

    def test_handle_key_event_tab_cycles_focus(self):
        app = self._make_app()

        self.key_router.handle_key_event(app, 9)

        app._cycle_focus.assert_called_once_with()
        app._handle_active_window_key.assert_not_called()

    def test_handle_key_event_menu_hotkeys_short_circuit(self):
        app = self._make_app()
        app._handle_menu_hotkeys.return_value = True

        self.key_router.handle_key_event(app, "x")

        app._handle_global_menu_key.assert_not_called()
        app._cycle_focus.assert_not_called()
        app._handle_active_window_key.assert_not_called()

    def test_handle_key_event_global_menu_short_circuit(self):
        app = self._make_app()
        app._handle_global_menu_key.return_value = True

        self.key_router.handle_key_event(app, "x")

        app._cycle_focus.assert_not_called()
        app._handle_active_window_key.assert_not_called()

    def test_handle_key_event_falls_back_to_active_window(self):
        app = self._make_app()

        self.key_router.handle_key_event(app, "z")

        app._handle_active_window_key.assert_called_once_with("z")


if __name__ == "__main__":
    unittest.main()

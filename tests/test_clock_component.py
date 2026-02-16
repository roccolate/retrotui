import importlib
import sys
import types
import unittest
from datetime import datetime
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.A_BOLD = 1
    fake.error = Exception
    fake.color_pair = lambda value: value * 10
    fake.beep = mock.Mock()
    return fake


class ClockComponentTests(unittest.TestCase):
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
            "retrotui.apps.clock",
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.clock_mod = importlib.import_module("retrotui.apps.clock")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.window",
            "retrotui.ui.menu",
            "retrotui.core.actions",
            "retrotui.apps.clock",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_window(self):
        return self.clock_mod.ClockCalendarWindow(0, 0, 34, 14)

    def test_toggle_top_and_chime_with_keys(self):
        win = self._make_window()
        self.assertTrue(win.always_on_top)
        self.assertFalse(win.chime_enabled)
        self.assertFalse(win.week_starts_sunday)

        win.handle_key(ord("t"))
        win.handle_key(ord("b"))
        win.handle_key(ord("s"))

        self.assertFalse(win.always_on_top)
        self.assertTrue(win.chime_enabled)
        self.assertTrue(win.week_starts_sunday)

    def test_close_key_returns_close_action(self):
        win = self._make_window()

        result = win.handle_key(ord("q"))

        self.assertEqual(result.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(result.payload, self.actions_mod.AppAction.CLOSE_WINDOW)

    def test_maybe_chime_only_once_per_hour(self):
        win = self._make_window()
        win.chime_enabled = True
        self.curses.beep.reset_mock()
        now = datetime(2026, 2, 16, 10, 0, 1)

        win._maybe_chime(now)
        win._maybe_chime(now)

        self.curses.beep.assert_called_once_with()

    def test_draw_renders_clock_calendar_and_status(self):
        win = self._make_window()
        fixed_now = datetime(2026, 2, 16, 10, 15, 30)

        with (
            mock.patch.object(win, "draw_frame", return_value=0),
            mock.patch.object(self.clock_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(self.clock_mod, "theme_attr", return_value=0),
            mock.patch.object(self.clock_mod, "datetime") as fake_datetime,
        ):
            fake_datetime.now.return_value = fixed_now
            win.draw(None)

        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("10:15:30" in text for text in rendered))
        self.assertTrue(any("February 2026" in text for text in rendered))
        self.assertTrue(any("top:" in text for text in rendered))
        self.assertTrue(any("week:" in text for text in rendered))

    def test_month_lines_respect_first_weekday_toggle(self):
        win = self._make_window()
        now = datetime(2026, 2, 16, 10, 15, 30)

        monday_lines = win._month_lines(now)
        self.assertTrue(any(line.strip().startswith("Mo Tu") for line in monday_lines))

        win.week_starts_sunday = True
        sunday_lines = win._month_lines(now)
        self.assertTrue(any(line.strip().startswith("Su Mo") for line in sunday_lines))


if __name__ == "__main__":
    unittest.main()

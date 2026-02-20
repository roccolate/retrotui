import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.A_BOLD = 1
    fake.color_pair = lambda value: value * 10
    fake.error = Exception
    return fake


class RenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.core.rendering",
        ):
            sys.modules.pop(mod_name, None)

        cls.rendering = importlib.import_module("retrotui.core.rendering")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.core.rendering",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_draw_desktop_renders_each_body_row(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(10, 40)))
        app = types.SimpleNamespace(stdscr=stdscr)

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_desktop(app)

        self.assertEqual(safe_addstr.call_count, 8)
        first_call = safe_addstr.call_args_list[0].args
        self.assertEqual(first_call[1], 1)
        self.assertEqual(first_call[2], 0)
        self.assertEqual(len(first_call[3]), 39)
        self.assertEqual(
            first_call[4], self.curses.color_pair(self.rendering.C_DESKTOP)
        )

    def test_draw_icons_uses_selected_and_normal_colors(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 80)))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            selected_icon=1,
            icons=[
                {"art": ["[]"], "label": "A"},
                {"art": ["[]"], "label": "B"},
            ],
            get_icon_screen_pos=lambda idx: (3, 3 + idx * 5),
        )
        selected_attr = self.curses.color_pair(self.rendering.C_ICON_SEL) | self.curses.A_BOLD
        normal_attr = self.curses.color_pair(self.rendering.C_ICON)

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_icons(app)

        self.assertTrue(
            any(
                call.args[1] == 3 and call.args[3] == "[]" and call.args[4] == normal_attr
                for call in safe_addstr.call_args_list
            )
        )
        self.assertTrue(
            any(
                call.args[1] == 8 and call.args[3] == "[]" and call.args[4] == selected_attr
                for call in safe_addstr.call_args_list
            )
        )

    def test_draw_icons_stops_when_vertical_space_exhausted(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(6, 80)))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            selected_icon=-1,
            icons=[{"art": ["[]"], "label": "A"}],
            get_icon_screen_pos=lambda idx: (3, 3),
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_icons(app)

        safe_addstr.assert_not_called()

    def test_draw_taskbar_no_minimized_windows_no_output(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 80)))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=[types.SimpleNamespace(minimized=False, title="Main")],
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_taskbar(app)

        safe_addstr.assert_not_called()

    def test_draw_taskbar_renders_buttons_for_minimized_windows(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 80)))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=[
                types.SimpleNamespace(minimized=True, title="Notes"),
                types.SimpleNamespace(minimized=False, title="Shell"),
                types.SimpleNamespace(minimized=True, title="Files"),
            ],
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_taskbar(app)

        self.assertGreaterEqual(safe_addstr.call_count, 3)
        self.assertTrue(any("[Notes]" in call.args[3] for call in safe_addstr.call_args_list))
        self.assertTrue(any("[Files]" in call.args[3] for call in safe_addstr.call_args_list))

    def test_draw_taskbar_breaks_when_button_does_not_fit(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 10)))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=[types.SimpleNamespace(minimized=True, title="VeryLongTitleForTaskbar")],
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_taskbar(app)

        # Background row is drawn, but oversized button is skipped.
        self.assertEqual(safe_addstr.call_count, 1)

    def test_draw_statusbar_includes_version_and_window_counts(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 80)))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=[
                types.SimpleNamespace(visible=True),
                types.SimpleNamespace(visible=False),
            ],
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_statusbar(app, "0.3.4")

        self.assertGreaterEqual(safe_addstr.call_count, 1)
        # Find the call that contains the status text
        all_text = "".join(str(call.args[3]) for call in safe_addstr.call_args_list if len(call.args) > 3)
        self.assertIn("v0.3.4", all_text)
        self.assertIn("Windows: 1/2", all_text)


if __name__ == "__main__":
    unittest.main()

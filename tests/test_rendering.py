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
        cls.constants = importlib.import_module("retrotui.constants")
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

        self.assertEqual(safe_addstr.call_count, 9)
        first_call = safe_addstr.call_args_list[0].args
        self.assertEqual(first_call[1], 1)
        self.assertEqual(first_call[2], 0)
        self.assertEqual(len(first_call[3]), 40)
        self.assertEqual(
            first_call[4], self.curses.color_pair(self.rendering.C_DESKTOP)
        )
        last_call = safe_addstr.call_args_list[-1].args
        self.assertEqual(last_call[1], 9)

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

    def test_draw_icons_prefers_symbol_when_present(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 80)))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            selected_icon=-1,
            icons=[{"symbol": "[D]", "art": ["[]"], "label": "Files"}],
            get_icon_screen_pos=lambda idx: (3, 3),
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_icons(app)

        self.assertTrue(any(call.args[3] == "[D]" for call in safe_addstr.call_args_list))
        self.assertFalse(any(call.args[3] == "[]" for call in safe_addstr.call_args_list))

    def test_draw_taskbar_no_minimized_windows_no_output(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 80)))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=[types.SimpleNamespace(minimized=False, title="Main")],
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_taskbar(app)

        self.assertEqual(safe_addstr.call_count, 0)

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

        self.assertGreaterEqual(safe_addstr.call_count, 2)
        self.assertTrue(any("[Notes]" in call.args[3] for call in safe_addstr.call_args_list))
        self.assertTrue(any("[Files]" in call.args[3] for call in safe_addstr.call_args_list))

    def test_draw_taskbar_uses_unified_top_bar_free_space(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 80)))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=[types.SimpleNamespace(minimized=True, title="Notes")],
            menu=types.SimpleNamespace(
                menu_items_right_x=mock.Mock(return_value=20),
                right_reserved_start_x=mock.Mock(return_value=70),
            ),
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_taskbar(app)

        self.assertTrue(
            any(
                call.args[1] == 0
                and call.args[2] == 22
                and call.args[3] == "[Notes]"
                and call.args[4]
                == (self.curses.color_pair(self.constants.C_MENUBAR) | self.curses.A_BOLD)
                for call in safe_addstr.call_args_list
            )
        )

    def test_draw_taskbar_uses_window_manager_taskbar_layout_when_available(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 80)))
        window_mgr = types.SimpleNamespace(
            taskbar_buttons=mock.Mock(
                return_value=((1, 8, "Notes", object()), (10, 17, "Files", object()))
            )
        )
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=[types.SimpleNamespace(minimized=True, title="Legacy")],
            window_mgr=window_mgr,
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_taskbar(app)

        window_mgr.taskbar_buttons.assert_called_once_with(80, start_x=1, end_x=80)
        self.assertTrue(any(call.args[2] == 1 and call.args[3] == "[Notes]" for call in safe_addstr.call_args_list))
        self.assertTrue(any(call.args[2] == 10 and call.args[3] == "[Files]" for call in safe_addstr.call_args_list))

    def test_draw_taskbar_breaks_when_button_does_not_fit(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 10)))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=[types.SimpleNamespace(minimized=True, title="VeryLongTitleForTaskbar")],
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_taskbar(app)

        self.assertEqual(safe_addstr.call_count, 0)

    def test_draw_statusbar_is_noop_without_bottom_bar(self):
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

        safe_addstr.assert_not_called()

    def test_draw_statusbar_noop_uses_no_terminal_query_with_explicit_frame_size(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(side_effect=AssertionError("unexpected getmaxyx call")))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=[types.SimpleNamespace(visible=True)],
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_statusbar(app, "0.3.4", frame_size=(20, 80))

        stdscr.getmaxyx.assert_not_called()
        safe_addstr.assert_not_called()

    def test_draw_statusbar_noop_does_not_read_window_manager_stats(self):
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 80)))
        window_mgr = types.SimpleNamespace(
            window_stats=mock.Mock(
                return_value={
                    "total": 3,
                    "visible": 2,
                    "minimized_labels": ("Notes",),
                }
            )
        )
        app = types.SimpleNamespace(
            stdscr=stdscr,
            window_mgr=window_mgr,
        )

        with mock.patch.object(self.rendering, "safe_addstr") as safe_addstr:
            self.rendering.draw_statusbar(app, "0.3.4")

        window_mgr.window_stats.assert_not_called()
        safe_addstr.assert_not_called()

    def test_taskbar_draw_uses_window_stats_cache_per_render_cycle(self):
        class _CountingWindows(list):
            def __init__(self, *items):
                super().__init__(items)
                self.iter_calls = 0

            def __iter__(self):
                self.iter_calls += 1
                return super().__iter__()

        windows = _CountingWindows(
            types.SimpleNamespace(minimized=True, title="Notes", visible=False),
            types.SimpleNamespace(minimized=False, title="Shell", visible=True),
        )
        stdscr = types.SimpleNamespace(getmaxyx=mock.Mock(return_value=(20, 80)))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=windows,
            _render_cycle_id=7,
        )

        with mock.patch.object(self.rendering, "safe_addstr"):
            self.rendering.draw_taskbar(app)
            self.rendering.draw_statusbar(app, "0.9.5")

        self.assertEqual(windows.iter_calls, 1)


if __name__ == "__main__":
    unittest.main()

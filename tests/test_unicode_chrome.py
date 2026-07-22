import unittest
from types import SimpleNamespace
from unittest import mock

from retrotui.constants import TASKBAR_TITLE_MAX_LEN
from retrotui.core.window_manager import WindowManager
from retrotui.ui.window import Window
from retrotui.utils import clip_text_columns, text_display_width


class UnicodeChromeTests(unittest.TestCase):
    def test_display_width_handles_wide_combining_and_emoji_text(self):
        self.assertEqual(text_display_width("A你"), 3)
        self.assertEqual(text_display_width("e\u0301"), 1)
        self.assertEqual(text_display_width("🙂"), 2)

    def test_display_width_uses_safe_fallback_for_unprintable_text(self):
        self.assertEqual(text_display_width("A\x01B"), 3)

    def test_clip_text_columns_preserves_physical_width_contract(self):
        self.assertEqual(clip_text_columns("你你", 3, suffix="…"), "你…")
        self.assertEqual(clip_text_columns("e\u0301x", 2, suffix="…"), "e\u0301x")
        self.assertEqual(clip_text_columns("🙂🙂", 3, suffix="…"), "🙂…")
        self.assertLessEqual(text_display_width(clip_text_columns("你你你", 4, suffix="…")), 4)

    def test_clip_text_columns_handles_zero_and_suffix_only_budgets(self):
        self.assertEqual(clip_text_columns("abc", 0, suffix="…"), "")
        self.assertEqual(clip_text_columns("你", 1, suffix="…"), "…")

    def test_window_title_stays_inside_reserved_title_columns(self):
        win = Window("你你你你", 0, 1, 18, 6)
        win.active = True
        safe_addstr = mock.Mock()
        draw_globals = Window.draw_frame.__globals__

        with mock.patch.dict(
            draw_globals,
            {
                "draw_box": mock.Mock(),
                "theme_attr": mock.Mock(return_value=0),
                "safe_addstr": safe_addstr,
            },
        ):
            win.draw_frame(SimpleNamespace(), frame_size=(24, 80))

        title_call = next(
            call
            for call in safe_addstr.call_args_list
            if call.args[1] == win.y and call.args[2] == win.x + 2
        )
        rendered_title = title_call.args[3]
        max_title_columns = max(0, win.w - win.MIN_BTN_OFFSET - 4)
        self.assertLessEqual(
            text_display_width(rendered_title.strip()),
            max_title_columns,
        )

    def test_taskbar_button_ranges_follow_physical_columns(self):
        app = SimpleNamespace(stdscr=SimpleNamespace(getmaxyx=lambda: (20, 80)))
        manager = WindowManager(app)
        wide = SimpleNamespace(minimized=True, visible=False, title="你你")
        manager.windows = [wide]

        button = manager.taskbar_buttons(80)[0]
        start_x, end_x, label, _win = button
        self.assertEqual(end_x - start_x, text_display_width(label) + 2)
        self.assertEqual(end_x - start_x, 6)

    def test_taskbar_label_clips_to_configured_column_budget(self):
        app = SimpleNamespace(stdscr=SimpleNamespace(getmaxyx=lambda: (20, 120)))
        manager = WindowManager(app)
        wide = SimpleNamespace(
            minimized=True,
            visible=False,
            title="你" * (TASKBAR_TITLE_MAX_LEN + 4),
        )
        manager.windows = [wide]

        _start, _end, label, _win = manager.taskbar_buttons(120)[0]
        self.assertLessEqual(text_display_width(label), TASKBAR_TITLE_MAX_LEN)
        self.assertTrue(label.endswith("…"))


if __name__ == "__main__":
    unittest.main()

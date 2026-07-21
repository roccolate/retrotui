#!/usr/bin/env python3
"""Apply the focused Unicode window chrome cut exactly once."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, *, path: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}, found {count}: {old!r}")
    return text.replace(old, new, 1)


def update_utils() -> None:
    path = "retrotui/utils.py"
    text = read(path)
    text = replace_once(
        text,
        "import locale\nfrom .constants import (",
        "import locale\nfrom wcwidth import wcwidth, wcswidth\nfrom .constants import (",
        path=path,
    )
    marker = """def safe_addstr(win, y, x, text, attr=0, *, _bounds=None):
"""
    helpers = '''def text_display_width(text) -> int:
    """Return the physical terminal-column width of arbitrary UI text."""
    value = str(text or "")
    width = wcswidth(value)
    if width >= 0:
        return width

    # Preserve safe layout even when a title contains an unprintable codepoint.
    total = 0
    for ch in value:
        ch_width = wcwidth(ch)
        total += ch_width if ch_width >= 0 else 1
    return total


def clip_text_columns(text, max_columns, *, suffix="") -> str:
    """Clip text to physical terminal columns without splitting combining text."""
    value = str(text or "")
    columns = max(0, int(max_columns))
    if columns <= 0:
        return ""
    if text_display_width(value) <= columns:
        return value

    suffix_value = str(suffix or "")
    suffix_width = text_display_width(suffix_value)
    if suffix_width > columns:
        suffix_value = ""
        suffix_width = 0
    content_limit = columns - suffix_width

    clipped = ""
    for ch in value:
        candidate = clipped + ch
        if text_display_width(candidate) > content_limit:
            break
        clipped = candidate
    return clipped + suffix_value


'''
    text = replace_once(text, marker, helpers + marker, path=path)
    write(path, text)


def update_window() -> None:
    path = "retrotui/ui/window.py"
    text = read(path)
    text = replace_once(
        text,
        "from ..utils import safe_addstr, draw_box, theme_attr",
        "from ..utils import clip_text_columns, safe_addstr, draw_box, theme_attr",
        path=path,
    )
    old = '''        max_title_len = max(0, self.w - self.MIN_BTN_OFFSET - 4)
        display_title = self.title
        if len(display_title) > max_title_len:
            display_title = display_title[:max_title_len-1] + "…"
'''
    new = '''        max_title_columns = max(0, self.w - self.MIN_BTN_OFFSET - 4)
        display_title = clip_text_columns(
            self.title,
            max_title_columns,
            suffix="…",
        )
'''
    text = replace_once(text, old, new, path=path)
    write(path, text)


def update_window_manager() -> None:
    path = "retrotui/core/window_manager.py"
    text = read(path)
    text = replace_once(
        text,
        "from ..constants import TASKBAR_TITLE_MAX_LEN, BOTTOM_BARS_HEIGHT\n",
        "from ..constants import TASKBAR_TITLE_MAX_LEN, BOTTOM_BARS_HEIGHT\nfrom ..utils import clip_text_columns, text_display_width\n",
        path=path,
    )
    text = replace_once(
        text,
        '                label = str(getattr(win, "title", ""))[:TASKBAR_TITLE_MAX_LEN]\n',
        '                label = clip_text_columns(\n                    getattr(win, "title", ""),\n                    TASKBAR_TITLE_MAX_LEN,\n                    suffix="…",\n                )\n',
        path=path,
    )
    text = replace_once(
        text,
        "            btn_w = len(label) + 2  # [label]\n",
        "            btn_w = text_display_width(label) + 2  # [label]\n",
        path=path,
    )
    write(path, text)


def add_tests() -> None:
    path = "tests/test_unicode_chrome.py"
    if (ROOT / path).exists():
        raise RuntimeError(f"{path} already exists")
    write(
        path,
        '''import unittest
from types import SimpleNamespace
from unittest import mock

from retrotui.constants import TASKBAR_TITLE_MAX_LEN
from retrotui.core.window_manager import WindowManager
from retrotui.ui.window import Window
from retrotui.utils import clip_text_columns, text_display_width


class UnicodeChromeTests(unittest.TestCase):
    def test_display_width_handles_wide_combining_and_emoji_text(self):
        self.assertEqual(text_display_width("A你"), 3)
        self.assertEqual(text_display_width("e\\u0301"), 1)
        self.assertEqual(text_display_width("🙂"), 2)

    def test_clip_text_columns_preserves_physical_width_contract(self):
        self.assertEqual(clip_text_columns("你你", 3, suffix="…"), "你…")
        self.assertEqual(clip_text_columns("e\\u0301x", 2, suffix="…"), "e\\u0301x")
        self.assertEqual(clip_text_columns("🙂🙂", 3, suffix="…"), "🙂…")
        self.assertLessEqual(text_display_width(clip_text_columns("你你你", 4, suffix="…")), 4)

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
''',
    )


def main() -> None:
    update_utils()
    update_window()
    update_window_manager()
    add_tests()


if __name__ == "__main__":
    main()

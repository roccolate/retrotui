#!/usr/bin/env python3
"""Apply the focused Unicode menus and dialogs cut exactly once."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def replace_exact(text: str, old: str, new: str, *, path: str, count: int = 1) -> str:
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(
            f"expected {count} match(es) in {path}, found {actual}: {old!r}"
        )
    return text.replace(old, new, count)


def update_utils() -> None:
    path = "retrotui/utils.py"
    text = read(path)
    marker = '''    return clipped + suffix_value


def safe_addstr(win, y, x, text, attr=0, *, _bounds=None):
'''
    replacement = '''    return clipped + suffix_value


def pad_text_columns(text, columns, *, suffix="") -> str:
    """Clip and right-pad text to an exact physical terminal-column width."""
    width = max(0, int(columns))
    fitted = clip_text_columns(text, width, suffix=suffix)
    return fitted + (" " * max(0, width - text_display_width(fitted)))


def safe_addstr(win, y, x, text, attr=0, *, _bounds=None):
'''
    text = replace_exact(text, marker, replacement, path=path)
    write(path, text)


def update_menu() -> None:
    path = "retrotui/ui/menu.py"
    text = read(path)
    text = replace_exact(
        text,
        "from ..utils import draw_box, safe_addstr, theme_attr",
        "from ..utils import (\n    draw_box,\n    pad_text_columns,\n    safe_addstr,\n    text_display_width,\n    theme_attr,\n)",
        path=path,
    )
    text = replace_exact(
        text,
        "            x += len(name) + 3\n",
        "            x += text_display_width(name) + 3\n",
        path=path,
    )
    text = replace_exact(
        text,
        "        return positions[last_idx] + len(self.menu_names[last_idx]) + 2\n",
        "        return positions[last_idx] + text_display_width(self.menu_names[last_idx]) + 2\n",
        path=path,
    )
    text = replace_exact(
        text,
        "            if pos <= mx < pos + len(name) + 2:\n",
        "            if pos <= mx < pos + text_display_width(name) + 2:\n",
        path=path,
        count=3,
    )
    text = replace_exact(
        text,
        "        max_item_len = max((len(label) for label, _ in full_items), default=0)\n        dropdown_w = max_item_len + 4\n",
        "        max_item_columns = max(\n            (text_display_width(label) for label, _ in full_items),\n            default=0,\n        )\n        dropdown_w = max_item_columns + 4\n",
        path=path,
    )
    text = replace_exact(
        text,
        "            menu_right = positions[last_idx] + len(self.menu_names[last_idx]) + 2\n",
        "            menu_right = (\n                positions[last_idx]\n                + text_display_width(self.menu_names[last_idx])\n                + 2\n            )\n",
        path=path,
    )
    old_row = '''                safe_addstr(
                    stdscr,
                    y + 1 + i,
                    x,
                    f' {label.ljust(dropdown_w - 2)} ',
                    attr,
                    _bounds=frame_size,
                )
'''
    new_row = '''                row_label = pad_text_columns(
                    label,
                    max(0, dropdown_w - 2),
                    suffix="…",
                )
                safe_addstr(
                    stdscr,
                    y + 1 + i,
                    x,
                    f' {row_label} ',
                    attr,
                    _bounds=frame_size,
                )
'''
    text = replace_exact(text, old_row, new_row, path=path)
    write(path, text)


def update_dialog() -> None:
    path = "retrotui/ui/dialog.py"
    text = read(path)
    text = replace_exact(
        text,
        "from ..utils import safe_addstr, draw_box, normalize_key_code, theme_attr",
        "from ..utils import (\n    clip_text_columns,\n    draw_box,\n    normalize_key_code,\n    pad_text_columns,\n    safe_addstr,\n    text_display_width,\n    theme_attr,\n)",
        path=path,
    )

    wrap_start = text.index("def _wrap_dialog_message(message, inner_w):")
    wrap_end = text.index("\n\nclass Dialog:", wrap_start)
    new_wrap = '''def _wrap_dialog_message(message, inner_w):
    """Word-wrap a dialog message by physical terminal columns."""
    columns = max(1, int(inner_w))
    lines = []
    for paragraph in str(message).split("\\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue

        line = ""
        for original_word in words:
            word = original_word
            while text_display_width(word) > columns:
                if line:
                    lines.append(line)
                    line = ""
                chunk = clip_text_columns(word, columns)
                if not chunk:
                    chunk = word[0]
                lines.append(chunk)
                word = word[len(chunk):]

            if not word:
                continue
            candidate = f"{line} {word}" if line else word
            if text_display_width(candidate) <= columns:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
    return lines or [""]
'''
    text = text[:wrap_start] + new_wrap + text[wrap_end:]

    text = replace_exact(
        text,
        "        self.width = max(20, max(width, len(title) + 8))\n",
        "        button_columns = sum(\n            text_display_width(button) + 4 for button in self.buttons\n        ) + max(0, len(self.buttons) - 1) * 2\n        self.width = max(\n            20,\n            int(width),\n            text_display_width(title) + 8,\n            button_columns + 4,\n        )\n",
        path=path,
    )

    old_title = '''        # Title
        title_text = f' {self.title} '
        safe_addstr(
            stdscr,
            y,
            x + 1,
            title_text.ljust(self.width - 2),
            title_attr,
            _bounds=frame_size,
        )
'''
    new_title = '''        # Title
        display_title = clip_text_columns(
            self.title,
            max(0, self.width - 4),
            suffix="…",
        )
        title_text = pad_text_columns(f' {display_title} ', self.width - 2)
        safe_addstr(
            stdscr,
            y,
            x + 1,
            title_text,
            title_attr,
            _bounds=frame_size,
        )
'''
    text = replace_exact(text, old_title, new_title, path=path)

    text = replace_exact(
        text,
        "        total_btn_width = sum(len(b) + 6 for b in self.buttons) + (len(self.buttons) - 1) * 2\n",
        "        button_widths = [text_display_width(button) + 4 for button in self.buttons]\n        total_btn_width = sum(button_widths) + max(0, len(button_widths) - 1) * 2\n",
        path=path,
    )
    text = replace_exact(
        text,
        "            btn_w = len(btn_text) + 4\n",
        "            btn_w = button_widths[i]\n",
        path=path,
    )
    text = replace_exact(
        text,
        "                btn_w = len(btn_text) + 4\n",
        "                btn_w = text_display_width(btn_text) + 4\n",
        path=path,
    )
    text = replace_exact(
        text,
        "                    text.ljust(list_w)[:list_w],\n",
        "                    pad_text_columns(text, list_w, suffix=\"…\"),\n",
        path=path,
    )
    write(path, text)


def add_tests() -> None:
    path = "tests/test_unicode_menus_dialogs.py"
    if (ROOT / path).exists():
        raise RuntimeError(f"{path} already exists")
    write(
        path,
        '''import importlib
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
    fake.A_DIM = 2
    fake.A_REVERSE = 4
    fake.error = Exception
    fake.color_pair = lambda _: 0
    return fake


class UnicodeMenusDialogsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()
        for name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
        ):
            sys.modules.pop(name, None)
        cls.utils = importlib.import_module("retrotui.utils")
        cls.menu_mod = importlib.import_module("retrotui.ui.menu")
        cls.dialog_mod = importlib.import_module("retrotui.ui.dialog")

    @classmethod
    def tearDownClass(cls):
        for name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.dialog",
        ):
            sys.modules.pop(name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_menu_positions_use_physical_columns(self):
        menu = self.menu_mod.MenuBar({
            "文件": [("打开", "open")],
            "编辑": [("复制", "copy")],
        })
        self.assertEqual(menu.get_menu_x_positions(), [2, 9])
        self.assertEqual(menu.menu_items_right_x(), 15)

    def test_menu_click_hitbox_matches_rendered_columns(self):
        menu = self.menu_mod.MenuBar({
            "文件": [("打开", "open")],
            "编辑": [("复制", "copy")],
        })
        second_x = menu.get_menu_x_positions()[1]
        self.assertFalse(menu.hit_test_menu_item(second_x - 1, 0))
        menu.handle_click(second_x, 0)
        self.assertTrue(menu.active)
        self.assertEqual(menu.selected_menu, 1)

    def test_dropdown_rows_clip_and_pad_to_physical_width(self):
        menu = self.menu_mod.MenuBar({"文件": [("你" * 12, "open")]})
        menu.active = True
        menu._set_viewport(width=10, height=10)
        layout = menu._dropdown_layout()
        self.assertIsNotNone(layout)
        x, y, dropdown_w, _items = layout
        safe_addstr = mock.Mock()
        draw_globals = self.menu_mod.MenuBar.draw_dropdown.__globals__
        with mock.patch.dict(
            draw_globals,
            {
                "draw_box": mock.Mock(),
                "safe_addstr": safe_addstr,
                "theme_attr": mock.Mock(return_value=0),
            },
        ):
            menu.draw_dropdown(types.SimpleNamespace())
        row = next(
            call.args[3]
            for call in safe_addstr.call_args_list
            if call.args[1] == y + 1 and call.args[2] == x
        )
        self.assertEqual(self.utils.text_display_width(row), dropdown_w)
        self.assertIn("…", row)

    def test_dialog_message_wraps_by_physical_columns(self):
        lines = self.dialog_mod._wrap_dialog_message("你你你 AB", 4)
        self.assertTrue(lines)
        self.assertTrue(
            all(self.utils.text_display_width(line) <= 4 for line in lines)
        )
        self.assertEqual(lines[:2], ["你你", "你"])

    def test_dialog_button_layout_and_hitboxes_use_physical_columns(self):
        dialog = self.dialog_mod.Dialog(
            "标题",
            "message",
            buttons=["确认", "Cancel"],
            width=20,
        )
        self.assertEqual(dialog.width, 24)
        draw_globals = self.dialog_mod.Dialog.draw.__globals__
        with mock.patch.dict(
            draw_globals,
            {
                "draw_box": mock.Mock(),
                "safe_addstr": mock.Mock(),
                "theme_attr": mock.Mock(return_value=0),
            },
        ):
            dialog.draw(types.SimpleNamespace(), frame_size=(24, 80))
        first_width = self.utils.text_display_width("确认") + 4
        second_x = dialog._btn_x_start + first_width + 2
        self.assertEqual(dialog.handle_click(dialog._btn_x_start, dialog._btn_y), 0)
        self.assertEqual(dialog.handle_click(second_x, dialog._btn_y), 1)
        self.assertEqual(dialog.handle_click(second_x - 1, dialog._btn_y), -1)

    def test_dialog_title_row_fills_exact_physical_width(self):
        dialog = self.dialog_mod.Dialog("标题🙂", "message", width=24)
        safe_addstr = mock.Mock()
        draw_globals = self.dialog_mod.Dialog.draw.__globals__
        with mock.patch.dict(
            draw_globals,
            {
                "draw_box": mock.Mock(),
                "safe_addstr": safe_addstr,
                "theme_attr": mock.Mock(return_value=0),
            },
        ):
            dialog.draw(types.SimpleNamespace(), frame_size=(24, 80))
        title_call = next(
            call
            for call in safe_addstr.call_args_list
            if call.args[1] == dialog._dialog_y
            and call.args[2] == dialog._dialog_x + 1
        )
        self.assertEqual(
            self.utils.text_display_width(title_call.args[3]),
            dialog.width - 2,
        )

    def test_multiselect_rows_fit_physical_list_width(self):
        dialog = self.dialog_mod.MultiSelectDialog(
            "选择",
            "message",
            [("你" * 30, "value", True)],
            width=24,
        )
        safe_addstr = mock.Mock()
        draw_globals = self.dialog_mod.MultiSelectDialog.draw.__globals__
        with mock.patch.dict(
            draw_globals,
            {
                "draw_box": mock.Mock(),
                "safe_addstr": safe_addstr,
                "theme_attr": mock.Mock(return_value=0),
            },
        ):
            dialog.draw(types.SimpleNamespace(), frame_size=(40, 100))
        list_w = dialog.width - 6
        row = next(
            call.args[3]
            for call in safe_addstr.call_args_list
            if isinstance(call.args[3], str) and "[x]" in call.args[3]
        )
        self.assertEqual(self.utils.text_display_width(row), list_w)
        self.assertIn("…", row)


if __name__ == "__main__":
    unittest.main()
''',
    )


def main() -> None:
    update_utils()
    update_menu()
    update_dialog()
    add_tests()


if __name__ == "__main__":
    main()

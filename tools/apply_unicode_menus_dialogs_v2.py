#!/usr/bin/env python3
"""Corrected Unicode menus/dialogs applicator with ProgressDialog coverage."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "tools/apply_unicode_menus_dialogs.py"
SPEC = importlib.util.spec_from_file_location("unicode_menus_dialogs_base", BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load base Unicode menus/dialogs applicator")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def update_dialog() -> None:
    path = "retrotui/ui/dialog.py"
    text = base.read(path)
    text = base.replace_exact(
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

    text = base.replace_exact(
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
    text = base.replace_exact(text, old_title, new_title, path=path)

    text = base.replace_exact(
        text,
        "        total_btn_width = sum(len(b) + 6 for b in self.buttons) + (len(self.buttons) - 1) * 2\n",
        "        button_widths = [text_display_width(button) + 4 for button in self.buttons]\n        total_btn_width = sum(button_widths) + max(0, len(button_widths) - 1) * 2\n",
        path=path,
    )

    old_draw_buttons = '''        for i, btn_text in enumerate(self.buttons):
            btn_w = len(btn_text) + 4
            if i == self.selected:
                btn_attr = theme_attr('button_selected') | curses.A_BOLD
                label = f'▸ {btn_text} ◂'
            else:
                btn_attr = theme_attr('button')
                label = f'[ {btn_text} ]'
            safe_addstr(stdscr, btn_y, btn_x, label, btn_attr, _bounds=frame_size)
            btn_x += btn_w + 2
'''
    new_draw_buttons = '''        for i, btn_text in enumerate(self.buttons):
            btn_w = button_widths[i]
            if i == self.selected:
                btn_attr = theme_attr('button_selected') | curses.A_BOLD
                label = f'▸ {btn_text} ◂'
            else:
                btn_attr = theme_attr('button')
                label = f'[ {btn_text} ]'
            safe_addstr(stdscr, btn_y, btn_x, label, btn_attr, _bounds=frame_size)
            btn_x += btn_w + 2
'''
    text = base.replace_exact(text, old_draw_buttons, new_draw_buttons, path=path)

    old_dialog_click = '''            for i, btn_text in enumerate(self.buttons):
                btn_w = len(btn_text) + 4
                if btn_x <= mx < btn_x + btn_w:
                    return i
                btn_x += btn_w + 2
'''
    new_dialog_click = '''            for i, btn_text in enumerate(self.buttons):
                btn_w = text_display_width(btn_text) + 4
                if btn_x <= mx < btn_x + btn_w:
                    return i
                btn_x += btn_w + 2
'''
    text = base.replace_exact(text, old_dialog_click, new_dialog_click, path=path)

    text = base.replace_exact(
        text,
        "                    text.ljust(list_w)[:list_w],\n",
        "                    pad_text_columns(text, list_w, suffix=\"…\"),\n",
        path=path,
    )

    old_multiselect_click = '''            for i, btn_text in enumerate(self.buttons):
                btn_w = len(btn_text) + 4
                if btn_x <= mx < btn_x + btn_w:
                    self.in_list = False
                    self.selected = i
                    return i
                btn_x += btn_w + 2
'''
    new_multiselect_click = '''            for i, btn_text in enumerate(self.buttons):
                btn_w = text_display_width(btn_text) + 4
                if btn_x <= mx < btn_x + btn_w:
                    self.in_list = False
                    self.selected = i
                    return i
                btn_x += btn_w + 2
'''
    text = base.replace_exact(
        text,
        old_multiselect_click,
        new_multiselect_click,
        path=path,
    )

    text = base.replace_exact(
        text,
        "        self.width = max(width, len(title) + 8)\n",
        "        self.width = max(int(width), text_display_width(title) + 8)\n",
        path=path,
    )
    text = base.replace_exact(
        text,
        "        safe_addstr(stdscr, y, x + 1, f' {self.title} '.ljust(self.width - 2), title_attr, _bounds=frame_size)\n",
        "        progress_title = clip_text_columns(\n            self.title, max(0, self.width - 4), suffix=\"…\"\n        )\n        safe_addstr(\n            stdscr, y, x + 1,\n            pad_text_columns(f' {progress_title} ', self.width - 2),\n            title_attr, _bounds=frame_size,\n        )\n",
        path=path,
    )
    text = base.replace_exact(
        text,
        "            safe_addstr(stdscr, y + 2 + i, x + 3, line[: self.width - 6], attr, _bounds=frame_size)\n",
        "            safe_addstr(\n                stdscr, y + 2 + i, x + 3,\n                clip_text_columns(line, self.width - 6),\n                attr, _bounds=frame_size,\n            )\n",
        path=path,
    )
    text = base.replace_exact(
        text,
        "            status[: self.width - 6].ljust(self.width - 6),\n",
        "            pad_text_columns(status, self.width - 6, suffix=\"…\"),\n",
        path=path,
    )
    text = base.replace_exact(
        text,
        "            cancel_x = x + max(3, (self.width - len(label)) // 2)\n",
        "            label_width = text_display_width(label)\n            cancel_x = x + max(3, (self.width - label_width) // 2)\n",
        path=path,
    )
    text = base.replace_exact(
        text,
        "            self._cancel_x_end = cancel_x + len(label)\n",
        "            self._cancel_x_end = cancel_x + label_width\n",
        path=path,
    )
    base.write(path, text)


def extend_tests() -> None:
    path = "tests/test_unicode_menus_dialogs.py"
    text = base.read(path)
    marker = '''

if __name__ == "__main__":
    unittest.main()
'''
    test = '''
    def test_progress_dialog_title_uses_physical_columns(self):
        dialog = self.dialog_mod.ProgressDialog("进度🙂", "message", width=20)
        self.assertEqual(dialog.width, 20)
        safe_addstr = mock.Mock()
        draw_globals = self.dialog_mod.ProgressDialog.draw.__globals__
        with mock.patch.dict(
            draw_globals,
            {
                "draw_box": mock.Mock(),
                "safe_addstr": safe_addstr,
                "theme_attr": mock.Mock(return_value=0),
            },
        ):
            dialog.draw(types.SimpleNamespace(), frame_size=(30, 80))
        title_call = next(
            call
            for call in safe_addstr.call_args_list
            if call.args[1] == (30 - dialog.height) // 2
            and call.args[2] == (80 - dialog.width) // 2 + 1
        )
        self.assertEqual(
            self.utils.text_display_width(title_call.args[3]),
            dialog.width - 2,
        )


if __name__ == "__main__":
    unittest.main()
'''
    text = base.replace_exact(text, marker, test, path=path)
    base.write(path, text)


def main() -> None:
    base.update_utils()
    base.update_menu()
    update_dialog()
    base.add_tests()
    extend_tests()


if __name__ == "__main__":
    main()

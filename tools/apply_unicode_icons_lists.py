from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _path(relative: str) -> Path:
    return ROOT / relative


def _read(relative: str) -> str:
    return _path(relative).read_text(encoding="utf-8")


def _write(relative: str, text: str) -> None:
    _path(relative).write_text(text, encoding="utf-8")


def replace_once(relative: str, old: str, new: str) -> None:
    text = _read(relative)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one exact match, found {count}")
    _write(relative, text.replace(old, new, 1))


def sub_once(relative: str, pattern: str, replacement: str) -> None:
    text = _read(relative)
    updated, count = re.subn(
        pattern,
        lambda _match: replacement,
        text,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    if count != 1:
        raise RuntimeError(f"{relative}: expected one regex match, found {count}")
    _write(relative, updated)


def write_new(relative: str, content: str) -> None:
    path = _path(relative)
    if path.exists():
        raise RuntimeError(f"{relative}: file already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def patch_utils() -> None:
    replace_once(
        "retrotui/utils.py",
        '''def pad_text_columns(text, columns, *, suffix="") -> str:
    """Clip and right-pad text to an exact physical terminal-column width."""
    width = max(0, int(columns))
    fitted = clip_text_columns(text, width, suffix=suffix)
    return fitted + (" " * max(0, width - text_display_width(fitted)))


''',
        '''def pad_text_columns(text, columns, *, suffix="") -> str:
    """Clip and right-pad text to an exact physical terminal-column width."""
    width = max(0, int(columns))
    fitted = clip_text_columns(text, width, suffix=suffix)
    return fitted + (" " * max(0, width - text_display_width(fitted)))


def center_text_columns(text, columns, *, suffix="") -> str:
    """Clip and center text inside an exact physical terminal-column width."""
    width = max(0, int(columns))
    fitted = clip_text_columns(text, width, suffix=suffix)
    remaining = max(0, width - text_display_width(fitted))
    left = remaining // 2
    return (" " * left) + fitted + (" " * (remaining - left))


''',
    )


def patch_icon_geometry() -> None:
    replace_once(
        "retrotui/core/icon_manager.py",
        '''    ICON_DEFAULT_SPACING_Y,
    ICON_GRID_BOTTOM_MARGIN,
    ICON_FALLBACK_TERMINAL_HEIGHT,
)
''',
        '''    ICON_DEFAULT_SPACING_Y,
    ICON_GRID_BOTTOM_MARGIN,
    ICON_FALLBACK_TERMINAL_HEIGHT,
    ICON_ART_HEIGHT,
)
from ..utils import text_display_width
''',
    )
    replace_once(
        "retrotui/core/icon_manager.py",
        '''_ICON_TERMINAL_SIZE_ERRORS = (AttributeError, OSError, TypeError, ValueError)


class IconPositionManager:
''',
        '''_ICON_TERMINAL_SIZE_ERRORS = (AttributeError, OSError, TypeError, ValueError)


def icon_render_metrics(icon):
    """Return art lines, art height and shared Unicode-aware icon width."""
    symbol = icon.get("symbol")
    if isinstance(symbol, str) and symbol:
        art_lines = [symbol]
    else:
        art = icon.get("art", ())
        art_lines = [str(line) for line in art] if isinstance(art, (list, tuple)) else []
        if not art_lines:
            art_lines = ["[]"]

    art_width = max((text_display_width(line) for line in art_lines), default=2)
    label_width = text_display_width(icon.get("label", ""))
    slot_width = max(2, int(ICON_DEFAULT_SPACING_X) - 1)
    render_width = min(slot_width, max(2, art_width, label_width))
    render_height = max(ICON_ART_HEIGHT, len(art_lines))
    return art_lines, render_height, render_width


class IconPositionManager:
''',
    )
    sub_once(
        "retrotui/core/icon_manager.py",
        r'''    def get_icon_at\(self, mx, my, \*, frame_size=None\):\n        """Return icon index at mouse position, or -1\."""\n.*?        return -1\n''',
        '''    def get_icon_at(self, mx, my, *, frame_size=None):
        """Return icon index at mouse position, or -1."""
        icons = self._app.icons
        for i, icon in enumerate(icons):
            x, y = self.get_screen_pos(i, frame_size=frame_size)
            _art_lines, render_height, render_width = icon_render_metrics(icon)
            if (
                y <= my < y + render_height + 1
                and x <= mx < x + render_width
            ):
                return i
        return -1
''',
    )


def patch_icon_rendering() -> None:
    replace_once(
        "retrotui/core/rendering.py",
        "from ..utils import safe_addstr, theme_attr\n",
        "from ..utils import center_text_columns, safe_addstr, theme_attr\n"
        "from .icon_manager import icon_render_metrics\n",
    )
    sub_once(
        "retrotui/core/rendering.py",
        r'''def draw_icons\(app, frame_size=None\):\n.*?\n\ndef draw_taskbar''',
        '''def draw_icons(app, frame_size=None):
    """Draw desktop icons with shared Unicode-aware render geometry."""
    h, w = _resolve_frame_size(app, frame_size)
    bounds = (h, w)
    get_pos = app.get_icon_screen_pos
    accepts_frame_size = getattr(app, "_get_pos_accepts_frame_size", None)
    if accepts_frame_size is None:
        try:
            import inspect
            accepts_frame_size = "frame_size" in inspect.signature(get_pos).parameters
        except (TypeError, ValueError):
            accepts_frame_size = False
        try:
            app._get_pos_accepts_frame_size = accepts_frame_size
        except (AttributeError, TypeError):
            pass

    for idx, icon in enumerate(app.icons):
        if accepts_frame_size:
            x, y = get_pos(idx, frame_size=frame_size)
        else:
            x, y = get_pos(idx)

        art_lines, render_height, render_width = icon_render_metrics(icon)
        if y + render_height >= workspace_bottom_exclusive(h) or x >= w:
            continue
        visible_width = min(render_width, max(0, w - x))
        if visible_width <= 0:
            continue

        is_selected = idx == app.selected_icon
        attr = theme_attr("icon_selected" if is_selected else "icon")
        if is_selected:
            attr |= curses.A_BOLD

        for row, line in enumerate(art_lines):
            rendered = center_text_columns(line, visible_width, suffix="…")
            safe_addstr(app.stdscr, y + row, x, rendered, attr, _bounds=bounds)
        label = center_text_columns(
            icon.get("label", ""),
            visible_width,
            suffix="…",
        )
        safe_addstr(
            app.stdscr,
            y + render_height,
            x,
            label,
            attr,
            _bounds=bounds,
        )


def draw_taskbar''',
    )


def patch_file_manager() -> None:
    replace_once(
        "retrotui/apps/filemanager/core.py",
        "import os\nimport unicodedata\n\n",
        "import os\n\nfrom ...utils import pad_text_columns, text_display_width\n\n",
    )
    sub_once(
        "retrotui/apps/filemanager/core.py",
        r'''def _cell_width\(ch\):\n.*?def _fit_text_to_cells\(text, max_cells\):\n.*?    return ''\.join\(out\)\n''',
        '''def _cell_width(ch):
    """Return physical terminal width for one character."""
    return text_display_width(ch)


def _fit_text_to_cells(text, max_cells):
    """Clip/pad text to an exact physical terminal-column width."""
    return pad_text_columns(text, max_cells)
''',
    )
    replace_once(
        "retrotui/apps/filemanager/core.py",
        '''        else:
            # ``name[:30]:<30`` truncates names longer than 30 chars before
            # left-aligning so the size column stays aligned. Without the
            # slice, names like executables with long paths overflow into
            # the size column and break the visual grid.
            self.display_text = f'  {file_icon} {name[:30]:<30} {self._format_size():>8}'
''',
        '''        else:
            name_field = pad_text_columns(name, 30, suffix="…")
            size_field = f"{self._format_size():>8}"
            self.display_text = f"  {file_icon} {name_field} {size_field}"
''',
    )
    replace_once(
        "retrotui/apps/filemanager/window.py",
        "             safe_addstr(stdscr, y + 2, x + 2, f'Error: {error_msg}'[:w-2], theme_attr('window_body'))\n",
        "             safe_addstr(\n"
        "                 stdscr,\n"
        "                 y + 2,\n"
        "                 x + 2,\n"
        "                 _fit_text_to_cells(f'Error: {error_msg}', max(0, w - 2)),\n"
        "                 theme_attr('window_body'),\n"
        "             )\n",
    )


def patch_selection_editors() -> None:
    replace_once(
        "retrotui/apps/app_manager.py",
        "from ..utils import draw_box, normalize_key_code, safe_addstr, theme_attr\n",
        "from ..utils import (\n"
        "    draw_box,\n"
        "    normalize_key_code,\n"
        "    pad_text_columns,\n"
        "    safe_addstr,\n"
        "    text_display_width,\n"
        "    theme_attr,\n"
        ")\n",
    )
    replace_once(
        "retrotui/apps/app_manager.py",
        '''        safe_addstr(stdscr, self.y + 1, self.x + 2, self._help_text.ljust(self.w - 4)[: self.w - 4], body_attr, _bounds=frame_size)
        safe_addstr(stdscr, self.y + 2, self.x + 2, self._status_text.ljust(self.w - 4)[: self.w - 4], body_attr, _bounds=frame_size)
''',
        '''        inner_width = max(0, self.w - 4)
        safe_addstr(
            stdscr,
            self.y + 1,
            self.x + 2,
            pad_text_columns(self._help_text, inner_width, suffix="…"),
            body_attr,
            _bounds=frame_size,
        )
        safe_addstr(
            stdscr,
            self.y + 2,
            self.x + 2,
            pad_text_columns(self._status_text, inner_width, suffix="…"),
            body_attr,
            _bounds=frame_size,
        )
''',
    )
    replace_once(
        "retrotui/apps/app_manager.py",
        '''            safe_addstr(stdscr, tab_y, tab_x, tab, attr, _bounds=frame_size)
            self._tab_ranges.append((tab_x, tab_x + len(tab), idx))
            tab_x += len(tab) + 1
''',
        '''            tab_width = text_display_width(tab)
            safe_addstr(stdscr, tab_y, tab_x, tab, attr, _bounds=frame_size)
            self._tab_ranges.append((tab_x, tab_x + tab_width, idx))
            tab_x += tab_width + 1
''',
    )
    replace_once(
        "retrotui/apps/app_manager.py",
        "                safe_addstr(stdscr, list_y + row, list_x, text.ljust(list_w)[:list_w], attr)\n",
        "                safe_addstr(\n"
        "                    stdscr,\n"
        "                    list_y + row,\n"
        "                    list_x,\n"
        "                    pad_text_columns(text, list_w, suffix=\"…\"),\n"
        "                    attr,\n"
        "                )\n",
    )
    replace_once(
        "retrotui/apps/app_manager.py",
        '''        total_w = sum(len(btn) + 4 for btn in self.buttons) + (len(self.buttons) - 1) * 2
        btn_x = self.x + max(0, (self.w - total_w) // 2)
        self._btn_ranges = []
        for idx, text in enumerate(self.buttons):
            label = f"[ {text} ]"
            attr = theme_attr("button_selected") if (self.active and not self.in_list and idx == self.selected_button) else theme_attr("button")
            safe_addstr(stdscr, btn_y, btn_x, label, attr)
            self._btn_ranges.append((btn_x, btn_x + len(label), idx))
            btn_x += len(label) + 2
''',
        '''        button_labels = [f"[ {text} ]" for text in self.buttons]
        total_w = sum(text_display_width(label) for label in button_labels)
        total_w += max(0, len(button_labels) - 1) * 2
        btn_x = self.x + max(0, (self.w - total_w) // 2)
        self._btn_ranges = []
        for idx, label in enumerate(button_labels):
            attr = (
                theme_attr("button_selected")
                if self.active and not self.in_list and idx == self.selected_button
                else theme_attr("button")
            )
            safe_addstr(stdscr, btn_y, btn_x, label, attr)
            label_width = text_display_width(label)
            self._btn_ranges.append((btn_x, btn_x + label_width, idx))
            btn_x += label_width + 2
''',
    )


def patch_process_manager() -> None:
    replace_once(
        "retrotui/apps/process_manager.py",
        "from ..utils import normalize_key_code, safe_addstr, theme_attr\n",
        "from ..utils import normalize_key_code, pad_text_columns, safe_addstr, theme_attr\n",
    )
    replace_once(
        "retrotui/apps/process_manager.py",
        "        safe_addstr(stdscr, by, bx, header[:bw].ljust(bw), theme_attr(\"menubar\"))\n",
        "        safe_addstr(\n"
        "            stdscr,\n"
        "            by,\n"
        "            bx,\n"
        "            pad_text_columns(header, bw, suffix=\"…\"),\n"
        "            theme_attr(\"menubar\"),\n"
        "        )\n",
    )
    replace_once(
        "retrotui/apps/process_manager.py",
        "            safe_addstr(stdscr, by + 1 + idx, bx, line[:bw].ljust(bw), attr)\n",
        "            safe_addstr(\n"
        "                stdscr,\n"
        "                by + 1 + idx,\n"
        "                bx,\n"
        "                pad_text_columns(line, bw, suffix=\"…\"),\n"
        "                attr,\n"
        "            )\n",
    )
    replace_once(
        "retrotui/apps/process_manager.py",
        "        safe_addstr(stdscr, by + bh - 2, bx, summary[:bw].ljust(bw), theme_attr(\"status\"))\n",
        "        safe_addstr(\n"
        "            stdscr,\n"
        "            by + bh - 2,\n"
        "            bx,\n"
        "            pad_text_columns(summary, bw, suffix=\"…\"),\n"
        "            theme_attr(\"status\"),\n"
        "        )\n",
    )
    replace_once(
        "retrotui/apps/process_manager.py",
        "        safe_addstr(stdscr, by + bh - 1, bx, status[:bw].ljust(bw), theme_attr(\"status\"))\n",
        "        safe_addstr(\n"
        "            stdscr,\n"
        "            by + bh - 1,\n"
        "            bx,\n"
        "            pad_text_columns(status, bw, suffix=\"…\"),\n"
        "            theme_attr(\"status\"),\n"
        "        )\n",
    )


def add_tests() -> None:
    write_new(
        "tests/test_unicode_icons_lists.py",
        '''import types
import unittest
from unittest import mock

from retrotui.apps import app_manager, process_manager
from retrotui.apps.filemanager.core import FileEntry, _fit_text_to_cells
from retrotui.core import rendering
from retrotui.core.icon_manager import IconPositionManager, icon_render_metrics
from retrotui.ui.window import Window
from retrotui.utils import text_display_width


class UnicodeIconAndListTests(unittest.TestCase):
    def test_file_entry_name_field_uses_physical_columns(self):
        name = "報告書e\u0301🙂" * 8
        with mock.patch("retrotui.apps.filemanager.core.os.access", return_value=False):
            entry = FileEntry(name, False, "/tmp/report", 123, use_unicode=True)

        self.assertEqual(text_display_width(entry.display_text), 44)
        self.assertTrue(entry.display_text.endswith("    123B"))
        self.assertIn("…", entry.display_text)
        self.assertEqual(text_display_width(_fit_text_to_cells("A界e\u0301Z", 8)), 8)

    def test_icon_hitbox_matches_unicode_render_width(self):
        icon = {"symbol": "界", "label": "設定🙂設定🙂設定"}
        app = types.SimpleNamespace(
            icons=[icon],
            stdscr=types.SimpleNamespace(getmaxyx=lambda: (24, 80)),
            persist_config=lambda: None,
        )
        manager = IconPositionManager(app)
        manager.positions["設定🙂設定🙂設定"] = (3, 4)
        _lines, render_height, render_width = icon_render_metrics(icon)

        self.assertEqual(manager.get_icon_at(3 + render_width - 1, 4), 0)
        self.assertEqual(manager.get_icon_at(3 + render_width, 4), -1)
        self.assertEqual(manager.get_icon_at(3, 4 + render_height), 0)
        self.assertEqual(manager.get_icon_at(3, 4 + render_height + 1), -1)

    def test_desktop_icon_rows_have_exact_physical_width(self):
        icon = {"symbol": "界", "label": "設定🙂設定🙂設定"}
        app = types.SimpleNamespace(
            stdscr=types.SimpleNamespace(),
            icons=[icon],
            selected_icon=-1,
            get_icon_screen_pos=lambda index, frame_size=None: (2, 2),
        )
        _lines, render_height, render_width = icon_render_metrics(icon)

        with (
            mock.patch.object(rendering, "safe_addstr") as safe_addstr,
            mock.patch.object(rendering, "theme_attr", return_value=0),
        ):
            rendering.draw_icons(app, frame_size=(20, 40))

        rendered = [
            call.args[3]
            for call in safe_addstr.call_args_list
            if call.args[1] in (2, 2 + render_height)
        ]
        self.assertEqual(len(rendered), 2)
        self.assertTrue(all(text_display_width(text) == render_width for text in rendered))

    def test_selection_editor_uses_physical_tab_and_button_ranges(self):
        editor = app_manager._BaseSelectionEditorWindow.__new__(
            app_manager._BaseSelectionEditorWindow
        )
        editor.visible = True
        editor.active = True
        editor.x = 1
        editor.y = 1
        editor.w = 36
        editor.h = 16
        editor.in_list = True
        editor.selected_button = 0
        editor.buttons = ["保存", "取消"]
        editor._tab_ranges = []
        editor._btn_ranges = []
        editor._help_text = "管理🙂插件"
        editor._status_text = "選択e\u0301"
        editor.categories = ["插件"]
        editor.choices = {"插件": [["設定🙂", "plugin:test", True]]}
        editor.active_cat_idx = 0
        editor.sel_indices = {"插件": 0}
        editor.offsets = {"插件": 0}

        with (
            mock.patch.object(Window, "draw", return_value=None),
            mock.patch.object(app_manager, "safe_addstr") as safe_addstr,
            mock.patch.object(app_manager, "draw_box"),
            mock.patch.object(app_manager, "theme_attr", return_value=0),
        ):
            editor.draw(types.SimpleNamespace(), frame_size=(30, 80))

        tab = " 插件 "
        self.assertEqual(
            editor._tab_ranges[0][1] - editor._tab_ranges[0][0],
            text_display_width(tab),
        )
        for start, end, idx in editor._btn_ranges:
            self.assertEqual(
                end - start,
                text_display_width(f"[ {editor.buttons[idx]} ]"),
            )
        list_w = editor._list_rect()[2]
        row_texts = [
            call.args[3]
            for call in safe_addstr.call_args_list
            if call.args[1] == editor._list_rect()[1]
            and call.args[2] == editor._list_rect()[0]
        ]
        self.assertTrue(row_texts)
        self.assertEqual(text_display_width(row_texts[0]), list_w)

    def test_process_rows_clip_by_terminal_columns(self):
        window = process_manager.ProcessManagerWindow.__new__(
            process_manager.ProcessManagerWindow
        )
        window.visible = True
        window.active = True
        window.rows = [
            process_manager.ProcessRow(7, 1.2, 3.4, "命令🙂e\u0301-long-command", 1)
        ]
        window.selected_index = 0
        window.scroll_offset = 0
        window.sort_key = "cmd"
        window.sort_reverse = False
        window.summary_uptime = "01h 00m"
        window.summary_load = "0.10 0.20 0.30"
        window.summary_mem = "1MB/2MB"
        window._error_message = None
        window.window_menu = None
        window.draw_frame = lambda stdscr: 0
        window.body_rect = lambda: (1, 1, 24, 6)
        window._visible_rows = lambda: 3
        window._max_scroll = lambda: 0

        with (
            mock.patch.object(process_manager, "safe_addstr") as safe_addstr,
            mock.patch.object(process_manager, "theme_attr", return_value=0),
        ):
            window.draw(types.SimpleNamespace())

        fitted = [
            call.args[3]
            for call in safe_addstr.call_args_list
            if call.args[2] == 1 and isinstance(call.args[3], str)
        ]
        self.assertTrue(fitted)
        self.assertTrue(all(text_display_width(text) == 24 for text in fitted))


if __name__ == "__main__":
    unittest.main()
''',
    )


def remove_temporary_files() -> None:
    for relative in (
        "tools/apply_unicode_icons_lists.py",
        ".github/workflows/apply-unicode-icons-lists.yml",
    ):
        path = _path(relative)
        if path.exists():
            path.unlink()


def main() -> None:
    patch_utils()
    patch_icon_geometry()
    patch_icon_rendering()
    patch_file_manager()
    patch_selection_editors()
    patch_process_manager()
    add_tests()
    remove_temporary_files()
    print("unicode icons and lists patch applied")


if __name__ == "__main__":
    main()

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
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE | re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one regex match, found {count}: {pattern}")
    _write(relative, updated)


def write_new(relative: str, content: str) -> None:
    path = _path(relative)
    if path.exists():
        raise RuntimeError(f"{relative}: file already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def patch_constants() -> None:
    replace_once(
        "retrotui/constants.py",
        "MENU_BAR_HEIGHT = 1          # Row 0 is the unified global menu/taskbar\n"
        "BOTTOM_BARS_HEIGHT = 0       # No separate bottom bar; row 0 owns shell chrome\n",
        "MENU_BAR_HEIGHT = 0          # Workspace begins at row 0\n"
        "BOTTOM_BARS_HEIGHT = 1       # One classic shell/taskbar row at the bottom\n",
    )


def add_shell_geometry() -> None:
    write_new(
        "retrotui/core/shell_geometry.py",
        '''"""Shared geometry for the desktop workspace and classic shell bar."""\n\n'
        'from ..constants import BOTTOM_BARS_HEIGHT, MENU_BAR_HEIGHT\n\n\n'
        'def global_bar_row(screen_h):\n'
        '    """Return the terminal row occupied by the global shell bar."""\n'
        '    height = max(0, int(screen_h))\n'
        '    if height <= 0:\n'
        '        return 0\n'
        '    if BOTTOM_BARS_HEIGHT:\n'
        '        return max(0, height - int(BOTTOM_BARS_HEIGHT))\n'
        '    return 0\n\n\n'
        'def workspace_top_row():\n'
        '    """Return the first row available to desktop content and windows."""\n'
        '    return max(0, int(MENU_BAR_HEIGHT))\n\n\n'
        'def workspace_bottom_exclusive(screen_h):\n'
        '    """Return the first row reserved below the desktop workspace."""\n'
        '    height = max(0, int(screen_h))\n'
        '    bottom = max(0, height - max(0, int(BOTTOM_BARS_HEIGHT)))\n'
        '    return max(workspace_top_row(), bottom)\n\n\n'
        'def workspace_height(screen_h):\n'
        '    """Return the number of rows available to windows and desktop content."""\n'
        '    return max(0, workspace_bottom_exclusive(screen_h) - workspace_top_row())\n'
        '''.replace("'''", ""),
    )


def patch_rendering() -> None:
    replace_once(
        "retrotui/core/rendering.py",
        "from ..utils import safe_addstr, theme_attr\n",
        "from ..utils import safe_addstr, theme_attr\n"
        "from .shell_geometry import (\n"
        "    global_bar_row,\n"
        "    workspace_bottom_exclusive,\n"
        "    workspace_top_row,\n"
        ")\n",
    )
    replace_once(
        "retrotui/core/rendering.py",
        "def _taskbar_row(frame_h):\n"
        "    return frame_h - BOTTOM_BARS_HEIGHT if BOTTOM_BARS_HEIGHT else 0\n",
        "def _taskbar_row(frame_h):\n"
        "    return global_bar_row(frame_h)\n",
    )
    sub_once(
        "retrotui/core/rendering.py",
        r"def _taskbar_bounds\(app, width\):\n.*?\n    return start_x, end_x\n\n\n",
        '''def _taskbar_bounds(app, width):
    menu = getattr(app, "menu", None)
    start_x = 1
    menu_right = getattr(menu, "menu_items_right_x", None)
    if callable(menu_right):
        try:
            start_x = max(start_x, int(menu_right()) + 1)
        except (TypeError, ValueError):
            start_x = 1

    end_x = width
    reserved = getattr(menu, "right_reserved_start_x", None)
    if callable(reserved):
        try:
            end_x = min(end_x, max(start_x, int(reserved(width)) - 1))
        except (TypeError, ValueError):
            end_x = width
    return start_x, end_x


''',
    )
    replace_once(
        "retrotui/core/rendering.py",
        "    for row in range(MENU_BAR_HEIGHT, h - BOTTOM_BARS_HEIGHT):\n",
        "    for row in range(workspace_top_row(), workspace_bottom_exclusive(h)):\n",
    )
    replace_once(
        "retrotui/core/rendering.py",
        "        if y + render_height >= h - BOTTOM_BARS_HEIGHT:\n",
        "        if y + render_height >= workspace_bottom_exclusive(h):\n",
    )
    replace_once(
        "retrotui/core/rendering.py",
        "    attr = theme_attr(\"taskbar\" if BOTTOM_BARS_HEIGHT else \"menubar\")\n\n"
        "    if BOTTOM_BARS_HEIGHT:\n"
        "        safe_addstr(app.stdscr, taskbar_y, 0, ' ' * w, attr, _bounds=bounds)\n\n",
        "    attr = theme_attr(\"taskbar\")\n\n",
    )
    sub_once(
        "retrotui/core/rendering.py",
        r"def draw_statusbar\(app, version, frame_size=None\):\n.*\Z",
        '''def draw_statusbar(app, version, frame_size=None):
    """Compatibility hook; the classic taskbar owns the only bottom row."""
    return None
''',
    )


def patch_window_manager() -> None:
    replace_once(
        "retrotui/core/window_manager.py",
        "from ..constants import TASKBAR_TITLE_MAX_LEN, BOTTOM_BARS_HEIGHT\n",
        "from ..constants import TASKBAR_TITLE_MAX_LEN\n",
    )
    replace_once(
        "retrotui/core/window_manager.py",
        "from ..utils import clip_text_columns, text_display_width\n",
        "from ..utils import clip_text_columns, text_display_width\n"
        "from .shell_geometry import global_bar_row\n",
    )
    replace_once(
        "retrotui/core/window_manager.py",
        "    def _taskbar_row(self, height):\n"
        "        return height - BOTTOM_BARS_HEIGHT if BOTTOM_BARS_HEIGHT else 0\n",
        "    def _taskbar_row(self, height):\n"
        "        return global_bar_row(height)\n",
    )
    sub_once(
        "retrotui/core/window_manager.py",
        r"    def _taskbar_bounds\(self, width\):\n.*?\n        return start_x, end_x\n\n",
        '''    def _taskbar_bounds(self, width):
        menu = getattr(self._app, "menu", None)
        start_x = 1
        menu_right = getattr(menu, "menu_items_right_x", None)
        if callable(menu_right):
            try:
                start_x = max(start_x, int(menu_right()) + 1)
            except (TypeError, ValueError):
                start_x = 1

        end_x = width
        reserved = getattr(menu, "right_reserved_start_x", None)
        if callable(reserved):
            try:
                end_x = min(end_x, max(start_x, int(reserved(width)) - 1))
            except (TypeError, ValueError):
                end_x = width
        return start_x, end_x

''',
    )


def patch_event_loop() -> None:
    replace_once(
        "retrotui/core/event_loop.py",
        "    BOTTOM_BARS_HEIGHT,\n",
        "    BOTTOM_BARS_HEIGHT,\n"
        "    MENU_BAR_HEIGHT,\n",
    )
    replace_once(
        "retrotui/core/event_loop.py",
        "        win.y = max(1, min(win.y, new_h - min(win.h, new_h) - BOTTOM_BARS_HEIGHT))\n",
        "        win.y = max(\n"
        "            MENU_BAR_HEIGHT,\n"
        "            min(win.y, new_h - min(win.h, new_h) - BOTTOM_BARS_HEIGHT),\n"
        "        )\n",
    )


def patch_mouse_router() -> None:
    replace_once(
        "retrotui/core/mouse_router.py",
        "from ..constants import MENU_BAR_HEIGHT, BOTTOM_BARS_HEIGHT, CLOCK_CLICK_REGION_WIDTH\n",
        "from ..constants import MENU_BAR_HEIGHT, CLOCK_CLICK_REGION_WIDTH\n"
        "from .shell_geometry import global_bar_row, workspace_bottom_exclusive\n",
    )
    replace_once(
        "retrotui/core/mouse_router.py",
        "def _bottom_limit_y(screen_h):\n"
        "    return screen_h - BOTTOM_BARS_HEIGHT\n\n\n"
        "def _clock_row(screen_h):\n"
        "    return screen_h - BOTTOM_BARS_HEIGHT if BOTTOM_BARS_HEIGHT else 0\n\n\n",
        "def _bottom_limit_y(screen_h):\n"
        "    return workspace_bottom_exclusive(screen_h)\n\n\n"
        "def _clock_row(screen_h):\n"
        "    return global_bar_row(screen_h)\n\n\n"
        "def _menu_bar_row(app):\n"
        "    menu = getattr(app, \"menu\", None)\n"
        "    resolver = getattr(menu, \"bar_row\", None)\n"
        "    if callable(resolver):\n"
        "        try:\n"
        "            return int(resolver())\n"
        "        except (TypeError, ValueError):\n"
        "            pass\n"
        "    return 0\n\n\n",
    )
    sub_once(
        "retrotui/core/mouse_router.py",
        r"def _menu_should_handle_top_click\(app, mx, my\):\n.*?\n    return True\n\n\n",
        '''def _menu_should_handle_top_click(app, mx, my):
    if my != _menu_bar_row(app):
        return False
    menu = getattr(app, "menu", None)
    if getattr(menu, "active", False):
        return True
    hit_test = getattr(menu, "hit_test_menu_item", None)
    if callable(hit_test):
        return bool(hit_test(mx, my))
    return True


''',
    )
    replace_once(
        "retrotui/core/mouse_router.py",
        "    if app.menu.hit_test_dropdown(mx, my) or my == 0:\n",
        "    if app.menu.hit_test_dropdown(mx, my) or my == _menu_bar_row(app):\n",
    )


def patch_menu() -> None:
    replace_once(
        "retrotui/ui/menu.py",
        "from ..constants import SB_H\n",
        "from ..constants import BOTTOM_BARS_HEIGHT, SB_H\n",
    )
    replace_once(
        "retrotui/ui/menu.py",
        "\n\nDEFAULT_GLOBAL_ITEMS = {\n",
        "\n\nSTART_BUTTON_TEXT = \"[ Inicio ]\"\n\n\nDEFAULT_GLOBAL_ITEMS = {\n",
    )
    sub_once(
        "retrotui/ui/menu.py",
        r"    def _bar_row\(self, win_y=0\):\n.*?\n    def get_menu_x_positions",
        '''    def _bar_row(self, win_y=0):
        if self.mode != "global":
            return win_y + 1
        if self._viewport_h is None:
            return 0
        if BOTTOM_BARS_HEIGHT:
            return max(0, self._viewport_h - BOTTOM_BARS_HEIGHT)
        return 0

    def bar_row(self):
        """Return the current global bar row for mouse-routing code."""
        return self._bar_row()

    def _start_button_bounds(self):
        if self.mode != "global" or not self.show_logo:
            return None
        return 0, text_display_width(START_BUTTON_TEXT)

    def hit_test_start_button(self, mx, my):
        bounds = self._start_button_bounds()
        if bounds is None or my != self._bar_row():
            return False
        start_x, end_x = bounds
        return start_x <= mx < end_x

    def _menu_start_x(self, win_x=0):
        if self.mode == "global" and self.show_logo:
            return text_display_width(START_BUTTON_TEXT) + 1
        return 2 if self.mode == "global" else win_x + 2

    def get_menu_x_positions''',
    )
    sub_once(
        "retrotui/ui/menu.py",
        r"    def hit_test_menu_item\(self, mx, my, \*, win_x=0, win_y=0, win_w=None\):\n.*?\n        return False\n\n",
        '''    def hit_test_menu_item(self, mx, my, *, win_x=0, win_y=0, win_w=None):
        """Return True when a point is over a start button or menu title."""
        if self.hit_test_start_button(mx, my):
            return True
        if my != self._bar_row(win_y):
            return False
        if self.mode == "window" and win_w is not None:
            if not (win_x + 1 <= mx < win_x + win_w - 1):
                return False
        positions = self.get_menu_x_positions(win_x)
        for i, pos in enumerate(positions):
            name = self.menu_names[i]
            if pos <= mx < pos + text_display_width(name) + 2:
                return True
        return False

''',
    )
    sub_once(
        "retrotui/ui/menu.py",
        r"    def _dropdown_layout\(self, win_x=0, win_y=0, win_w=None\):\n.*?\n        return x, y, dropdown_w, visible_items\n\n",
        '''    def _dropdown_layout(self, win_x=0, win_y=0, win_w=None):
        if not self.menu_names:
            return None

        # Keep keyboard/mouse layout stable between draw and event handlers.
        if win_x == 0 and win_y == 0 and win_w is None:
            win_x, win_y, win_w = self._last_layout_args

        full_items = self._current_items()
        positions = self.get_menu_x_positions(win_x)
        x = positions[self.selected_menu]
        max_item_columns = max(
            (text_display_width(label) for label, _ in full_items),
            default=0,
        )
        dropdown_w = max_item_columns + 4

        if full_items:
            self.selected_item = max(0, min(self.selected_item, len(full_items) - 1))
        else:
            self.selected_item = 0
            self.dropdown_scroll = 0

        viewport_w = self._viewport_w
        viewport_h = self._viewport_h

        if self.mode == "global" and viewport_w is not None:
            dropdown_w = min(dropdown_w, max(4, viewport_w - 2))

        if self.mode == "window" and win_w is not None:
            right_edge = win_x + win_w
            if x - 1 + dropdown_w + 2 > right_edge:
                x = max(win_x + 2, right_edge - dropdown_w - 2)
        elif self.mode == "global" and viewport_w is not None:
            max_x = max(1, viewport_w - dropdown_w - 1)
            x = max(1, min(x, max_x))

        bar_y = self._bar_row(win_y)
        opens_up = (
            self.mode == "global"
            and bool(BOTTOM_BARS_HEIGHT)
            and viewport_h is not None
        )
        visible_rows = len(full_items)
        if viewport_h is not None:
            if opens_up:
                available_rows = max(0, bar_y - 2)
            else:
                available_rows = max(0, viewport_h - (bar_y + 1) - 2)
            visible_rows = min(visible_rows, available_rows)

        max_scroll = max(0, len(full_items) - visible_rows)
        self.dropdown_scroll = max(0, min(self.dropdown_scroll, max_scroll))
        if self.selected_item < self.dropdown_scroll:
            self.dropdown_scroll = self.selected_item
        elif self.selected_item >= self.dropdown_scroll + max(1, visible_rows):
            self.dropdown_scroll = self.selected_item - visible_rows + 1
        self.dropdown_scroll = max(0, min(self.dropdown_scroll, max_scroll))

        visible_items = full_items[
            self.dropdown_scroll : self.dropdown_scroll + visible_rows
        ]
        if opens_up:
            y = max(0, bar_y - (len(visible_items) + 2))
        else:
            y = bar_y + 1
        return x, y, dropdown_w, visible_items

''',
    )
    sub_once(
        "retrotui/ui/menu.py",
        r"    def draw_bar\(\n.*?\n    def draw_dropdown",
        '''    def draw_bar(
        self,
        stdscr,
        *,
        width=None,
        win_x=0,
        win_y=0,
        win_w=None,
        is_active=True,
        frame_size=None,
    ):
        """Draw the bar row for either global or window mode."""
        bar_attr = theme_attr("menubar")
        self._last_layout_args = (win_x, win_y, win_w)
        size = frame_size if frame_size is not None else self._read_stdscr_size(stdscr)

        if self.mode == "global":
            if width is None:
                if size is not None:
                    viewport_h, width = size
                else:
                    viewport_h = self._viewport_h
                    width = self._viewport_w if self._viewport_w is not None else 80
            else:
                viewport_h = size[0] if size is not None else self._viewport_h
            self._set_viewport(width=width, height=viewport_h)
            bar_y = self._bar_row(win_y)
            safe_addstr(stdscr, bar_y, 0, " " * width, bar_attr, _bounds=frame_size)
            if self.show_logo:
                start_attr = (
                    theme_attr("menu_selected")
                    if self.active and self.selected_menu == 0 and is_active
                    else bar_attr | curses.A_BOLD
                )
                safe_addstr(
                    stdscr,
                    bar_y,
                    0,
                    START_BUTTON_TEXT,
                    start_attr,
                    _bounds=frame_size,
                )
        else:
            if win_w is None:
                return
            if size is not None:
                viewport_h, viewport_w = size
                self._set_viewport(width=viewport_w, height=viewport_h)
            bar_y = self._bar_row(win_y)
            safe_addstr(
                stdscr,
                bar_y,
                win_x + 1,
                " " * max(0, win_w - 2),
                bar_attr,
                _bounds=frame_size,
            )

        positions = self.get_menu_x_positions(win_x)
        for i, name in enumerate(self.menu_names):
            attr = bar_attr
            if self.active and i == self.selected_menu and is_active:
                attr = theme_attr("menu_selected")
            safe_addstr(
                stdscr,
                bar_y,
                positions[i],
                f" {name} ",
                attr,
                _bounds=frame_size,
            )

        if self.mode == "global":
            self.refresh_clock(
                stdscr, width=width, win_x=win_x, force=True, frame_size=frame_size,
            )

    def draw_dropdown''',
    )
    sub_once(
        "retrotui/ui/menu.py",
        r"    def handle_hover\(self, mx, my, \*, win_x=0, win_y=0, win_w=None\):\n.*?\n        return False\n\n",
        '''    def handle_hover(self, mx, my, *, win_x=0, win_y=0, win_w=None):
        """Handle hover and keep menu active while pointer remains in menu area."""
        if not self.active:
            return False

        bar_y = self._bar_row(win_y)
        if my == bar_y:
            if self.hit_test_start_button(mx, my) and self.menu_names:
                if self.selected_menu != 0:
                    self.selected_menu = 0
                    self.selected_item = self._first_selectable(self._current_items())
                    self.dropdown_scroll = 0
                return True
            positions = self.get_menu_x_positions(win_x)
            for i, pos in enumerate(positions):
                name = self.menu_names[i]
                if pos <= mx < pos + text_display_width(name) + 2:
                    if i != self.selected_menu:
                        self.selected_menu = i
                        self.selected_item = self._first_selectable(self._current_items())
                        self.dropdown_scroll = 0
                    return True
            return self.on_menu_bar(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)

        if self.hit_test_dropdown(mx, my, win_x=win_x, win_y=win_y, win_w=win_w):
            layout = self._dropdown_layout(win_x=win_x, win_y=win_y, win_w=win_w)
            if layout is None:
                return False
            _, layout_y, _, visible_items = layout
            full_items = self._current_items()
            idx = self.dropdown_scroll + (my - (layout_y + 1))
            if (
                0 <= idx < len(full_items)
                and (idx - self.dropdown_scroll) < len(visible_items)
                and full_items[idx][1] is not None
            ):
                self.selected_item = idx
            return True

        return False

''',
    )
    sub_once(
        "retrotui/ui/menu.py",
        r"    def handle_click\(self, mx, my, \*, win_x=0, win_y=0, win_w=None\):\n.*?\n        return None\n\n",
        '''    def handle_click(self, mx, my, *, win_x=0, win_y=0, win_w=None):
        """Handle click on menu bar/dropdown and return action string or None."""
        bar_y = self._bar_row(win_y)

        if my == bar_y and self.on_menu_bar(mx, my, win_x=win_x, win_y=win_y, win_w=win_w):
            if self.hit_test_start_button(mx, my) and self.menu_names:
                if self.active and self.selected_menu == 0:
                    self.active = False
                    self.dropdown_scroll = 0
                else:
                    self.active = True
                    self.selected_menu = 0
                    self.selected_item = self._first_selectable(self._current_items())
                    self.dropdown_scroll = 0
                return None

            positions = self.get_menu_x_positions(win_x)
            for i, pos in enumerate(positions):
                name = self.menu_names[i]
                if pos <= mx < pos + text_display_width(name) + 2:
                    if self.active and self.selected_menu == i:
                        self.active = False
                        self.dropdown_scroll = 0
                    else:
                        self.active = True
                        self.selected_menu = i
                        self.selected_item = self._first_selectable(self._current_items())
                        self.dropdown_scroll = 0
                    return None
            self.active = False
            self.dropdown_scroll = 0
            return None

        if self.active:
            layout = self._dropdown_layout(win_x=win_x, win_y=win_y, win_w=win_w)
            if layout is None:
                self.active = False
                self.dropdown_scroll = 0
                return None
            x, layout_y, dropdown_w, visible_items = layout
            full_items = self._current_items()

            if (
                x - 1 <= mx < x + dropdown_w + 1
                and layout_y + 1 <= my < layout_y + 1 + len(visible_items)
            ):
                idx = self.dropdown_scroll + (my - (layout_y + 1))
                if 0 <= idx < len(full_items) and full_items[idx][1] is not None:
                    action = full_items[idx][1]
                    self.active = False
                    self.dropdown_scroll = 0
                    return action
            else:
                self.active = False
                self.dropdown_scroll = 0

        return None

''',
    )


def patch_existing_tests() -> None:
    replace_once(
        "tests/test_rendering.py",
        "        self.assertEqual(first_call[1], 1)\n",
        "        self.assertEqual(first_call[1], 0)\n",
    )
    replace_once(
        "tests/test_rendering.py",
        "        self.assertEqual(last_call[1], 9)\n",
        "        self.assertEqual(last_call[1], 8)\n",
    )
    replace_once(
        "tests/test_rendering.py",
        "    def test_draw_taskbar_uses_unified_top_bar_free_space(self):\n",
        "    def test_draw_taskbar_uses_classic_bottom_bar_free_space(self):\n",
    )
    replace_once(
        "tests/test_rendering.py",
        "                call.args[1] == 0\n",
        "                call.args[1] == 19\n",
    )
    replace_once(
        "tests/test_rendering.py",
        "                == (self.curses.color_pair(self.constants.C_MENUBAR) | self.curses.A_BOLD)\n",
        "                == (self.curses.color_pair(self.constants.C_TASKBAR) | self.curses.A_BOLD)\n",
    )
    replace_once(
        "tests/test_event_loop.py",
        "        self.assertEqual(app.windows[0].y, 10)\n",
        "        self.assertEqual(app.windows[0].y, 9)\n",
    )
    replace_once(
        "tests/test_menu_bar.py",
        "        self.assertIn(' =', rendered)\n",
        "        self.assertIn('[ Inicio ]', rendered)\n",
    )


def add_focused_tests() -> None:
    write_new(
        "tests/test_classic_bottom_taskbar.py",
        '''import types\n'
        'import unittest\n'
        'from unittest import mock\n\n'
        'from retrotui.constants import BOTTOM_BARS_HEIGHT, MENU_BAR_HEIGHT\n'
        'from retrotui.core import rendering\n'
        'from retrotui.core.shell_geometry import (\n'
        '    global_bar_row,\n'
        '    workspace_bottom_exclusive,\n'
        '    workspace_top_row,\n'
        ')\n'
        'from retrotui.ui.menu import Menu\n'
        'from retrotui.ui.window import Window\n\n\n'
        'class ClassicBottomTaskbarTests(unittest.TestCase):\n'
        '    def test_workspace_reserves_one_bottom_row(self):\n'
        '        self.assertEqual(MENU_BAR_HEIGHT, 0)\n'
        '        self.assertEqual(BOTTOM_BARS_HEIGHT, 1)\n'
        '        self.assertEqual(workspace_top_row(), 0)\n'
        '        self.assertEqual(global_bar_row(24), 23)\n'
        '        self.assertEqual(workspace_bottom_exclusive(24), 23)\n\n'
        '    def test_global_menu_draws_on_bottom_and_opens_upward(self):\n'
        '        menu = Menu({"File": [("Open", "open"), ("Exit", "exit")]})\n'
        '        menu.active = True\n'
        '        stdscr = types.SimpleNamespace(getmaxyx=lambda: (24, 80))\n\n'
        '        with mock.patch.object(rendering, "safe_addstr"):\n'
        '            pass\n'
        '        with (\n'
        '            mock.patch("retrotui.ui.menu.safe_addstr") as safe_addstr,\n'
        '            mock.patch("retrotui.ui.menu.draw_box"),\n'
        '        ):\n'
        '            menu.draw_bar(stdscr, 80, frame_size=(24, 80))\n'
        '            menu.draw_dropdown(stdscr, frame_size=(24, 80))\n\n'
        '        self.assertEqual(menu.bar_row(), 23)\n'
        '        self.assertTrue(any(call.args[1] == 23 for call in safe_addstr.call_args_list))\n'
        '        rect = menu.get_dropdown_rect()\n'
        '        self.assertIsNotNone(rect)\n'
        '        _x, y, _w, h = rect\n'
        '        self.assertEqual(y + h, 23)\n\n'
        '    def test_start_button_click_uses_bottom_row(self):\n'
        '        menu = Menu({"File": [("Open", "open")]})\n'
        '        stdscr = types.SimpleNamespace(getmaxyx=lambda: (24, 80))\n'
        '        with mock.patch("retrotui.ui.menu.safe_addstr"):\n'
        '            menu.draw_bar(stdscr, 80, frame_size=(24, 80))\n\n'
        '        result = menu.handle_click(1, 23)\n\n'
        '        self.assertIsNone(result)\n'
        '        self.assertTrue(menu.active)\n'
        '        self.assertEqual(menu.selected_menu, 0)\n'
        '        self.assertFalse(menu.hit_test_menu_item(1, 0))\n\n'
        '    def test_taskbar_buttons_render_on_bottom_row(self):\n'
        '        stdscr = types.SimpleNamespace(getmaxyx=lambda: (20, 80))\n'
        '        app = types.SimpleNamespace(\n'
        '            stdscr=stdscr,\n'
        '            windows=[types.SimpleNamespace(minimized=True, title="Notes")],\n'
        '            menu=types.SimpleNamespace(\n'
        '                menu_items_right_x=lambda: 20,\n'
        '                right_reserved_start_x=lambda width: 70,\n'
        '            ),\n'
        '        )\n\n'
        '        with mock.patch.object(rendering, "safe_addstr") as safe_addstr:\n'
        '            rendering.draw_taskbar(app)\n\n'
        '        self.assertTrue(\n'
        '            any(call.args[1] == 19 and call.args[3] == "[Notes]" for call in safe_addstr.call_args_list)\n'
        '        )\n\n'
        '    def test_maximized_window_uses_workspace_above_taskbar(self):\n'
        '        window = Window("Test", 5, 4, 30, 10)\n\n'
        '        window.toggle_maximize(80, 24)\n\n'
        '        self.assertEqual(window.y, 0)\n'
        '        self.assertEqual(window.h, 23)\n'
        '        self.assertEqual(window.y + window.h, global_bar_row(24))\n\n\n'
        'if __name__ == "__main__":\n'
        '    unittest.main()\n'
        '''.replace("'''", ""),
    )


def remove_temporary_gate_files() -> None:
    for relative in (
        "tools/apply_classic_bottom_taskbar.py",
        ".github/workflows/apply-classic-bottom-taskbar.yml",
    ):
        path = _path(relative)
        if path.exists():
            path.unlink()


def main() -> None:
    patch_constants()
    add_shell_geometry()
    patch_rendering()
    patch_window_manager()
    patch_event_loop()
    patch_mouse_router()
    patch_menu()
    patch_existing_tests()
    add_focused_tests()
    remove_temporary_gate_files()
    print("classic bottom taskbar patch applied")


if __name__ == "__main__":
    main()

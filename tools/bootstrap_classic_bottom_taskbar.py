from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools/apply_classic_bottom_taskbar.py"


SHELL_GEOMETRY = '''"""Shared geometry for the desktop workspace and classic shell bar."""

from ..constants import BOTTOM_BARS_HEIGHT, MENU_BAR_HEIGHT


def global_bar_row(screen_h):
    """Return the terminal row occupied by the global shell bar."""
    height = max(0, int(screen_h))
    if height <= 0:
        return 0
    if BOTTOM_BARS_HEIGHT:
        return max(0, height - int(BOTTOM_BARS_HEIGHT))
    return 0


def workspace_top_row():
    """Return the first row available to desktop content and windows."""
    return max(0, int(MENU_BAR_HEIGHT))


def workspace_bottom_exclusive(screen_h):
    """Return the first row reserved below the desktop workspace."""
    height = max(0, int(screen_h))
    bottom = max(0, height - max(0, int(BOTTOM_BARS_HEIGHT)))
    return max(workspace_top_row(), bottom)


def workspace_height(screen_h):
    """Return the number of rows available to windows and desktop content."""
    return max(0, workspace_bottom_exclusive(screen_h) - workspace_top_row())
'''


FOCUSED_TESTS = '''import types
import unittest
from unittest import mock

from retrotui.constants import BOTTOM_BARS_HEIGHT, MENU_BAR_HEIGHT
from retrotui.core import rendering
from retrotui.core.shell_geometry import (
    global_bar_row,
    workspace_bottom_exclusive,
    workspace_top_row,
)
from retrotui.ui.menu import Menu
from retrotui.ui.window import Window


class ClassicBottomTaskbarTests(unittest.TestCase):
    def test_workspace_reserves_one_bottom_row(self):
        self.assertEqual(MENU_BAR_HEIGHT, 0)
        self.assertEqual(BOTTOM_BARS_HEIGHT, 1)
        self.assertEqual(workspace_top_row(), 0)
        self.assertEqual(global_bar_row(24), 23)
        self.assertEqual(workspace_bottom_exclusive(24), 23)

    def test_global_menu_draws_on_bottom_and_opens_upward(self):
        menu = Menu({"File": [("Open", "open"), ("Exit", "exit")]})
        menu.active = True
        stdscr = types.SimpleNamespace(getmaxyx=lambda: (24, 80))

        with (
            mock.patch("retrotui.ui.menu.safe_addstr") as safe_addstr,
            mock.patch("retrotui.ui.menu.draw_box"),
        ):
            menu.draw_bar(stdscr, 80, frame_size=(24, 80))
            menu.draw_dropdown(stdscr, frame_size=(24, 80))

        self.assertEqual(menu.bar_row(), 23)
        self.assertTrue(any(call.args[1] == 23 for call in safe_addstr.call_args_list))
        rect = menu.get_dropdown_rect()
        self.assertIsNotNone(rect)
        _x, y, _w, h = rect
        self.assertEqual(y + h, 23)

    def test_start_button_click_uses_bottom_row(self):
        menu = Menu({"File": [("Open", "open")]})
        stdscr = types.SimpleNamespace(getmaxyx=lambda: (24, 80))
        with mock.patch("retrotui.ui.menu.safe_addstr"):
            menu.draw_bar(stdscr, 80, frame_size=(24, 80))

        result = menu.handle_click(1, 23)

        self.assertIsNone(result)
        self.assertTrue(menu.active)
        self.assertEqual(menu.selected_menu, 0)
        self.assertFalse(menu.hit_test_menu_item(1, 0))

    def test_taskbar_buttons_render_on_bottom_row(self):
        stdscr = types.SimpleNamespace(getmaxyx=lambda: (20, 80))
        app = types.SimpleNamespace(
            stdscr=stdscr,
            windows=[types.SimpleNamespace(minimized=True, title="Notes")],
            menu=types.SimpleNamespace(
                menu_items_right_x=lambda: 20,
                right_reserved_start_x=lambda width: 70,
            ),
        )

        with mock.patch.object(rendering, "safe_addstr") as safe_addstr:
            rendering.draw_taskbar(app)

        self.assertTrue(
            any(
                call.args[1] == 19 and call.args[3] == "[Notes]"
                for call in safe_addstr.call_args_list
            )
        )

    def test_maximized_window_uses_workspace_above_taskbar(self):
        window = Window("Test", 5, 4, 30, 10)

        window.toggle_maximize(80, 24)

        self.assertEqual(window.y, 0)
        self.assertEqual(window.h, 23)
        self.assertEqual(window.y + window.h, global_bar_row(24))


if __name__ == "__main__":
    unittest.main()
'''


def replace_function(source: str, name: str, next_name: str, body: str) -> str:
    pattern = rf"def {name}\(\) -> None:\n.*?\n\n\ndef {next_name}"
    replacement = (
        f"def {name}() -> None:\n"
        f"    write_new(\n"
        f"        {('retrotui/core/shell_geometry.py' if name == 'add_shell_geometry' else 'tests/test_classic_bottom_taskbar.py')!r},\n"
        f"        {body!r},\n"
        f"    )\n\n\n"
        f"def {next_name}"
    )
    updated, count = re.subn(pattern, replacement, source, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"could not repair {name}")
    return updated


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    source = replace_function(source, "add_shell_geometry", "patch_rendering", SHELL_GEOMETRY)
    source = replace_function(source, "add_focused_tests", "remove_temporary_gate_files", FOCUSED_TESTS)
    source = source.replace(
        '        "tools/apply_classic_bottom_taskbar.py",\n'
        '        ".github/workflows/apply-classic-bottom-taskbar.yml",\n',
        '        "tools/apply_classic_bottom_taskbar.py",\n'
        '        "tools/bootstrap_classic_bottom_taskbar.py",\n'
        '        ".github/workflows/apply-classic-bottom-taskbar.yml",\n',
        1,
    )
    TARGET.write_text(source, encoding="utf-8")
    subprocess.run([sys.executable, str(TARGET)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()

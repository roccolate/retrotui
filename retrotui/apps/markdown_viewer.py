"""Markdown viewer window for RetroTUI."""

import curses
import os
import re

from ..core.actions import ActionResult, ActionType, AppAction
from ..ui.menu import WindowMenu
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr


class MarkdownViewerWindow(Window):
    """Read-only viewer for Markdown files with basic formatting."""

    def __init__(self, x, y, w, h, filepath=None):
        super().__init__("Markdown Viewer", x, y, w, h, content=[])
        self.window_menu = WindowMenu(
            {
                "File": [
                    ("Open...        O", "md_open"),
                    ("Reload         R", "md_reload"),
                    ("-------------", None),
                    ("Close          Q", "md_close"),
                ],
                "View": [
                    ("Scroll Up      Up", None),
                    ("Scroll Down    Down", None),
                ],
            }
        )
        self.filepath = None
        self.raw_content = []
        self.scroll_offset = 0
        self.status_message = ""

        if filepath:
            self.open_path(filepath)

    def open_path(self, filepath):
        """Load and parse markdown file."""
        path = os.path.realpath(os.path.expanduser(str(filepath)))
        if not os.path.isfile(path):
            return ActionResult(ActionType.ERROR, f"Not a file: {path}")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                self.raw_content = f.readlines()
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        self.filepath = path
        self.scroll_offset = 0
        self.status_message = f"Opened {os.path.basename(path)}"
        self._update_title()
        return None

    def _update_title(self):
        if self.filepath:
            self.title = f"Markdown Viewer - {os.path.basename(self.filepath)}"
        else:
            self.title = "Markdown Viewer"

    def _rows_visible(self):
        _, _, _, bh = self.body_rect()
        return max(1, bh - 1) # Space for status line

    def _max_scroll(self):
        return max(0, len(self.raw_content) - self._rows_visible())

    def draw(self, stdscr):
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        if bw <= 0 or bh <= 0:
            return

        # Clear body
        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, " " * bw, body_attr)

        visible_rows = self._rows_visible()
        self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))

        in_code_block = False

        for row in range(visible_rows):
            idx = self.scroll_offset + row
            if idx >= len(self.raw_content):
                break
            
            line = self.raw_content[idx].rstrip("\r\n")
            
            # 1. Code block detection
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                safe_addstr(stdscr, by + row, bx, line[:bw].ljust(bw), theme_attr("menubar"))
                continue

            if in_code_block:
                # Use a specific color for code
                code_attr = curses.color_pair(4) if curses.can_change_color() else body_attr
                safe_addstr(stdscr, by + row, bx, line[:bw].ljust(bw), code_attr | curses.A_BOLD)
                continue

            # 2. Header detection
            if line.startswith("#"):
                header_level = len(line) - len(line.lstrip("#"))
                clean_line = line.lstrip("#").strip()
                attr = curses.A_BOLD | curses.A_UNDERLINE
                if header_level == 1:
                    attr |= theme_attr("menubar")
                safe_addstr(stdscr, by + row, bx, clean_line[:bw].ljust(bw), attr)
                continue

            # 3. List detection
            stripped = line.lstrip()
            if stripped.startswith(("- ", "* ", "+ ")):
                bullet = "\u2022" if curses.can_change_color() else "-"
                indent = "  " * ( (len(line) - len(stripped)) // 2 + 1)
                safe_addstr(stdscr, by + row, bx, indent + bullet + " ", curses.A_BOLD)
                self._render_line(stdscr, by + row, bx + len(indent) + 2, stripped[2:], bw - (len(indent) + 2), body_attr)
                continue

            # 4. Horizontal rule
            if line.strip() in ("---", "***", "___"):
                safe_addstr(stdscr, by + row, bx, "\u2500" * bw, body_attr)
                continue

            # 4. Normal line with inline bold support
            self._render_line(stdscr, by + row, bx, line, bw, body_attr)

        # Status line
        status = self.status_message or "Arrows scroll | O open | R reload | Q close"
        safe_addstr(stdscr, by + bh - 1, bx, status[:bw].ljust(bw), theme_attr("status"))

        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def _render_line(self, stdscr, y, x, line, bw, base_attr):
        """Render a single line with inline formatting (bold)."""
        current_x = x
        parts = re.split(r"(\*\*.*?\*\*)", line)
        
        for part in parts:
            if current_x - x >= bw:
                break
                
            attr = base_attr
            text = part
            
            if part.startswith("**") and part.endswith("**") and len(part) > 3:
                attr |= curses.A_BOLD
                text = part[2:-2]
            
            # Truncate if needed
            remaining_w = bw - (current_x - x)
            chunk = text[:remaining_w]
            
            safe_addstr(stdscr, y, current_x, chunk, attr)
            current_x += len(chunk)

    def handle_key(self, key):
        key_code = normalize_key_code(key)

        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self.execute_action(action)
            return None

        if key_code in (ord("q"), ord("Q")):
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        if key_code in (ord("o"), ord("O")):
            return ActionResult(ActionType.REQUEST_OPEN_PATH)
        if key_code in (ord("r"), ord("R")):
            if self.filepath:
                return self.open_path(self.filepath)
            return None

        if key_code == getattr(curses, "KEY_UP", -1):
            self.scroll_offset = max(0, self.scroll_offset - 1)
        elif key_code == getattr(curses, "KEY_DOWN", -1):
            self.scroll_offset = min(self._max_scroll(), self.scroll_offset + 1)
        elif key_code == getattr(curses, "KEY_PPAGE", -1):
            self.scroll_offset = max(0, self.scroll_offset - self._rows_visible())
        elif key_code == getattr(curses, "KEY_NPAGE", -1):
            self.scroll_offset = min(self._max_scroll(), self.scroll_offset + self._rows_visible())
        elif key_code == getattr(curses, "KEY_HOME", -1):
            self.scroll_offset = 0
        elif key_code == getattr(curses, "KEY_END", -1):
            self.scroll_offset = self._max_scroll()

        return None

    def handle_click(self, mx, my):
        if self.window_menu:
            action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
            if action:
                return self.execute_action(action)
        return None

    def handle_hover(self, mx, my):
        if self.window_menu:
            return self.window_menu.handle_hover(mx, my, self.x, self.y, self.w)
        return False

    def execute_action(self, action):
        if action == "md_open":
            return ActionResult(ActionType.REQUEST_OPEN_PATH)
        if action == "md_reload":
            if self.filepath:
                return self.open_path(self.filepath)
        if action == "md_close":
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

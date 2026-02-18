"""Character Map app (minimal) for tests."""
from __future__ import annotations

import curses
import unicodedata

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr
from ..core.clipboard import copy_text
try:
    import pyperclip
except Exception:
    pyperclip = None


class CharacterMapWindow(Window):
    def __init__(self, x, y, w, h):
        super().__init__("Character Map", x, y, max(40, w), max(12, h), content=[], resizable=False)
        # Build a small block of characters for tests (ASCII 32-126)
        self.chars = [chr(i) for i in range(32, 126)]
        self.selected = None
        self.search = ""
        self.page = 0

    def draw(self, stdscr):
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        per_line = max(8, bw // 2)
        per_page = max(1, (bh) * per_line)
        start = self.page * per_page
        for row_idx in range(bh):
            line_chars = self.chars[start + row_idx * per_line: start + (row_idx + 1) * per_line]
            if not line_chars:
                break
            line = ' '.join(line_chars)
            safe_addstr(stdscr, by + row_idx, bx, line[:bw], body_attr)
        # page indicator
        safe_addstr(stdscr, by + bh - 1, bx + max(0, bw - 12), f"Page {self.page+1}", body_attr)

    def handle_click(self, mx, my, bstate=None):
        bx, by, bw, bh = self.body_rect()
        if not (by <= my < by + bh):
            return None
        # Map click to index simplistically: column based
        rel_y = my - by
        per_line = max(8, bw // 2)
        per_page = max(1, (bh) * per_line)
        idx = self.page * per_page + rel_y * per_line
        if 0 <= idx < len(self.chars):
            ch = self.chars[idx]
            info = {
                'char': ch,
                'codepoint': ord(ch),
                'name': unicodedata.name(ch, '<unknown>'),
            }
            self.selected = info
            return info
        return None

    def handle_key(self, key):
        # 'c' copies selected char to clipboard if present
        if getattr(key, '__int__', None) and int(key) == ord('c') and self.selected:
            copy_text(self.selected['char'])
            if pyperclip:
                try:
                    pyperclip.copy(self.selected['char'])
                except Exception:
                    pass
            return None
        # page navigation
        if getattr(key, '__int__', None):
            ik = int(key)
            if ik == curses.KEY_RIGHT:
                self.page += 1
            elif ik == curses.KEY_LEFT and self.page > 0:
                self.page -= 1
        return None

"""Character Map app (minimal) for tests."""
from __future__ import annotations

import curses
import unicodedata

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr


class CharacterMapWindow(Window):
    def __init__(self, x, y, w, h):
        super().__init__("Character Map", x, y, max(40, w), max(12, h), content=[], resizable=False)
        # Build a small block of characters for tests (ASCII 32-126)
        self.chars = [chr(i) for i in range(32, 96)]
        self.selected = None
        self.search = ""

    def draw(self, stdscr):
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        per_line = max(8, bw // 2)
        for i in range(0, len(self.chars), per_line):
            line = ' '.join(self.chars[i : i + per_line])
            safe_addstr(stdscr, by + (i // per_line), bx, line[:bw], body_attr)

    def handle_click(self, mx, my, bstate=None):
        bx, by, bw, bh = self.body_rect()
        if not (by <= my < by + bh):
            return None
        # Map click to index simplistically: column based
        rel_y = my - by
        per_line = max(8, bw // 2)
        idx = rel_y * per_line
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
            from ..core.clipboard import copy_text

            copy_text(self.selected['char'])
        return None

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
        per_line = max(4, bw // 2)
        per_page = max(1, (bh) * per_line)
        total_pages = (len(self.chars) + per_page - 1) // per_page
        start = self.page * per_page
        for row_idx in range(bh):
            line_chars = self.chars[start + row_idx * per_line: start + (row_idx + 1) * per_line]
            if not line_chars:
                break
            line = ' '.join(line_chars)
            safe_addstr(stdscr, by + row_idx, bx, line[:bw], body_attr)
        # page indicator (current/total)
        safe_addstr(stdscr, by + bh - 1, bx + max(0, bw - 16), f"Page {self.page+1}/{max(1,total_pages)}", body_attr)

    def handle_click(self, mx, my, bstate=None):
        bx, by, bw, bh = self.body_rect()
        if not (by <= my < by + bh):
            return None
        # Map click to grid index using column and row
        rel_y = my - by
        rel_x = mx - bx
        per_line = max(4, bw // 2)
        per_page = max(1, (bh) * per_line)
        col = rel_x // 2
        idx = self.page * per_page + rel_y * per_line + col
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
        # simple page navigation: 'n'next, 'p'prev
        if getattr(key, '__int__', None):
            ik = int(key)
            if ik == ord('n'):
                self.page += 1
            elif ik == ord('p') and self.page > 0:
                self.page -= 1
        # arrow keys already handled below
        # page navigation
        if getattr(key, '__int__', None):
            ik = int(key)
            if ik == curses.KEY_RIGHT:
                self.page += 1
            elif ik == curses.KEY_LEFT and self.page > 0:
                self.page -= 1
        # clamp page bounds
        try:
            _, _, bw, bh = self.body_rect()
            per_line = max(4, bw // 2)
            per_page = max(1, (bh) * per_line)
            total_pages = (len(self.chars) + per_page - 1) // per_page
            if self.page < 0:
                self.page = 0
            if self.page >= total_pages:
                self.page = max(0, total_pages - 1)
        except Exception:
            pass
        return None

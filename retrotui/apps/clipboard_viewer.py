"""Clipboard Viewer window (minimal for tests)."""
from __future__ import annotations

import curses
from typing import List

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr
from ..core.clipboard import paste_text, copy_text, clear_clipboard


class ClipboardViewerWindow(Window):
    def __init__(self, x, y, w, h, history_size=10):
        super().__init__("Clipboard", x, y, max(30, w), max(10, h), content=[], resizable=False)
        self.history_size = history_size
        self.history: List[str] = []
        self._refresh_from_clipboard()

    def _refresh_from_clipboard(self):
        text = paste_text(sync_system=False)
        if text and (not self.history or self.history[0] != text):
            self.history.insert(0, text)
            self.history = self.history[: self.history_size]

    def draw(self, stdscr):
        if not self.visible:
            return
        self._refresh_from_clipboard()
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        for i, item in enumerate(self.history[: bh]):
            safe_addstr(stdscr, by + i, bx, item[:bw].ljust(bw), body_attr)
        if not self.history:
            safe_addstr(stdscr, by, bx, "<clipboard empty>"[:bw], body_attr)

    def handle_click(self, mx, my, bstate=None):
        bx, by, bw, bh = self.body_rect()
        if not (by <= my < by + bh):
            return None
        idx = my - by
        if 0 <= idx < len(self.history):
            copy_text(self.history[idx])
        return None

    def handle_key(self, key):
        # 'c' clears clipboard
        if getattr(key, '__int__', None) and int(key) == ord('c'):
            clear_clipboard()
            self.history = []
        return None

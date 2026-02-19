"""Clipboard Viewer window (minimal for tests)."""
from __future__ import annotations

import curses
from typing import List

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr
from ..core.clipboard import paste_text, copy_text, clear_clipboard
try:
    import pyperclip
except Exception:
    pyperclip = None


class ClipboardViewerWindow(Window):
    def __init__(self, x, y, w, h, history_size=10):
        super().__init__("Clipboard", x, y, max(30, w), max(10, h), content=[], resizable=False)
        self.history_size = history_size
        self.history: List[str] = []
        self.selected_index = 0
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
            attr = body_attr
            if i == self.selected_index:
                try:
                    sel_attr = theme_attr("selected")
                    # combine, but fall back to body_attr if theme_attr is not available
                    attr = body_attr | (sel_attr or 0)
                except Exception:
                    attr = body_attr
            safe_addstr(stdscr, by + i, bx, item[:bw].ljust(bw), attr)
        if not self.history:
            safe_addstr(stdscr, by, bx, "<clipboard empty>"[:bw], body_attr)

    def handle_click(self, mx, my, bstate=None):
        bx, by, bw, bh = self.body_rect()
        if not (by <= my < by + bh):
            return None
        idx = my - by
        if 0 <= idx < len(self.history):
            copy_text(self.history[idx])
            if pyperclip:
                try:
                    pyperclip.copy(self.history[idx])
                except Exception:
                    pass
            # update selection to clicked item
            self.selected_index = idx
        return None

    def handle_key(self, key):
        # 'c' clears clipboard
        if getattr(key, '__int__', None) and int(key) == ord('c'):
            clear_clipboard()
            self.history = []
            self.selected_index = 0
        # 'y' yank top history to system clipboard if available
        if getattr(key, '__int__', None) and int(key) == ord('y') and self.history:
            if pyperclip:
                try:
                    pyperclip.copy(self.history[0])
                except Exception:
                    pass
        # navigation: up/down and enter to copy
        if getattr(key, '__int__', None):
            k = int(key)
            try:
                import curses as _c

                KEY_UP = _c.KEY_UP
                KEY_DOWN = _c.KEY_DOWN
            except Exception:
                KEY_UP = -1
                KEY_DOWN = -2

            if k in (KEY_UP, ord('k')):
                if self.history:
                    self.selected_index = max(0, self.selected_index - 1)
            if k in (KEY_DOWN, ord('j')):
                if self.history:
                    self.selected_index = min(len(self.history) - 1, self.selected_index + 1)
            # Enter/Return to copy selected
            if k in (10, 13):
                if self.history and 0 <= self.selected_index < len(self.history):
                    copy_text(self.history[self.selected_index])
                    if pyperclip:
                        try:
                            pyperclip.copy(self.history[self.selected_index])
                        except Exception:
                            pass
        return None

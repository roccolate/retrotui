"""
ContextMenu component.

Simple position-based context menu compatible with the existing `Menu` style.
"""
from __future__ import annotations

import curses

from ..constants import SB_H
from ..utils import draw_box, safe_addstr, theme_attr


class ContextMenu:
    def __init__(self, items: list[tuple[str, object]]):
        """Items is a list of (label, action) where action may be None for a separator."""
        self.items = items or []
        self.x = 0
        self.y = 0
        self.w = 0
        self.h = 0
        self.opened = False
        self.selected = 0

    def open_at(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        max_label = max((len(label) for label, _ in self.items), default=0)
        self.w = max_label + 2
        self.h = len(self.items) + 2
        # move selection to first selectable
        self.selected = self._first_selectable()
        self.opened = True

    def close(self) -> None:
        self.opened = False

    def is_open(self) -> bool:
        return self.opened

    def _first_selectable(self) -> int:
        for i, (_, action) in enumerate(self.items):
            if action is not None:
                return i
        return 0

    def draw(self, stdscr) -> None:
        if not self.opened:
            return

        x = self.x
        y = self.y
        w = self.w
        h = self.h

        item_attr = theme_attr("menu_item")
        sel_attr = theme_attr("menu_selected")

        draw_box(stdscr, y, x - 1, h, w + 2, item_attr, double=False)

        for i, (label, action) in enumerate(self.items):
            attr = sel_attr if i == self.selected else item_attr
            if action is None:
                safe_addstr(stdscr, y + 1 + i, x, SB_H * w, item_attr)
            else:
                safe_addstr(stdscr, y + 1 + i, x, f' {label.ljust(w - 2)} ', attr)

    def get_rect(self) -> tuple[int, int, int, int] | None:
        if not self.opened:
            return None
        return (self.x - 1, self.y, self.w + 2, self.h)

    def hit_test(self, mx: int, my: int) -> bool:
        rect = self.get_rect()
        if rect is None:
            return False
        rx, ry, rw, rh = rect
        return rx <= mx < rx + rw and ry <= my < ry + rh

    def handle_click(self, mx: int, my: int):
        if not self.opened:
            return None
        if not self.hit_test(mx, my):
            self.close()
            return None

        # inside menu
        idx = my - (self.y + 1)
        if 0 <= idx < len(self.items):
            label, action = self.items[idx]
            if action is not None:
                self.close()
                return action
        return None

    def handle_key(self, key: int):
        if not self.opened:
            return None

        if key == curses.KEY_UP:
            self._move(-1)
            return None
        if key == curses.KEY_DOWN:
            self._move(1)
            return None
        if key in (curses.KEY_ENTER, 10, 13):
            label, action = self.items[self.selected]
            if action is not None:
                self.close()
                return action
            return None
        if key == 27:  # Escape
            self.close()
            return None
        return None

    def _move(self, delta: int) -> None:
        if not self.items:
            return
        for _ in range(len(self.items)):
            self.selected = (self.selected + delta) % len(self.items)
            if self.items[self.selected][1] is not None:
                return

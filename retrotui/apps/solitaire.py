"""Solitaire (Klondike) minimal implementation for tests."""
from __future__ import annotations

import curses
from typing import List

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr


class SolitaireWindow(Window):
    def __init__(self, x, y, w, h):
        super().__init__("Solitaire", x, y, max(40, w), max(12, h), content=[], resizable=False)
        # Minimal internal state for tests
        self.columns = [[] for _ in range(7)]
        self.foundations = [[] for _ in range(4)]
        self.stock = []
        self.waste = []
        self.selected = None
        self.moves = 0
        self.victory = False

    def draw(self, stdscr):
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        # Draw placeholder board
        safe_addstr(stdscr, by, bx, "[Solitaire board placeholder]", body_attr)

    def handle_click(self, mx, my, bstate=None):
        # Toggle selection on any click for tests
        if self.selected is None:
            self.selected = (mx, my)
        else:
            self.selected = None
            self.moves += 1
        return None

    def handle_key(self, key):
        # 'q' to close
        if isinstance(key, int) and key == ord('q'):
            from ..core.actions import ActionResult, ActionType, AppAction

            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

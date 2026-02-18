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
        # columns hold tuples of (card_str, face_up: bool)
        self.columns = [[] for _ in range(7)]
        self.foundations = [[] for _ in range(4)]
        self.stock = []
        self.waste = []
        # build and deal a simple deck (no face-down tracking for simplicity)
        suits = ('H', 'D', 'C', 'S')
        ranks = ['A'] + [str(i) for i in range(2, 11)] + ['J', 'Q', 'K']
        deck = [r + s for s in suits for r in ranks]
        import random

        random.shuffle(deck)
        # deal to columns: column i gets i+1 cards (top is last)
        pos = 0
        for i in range(7):
            cnt = i + 1
            slice_cards = deck[pos : pos + cnt]
            # all but top are face-down
            col = [(c, False) for c in slice_cards[:-1]]
            if slice_cards:
                col.append((slice_cards[-1], True))
            self.columns[i] = col
            pos += cnt
        self.stock = deck[pos:]
        self.selected = None
        self.moves = 0
        self.victory = False
        # simple double-click detection (store last click pos)
        self._last_click = None

    # Helper card utilities
    def _rank_value(self, card: str) -> int:
        # accept tuple (card, face_up) or raw card
        if isinstance(card, tuple):
            card = card[0]
        r = card[:-1]
        if r == 'A':
            return 1
        if r == 'J':
            return 11
        if r == 'Q':
            return 12
        if r == 'K':
            return 13
        try:
            return int(r)
        except Exception:
            return 0

    def _suit(self, card: str) -> str:
        if isinstance(card, tuple):
            card = card[0]
        return card[-1]

    def _can_move_to_foundation(self, card: str, foundation: list) -> bool:
        # foundation is built by suit ascending A..K
        if not foundation:
            return self._rank_value(card) == 1
        top = foundation[-1]
        return self._suit(top) == self._suit(card) and self._rank_value(card) == self._rank_value(top) + 1

    def _auto_move_to_foundation(self) -> bool:
        # Try waste first
        if self.waste:
            card = self.waste[-1]
            for f in self.foundations:
                if self._can_move_to_foundation(card, f):
                    self.waste.pop()
                    f.append(card)
                    return True
        # Try each column top
        for col in self.columns:
            if not col:
                continue
            top, face_up = col[-1]
            if not face_up:
                continue
            card = top
            for f in self.foundations:
                if self._can_move_to_foundation(card, f):
                    col.pop()
                    f.append(card)
                    # reveal new top if present
                    if col:
                        c, _ = col[-1]
                        col[-1] = (c, True)
                    return True
        return False

    def _drain_auto_moves(self) -> int:
        """Repeatedly attempt auto-moves to foundations until none are possible.
        Returns the number of moves performed."""
        moved = 0
        while True:
            # Prefer single-card moves from waste and columns to foundations
            if self._auto_move_to_foundation():
                moved += 1
                continue
            # Try moving sequences between columns to free more single-card moves
            if self._auto_move_sequence_to_column():
                moved += 1
                continue
            break
        return moved

    def _is_red(self, suit: str) -> bool:
        return suit in ("H", "D")

    def _can_place_sequence_on(self, target_card: str, seq_card: str) -> bool:
        # target_card must be face-up on destination column; seq_card is first card of sequence
        if target_card is None:
            # empty column: only allow if sequence starts with King
            return self._rank_value(seq_card) == 13
        # colors must alternate and rank must be exactly one higher
        t_color = self._is_red(self._suit(target_card))
        s_color = self._is_red(self._suit(seq_card))
        return t_color != s_color and self._rank_value(target_card) == self._rank_value(seq_card) + 1

    def _auto_move_sequence_to_column(self) -> bool:
        # Try moving any face-up sequence to another column where it fits
        for src_idx, col in enumerate(self.columns):
            if not col:
                continue
            # find first face-up index
            first_up = None
            for i, (_, up) in enumerate(col):
                if up:
                    first_up = i
                    break
            if first_up is None:
                continue
            seq = col[first_up:]
            seq_first_card = seq[0][0]
            # try each target column
            for tgt_idx, tgt_col in enumerate(self.columns):
                if tgt_idx == src_idx:
                    continue
                if tgt_col:
                    tgt_top, tgt_up = tgt_col[-1]
                    if not tgt_up:
                        continue
                    if self._can_place_sequence_on(tgt_top, seq_first_card):
                        # move sequence
                        moving = col[first_up:]
                        self.columns[tgt_idx].extend(moving)
                        del self.columns[src_idx][first_up:]
                        # reveal new top of source
                        if self.columns[src_idx]:
                            c, _ = self.columns[src_idx][-1]
                            self.columns[src_idx][-1] = (c, True)
                        return True
                else:
                    # empty column: allow if seq starts with King
                    if self._rank_value(seq_first_card) == 13:
                        moving = col[first_up:]
                        self.columns[tgt_idx].extend(moving)
                        del self.columns[src_idx][first_up:]
                        if self.columns[src_idx]:
                            c, _ = self.columns[src_idx][-1]
                            self.columns[src_idx][-1] = (c, True)
                        return True
        return False

    def draw(self, stdscr):
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        # Draw stock/waste/foundations top-line
        stock_disp = f"Stock:{len(self.stock)}"
        waste_disp = f"Waste:{self.waste[-1] if self.waste else '--'}"
        found_disp = ' '.join([f"F{idx+1}:{(f[-1] if f else '--')}" for idx, f in enumerate(self.foundations)])
        safe_addstr(stdscr, by, bx, stock_disp + '  ' + waste_disp + '  ' + found_disp, body_attr)
        # Draw columns (top card or empty)
        for i, col in enumerate(self.columns):
            if not col:
                top = '--'
            else:
                top_card, up = col[-1]
                top = top_card if up else '--'
            safe_addstr(stdscr, by + 2 + i, bx, f"C{i+1}: {top}", body_attr)

    def handle_click(self, mx, my, bstate=None):
        # Toggle selection on any click for tests
        if self.selected is None:
            self.selected = (mx, my)
            # detect double-click on same spot -> try auto-move to foundation
            if self._last_click == (mx, my):
                moved = self._drain_auto_moves()
                if moved:
                    self.moves += moved
                    self.selected = None
        else:
            # normal second click: deselect
            self.selected = None
            self.moves += 1
        self._last_click = (mx, my)
        return None

    def handle_key(self, key):
        # 'q' to close
        if isinstance(key, int) and key == ord('q'):
            from ..core.actions import ActionResult, ActionType, AppAction

            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        # 's' to draw from stock to waste
        if getattr(key, '__int__', None) and int(key) == ord('s'):
            # Draw one card from stock to waste. If stock empty, reset from waste.
            if self.stock:
                card = self.stock.pop()
                self.waste.append(card)
                # After drawing, attempt a single-card auto-move from waste to foundations
                if self._auto_move_to_foundation():
                    self.moves += 1
            else:
                # recycle waste back to stock (flip over)
                if self.waste:
                    self.stock = list(reversed(self.waste))
                    self.waste = []
        # 'a' to auto-move all possible cards to foundations
        if getattr(key, '__int__', None) and int(key) == ord('a'):
            moved = self._drain_auto_moves()
            if moved:
                self.moves += moved
        return None

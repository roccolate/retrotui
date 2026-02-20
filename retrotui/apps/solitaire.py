"""Solitaire (Klondike) graphical implementation."""
from __future__ import annotations

import curses
import json
import random
from typing import List
from pathlib import Path

from ..ui.window import Window
from ..ui.menu import WindowMenu
from ..core.actions import AppAction, ActionResult, ActionType
from ..utils import safe_addstr, theme_attr


class SolitaireWindow(Window):
    def __init__(self, x, y, w, h):
        super().__init__("Solitaire", x, y, 46, max(22, h), content=[], resizable=False)
        self.window_menu = WindowMenu({
            "Game": [
                ("New Game (R)", "solitaire_new"),
                ("-", None),
                ("Close (Q)", AppAction.CLOSE_WINDOW)
            ]
        })
        self.best_moves = 9999
        self._load_high_scores()
        self._reset_game()

    def _score_file_path(self) -> Path:
        return Path.home() / ".config" / "retrotui" / "solitaire_scores.json"

    def _load_high_scores(self):
        try:
            path = self._score_file_path()
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    scores = json.load(f)
                    if "best_moves" in scores and isinstance(scores["best_moves"], int):
                        self.best_moves = scores["best_moves"]
        except Exception:
            pass

    def _save_high_scores(self):
        try:
            path = self._score_file_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"best_moves": self.best_moves}, f)
        except Exception:
            pass

    def _reset_game(self):
        self.columns = [[] for _ in range(7)]
        self.foundations = [[] for _ in range(4)]
        self.stock = []
        self.waste = []
        self.card_rects = {}
        
        suits = ('H', 'D', 'C', 'S')
        ranks = ['A'] + [str(i) for i in range(2, 11)] + ['J', 'Q', 'K']
        deck = [r + s for s in suits for r in ranks]
        random.shuffle(deck)
        
        pos = 0
        for i in range(7):
            cnt = i + 1
            slice_cards = deck[pos : pos + cnt]
            col = [(c, False) for c in slice_cards[:-1]]
            if slice_cards:
                col.append((slice_cards[-1], True))
            self.columns[i] = col
            pos += cnt
            
        self.stock = deck[pos:]
        self.selected = None
        self.moves = 0
        self.scroll_y = 0
        self.victory = False
        self._last_click = None

    def execute_action(self, action: str | AppAction) -> ActionResult | None:
        if action == "solitaire_new":
            self._reset_game()
            return ActionResult(ActionType.REFRESH)
        elif action == AppAction.CLOSE_WINDOW:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

    def _rank_value(self, card: str) -> int:
        if isinstance(card, tuple): card = card[0]
        r = card[:-1]
        if r == 'A': return 1
        if r == 'J': return 11
        if r == 'Q': return 12
        if r == 'K': return 13
        try: return int(r)
        except: return 0

    def _suit(self, card: str) -> str:
        if isinstance(card, tuple): card = card[0]
        return card[-1]

    def _is_red(self, suit: str) -> bool:
        return suit in ("H", "D")

    def _can_move_to_foundation(self, card: str, foundation: list) -> bool:
        if not foundation:
            return self._rank_value(card) == 1
        top = foundation[-1]
        return self._suit(top) == self._suit(card) and self._rank_value(card) == self._rank_value(top) + 1

    def _can_place_sequence_on(self, target_card: str|None, seq_card: str) -> bool:
        if target_card is None:
            return self._rank_value(seq_card) == 13
        t_color = self._is_red(self._suit(target_card))
        s_color = self._is_red(self._suit(seq_card))
        return t_color != s_color and self._rank_value(target_card) == self._rank_value(seq_card) + 1

    def _auto_move_to_foundation(self) -> bool:
        if self.waste:
            card = self.waste[-1]
            for f in self.foundations:
                if self._can_move_to_foundation(card, f):
                    self.waste.pop()
                    f.append(card)
                    return True
        for col in self.columns:
            if not col: continue
            top, face_up = col[-1]
            if not face_up: continue
            for f in self.foundations:
                if self._can_move_to_foundation(top, f):
                    col.pop()
                    f.append(top)
                    if col:
                        c, _ = col[-1]
                        col[-1] = (c, True)
                    return True
        return False

    def _check_victory(self):
        if sum(len(f) for f in self.foundations) == 52:
            self.victory = True
            if self.moves < self.best_moves:
                self.best_moves = self.moves
                self._save_high_scores()

    def _draw_card(self, stdscr, y, x, card: str|None, face_up: bool, selected: bool, body_attr: int, min_y: int = 0):
        from ..constants import C_ANSI_START
        _, by, _, bh = self.body_rect()
        max_y = by + bh

        def safe_add(dy, dx, text, attr_val):
            target_y = y + dy
            if min_y <= target_y < max_y:
                safe_addstr(stdscr, target_y, x + dx, text, attr_val)

        if card is None:
            safe_add(0, 0, "╭───╮", body_attr)
            safe_add(1, 0, "│   │", body_attr)
            safe_add(2, 0, "╰───╯", body_attr)
            return

        rank = card[:-1]
        suit = card[-1]
        suit_char = {'H': '♥', 'D': '♦', 'C': '♣', 'S': '♠'}.get(suit, suit)
        is_red = self._is_red(suit)
        
        color_attr = curses.color_pair(C_ANSI_START + curses.COLOR_RED) if is_red else body_attr
        attr = body_attr
        
        if selected:
            attr |= curses.A_REVERSE
            color_attr |= curses.A_REVERSE

        if not face_up:
            safe_add(0, 0, "╭───╮", attr)
            safe_add(1, 0, "│▒▒▒│", attr)
            safe_add(2, 0, "╰───╯", attr)
        else:
            safe_add(0, 0, "╭───╮", attr)
            safe_add(1, 0, "│", attr)
            safe_add(1, 1, f"{rank:<2}{suit_char}", color_attr | curses.A_BOLD)
            safe_add(1, 4, "│", attr)
            safe_add(2, 0, "╰───╯", attr)

    def draw(self, stdscr):
        if not self.visible: return
        
        bm_str = "---" if self.best_moves == 9999 else str(self.best_moves)
        
        if self.victory:
            self.title = f"Solitaire - YOU WON! 🎉 (Best: {bm_str})"
        else:
            self.title = f"Solitaire  ♟ {self.moves} (Best: {bm_str})"

        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        
        # Clear body to prevent ghosting from deep columns
        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, " " * bw, body_attr)
        
        self.card_rects = {}
        
        # 1. Stock
        sx, sy = bx + 2, by + 1
        self.card_rects[("stock", 0, 0)] = (sx, sy, 5, 3)
        if not self.stock:
            safe_addstr(stdscr, sy,   sx, "╭───╮", body_attr)
            safe_addstr(stdscr, sy+1, sx, "│ ⟳ │", body_attr)
            safe_addstr(stdscr, sy+2, sx, "╰───╯", body_attr)
        else:
            is_sel = self.selected == ("stock", 0, 0)
            self._draw_card(stdscr, sy, sx, self.stock[-1], False, is_sel, body_attr)

        # 2. Waste
        wx, wy = bx + 8, by + 1
        self.card_rects[("waste", 0, 0)] = (wx, wy, 5, 3)
        if not self.waste:
            self._draw_card(stdscr, wy, wx, None, True, False, body_attr)
        else:
            is_sel = self.selected == ("waste", 0, 0)
            self._draw_card(stdscr, wy, wx, self.waste[-1], True, is_sel, body_attr)

        # 3. Foundations
        for i in range(4):
            fx, fy = bx + 2 + (i + 3) * 6, by + 1
            self.card_rects[("found", i, 0)] = (fx, fy, 5, 3)
            f = self.foundations[i]
            if not f:
                self._draw_card(stdscr, fy, fx, None, True, False, body_attr)
            else:
                is_sel = self.selected == ("found", i, 0)
                self._draw_card(stdscr, fy, fx, f[-1], True, is_sel, body_attr)

        # 4. Columns
        max_col_h = 0
        for i, col in enumerate(self.columns):
            cx = bx + 2 + i * 6
            cy = by + 5 - getattr(self, 'scroll_y', 0)
            
            if not col:
                self.card_rects[("col", i, 0)] = (cx, cy, 5, 3)
                self._draw_card(stdscr, cy, cx, None, True, False, body_attr, min_y=by+4)
                max_col_h = max(max_col_h, 3)
                continue
                
            col_y_start = cy
            for j, (card, up) in enumerate(col):
                is_sel = False
                if self.selected and self.selected[0] == "col" and self.selected[1] == i and j >= self.selected[2]:
                    is_sel = True
                self._draw_card(stdscr, cy, cx, card, up, is_sel, body_attr, min_y=by+4)
                h = 3 if j == len(col) - 1 else (2 if up else 1)
                self.card_rects[("col", i, j)] = (cx, cy, 5, h)
                cy += 2 if up else 1
            max_col_h = max(max_col_h, cy + 2 - col_y_start)

        usable_h = bh - 5
        self.max_scroll = max(0, max_col_h - usable_h)
        self.scroll_y = max(0, min(getattr(self, 'scroll_y', 0), self.max_scroll))
        
        if self.max_scroll > 0:
            scroll_pct = self.scroll_y / self.max_scroll
            scroll_indicator_y = by + 5 + int(scroll_pct * (usable_h - 1))
            if scroll_indicator_y < by + bh:
                safe_addstr(stdscr, scroll_indicator_y, bx + bw - 1, "█", body_attr | curses.A_BOLD)

        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def handle_click(self, mx, my, bstate=None):
        if self.window_menu and (self.window_menu.active or self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w)):
            res = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
            if res: return self.execute_action(res)
            return None

        clicked = None
        for key, (cx, cy, cw, ch) in self.card_rects.items():
            if cx <= mx < cx + cw and cy <= my < cy + ch:
                clicked = key
                break
        
        if self._last_click == (mx, my) and clicked and clicked == self.selected:
            area, col_idx, card_idx = clicked
            if area in ("waste", "col"):
                if self._auto_move_to_foundation():
                    self.moves += 1
                    self.selected = None
                    self._check_victory()
            self._last_click = (mx, my)
            return None

        self._last_click = (mx, my)

        if not clicked:
            self.selected = None
            return None

        area, col_idx, card_idx = clicked

        if area == "stock":
            if self.stock:
                self.waste.append(self.stock.pop())
            else:
                self.stock = list(reversed(self.waste))
                self.waste = []
            self.selected = None
            self.moves += 1
            return None

        if self.selected is None:
            if area == "waste" and self.waste:
                self.selected = clicked
            elif area == "col":
                col = self.columns[col_idx]
                if col and card_idx < len(col) and col[card_idx][1]:
                    self.selected = clicked
                elif col and not col[-1][1] and card_idx == len(col)-1:
                    c, _ = col[-1]
                    col[-1] = (c, True)
                    self.moves += 1
            elif area == "found" and self.foundations[col_idx]:
                 self.selected = clicked
        else:
            sel_area, sel_col, sel_idx = self.selected
            
            if area == "col":
                moving = []
                if sel_area == "waste": moving = [(self.waste[-1], True)]
                elif sel_area == "found": moving = [(self.foundations[sel_col][-1], True)]
                elif sel_area == "col": moving = self.columns[sel_col][sel_idx:]
                
                target_col = self.columns[col_idx]
                target_top = target_col[-1][0] if target_col else None
                seq_first = moving[0][0]
                
                if self._can_place_sequence_on(target_top, seq_first):
                    self.columns[col_idx].extend(moving)
                    if sel_area == "waste": self.waste.pop()
                    elif sel_area == "found": self.foundations[sel_col].pop()
                    elif sel_area == "col":
                        del self.columns[sel_col][sel_idx:]
                        if self.columns[sel_col] and not self.columns[sel_col][-1][1]:
                            c, _ = self.columns[sel_col][-1]
                            self.columns[sel_col][-1] = (c, True)
                    self.moves += 1
                    
            elif area == "found":
                moving_card = None
                if sel_area == "waste": moving_card = self.waste[-1]
                elif sel_area == "col" and sel_idx == len(self.columns[sel_col]) - 1:
                    moving_card = self.columns[sel_col][-1][0]
                
                if moving_card and self._can_move_to_foundation(moving_card, self.foundations[col_idx]):
                    self.foundations[col_idx].append(moving_card)
                    if sel_area == "waste": self.waste.pop()
                    elif sel_area == "col":
                        self.columns[sel_col].pop()
                        if self.columns[sel_col] and not self.columns[sel_col][-1][1]:
                            c, _ = self.columns[sel_col][-1]
                            self.columns[sel_col][-1] = (c, True)
                    self.moves += 1
                    
            self.selected = None
            self._check_victory()
        
        return None

    def handle_key(self, key):
        if self.window_menu and self.window_menu.active:
            res = self.window_menu.handle_key(key)
            if res: return self.execute_action(res)
            return None

        from ..core.key_router import normalize_key_code
        kc = normalize_key_code(key)
        
        if kc == curses.KEY_UP:
            self.scroll_y = max(0, getattr(self, 'scroll_y', 0) - 1)
        elif kc == curses.KEY_DOWN:
            self.scroll_y = min(getattr(self, 'max_scroll', 0), getattr(self, 'scroll_y', 0) + 1)
        elif kc == curses.KEY_PPAGE:
            self.scroll_y = max(0, getattr(self, 'scroll_y', 0) - 5)
        elif kc == curses.KEY_NPAGE:
            self.scroll_y = min(getattr(self, 'max_scroll', 0), getattr(self, 'scroll_y', 0) + 5)

        if isinstance(key, int):
            if key == ord('q'):
                return self.execute_action(AppAction.CLOSE_WINDOW)
            elif key == ord('r'):
                return self.execute_action("solitaire_new")
        return None

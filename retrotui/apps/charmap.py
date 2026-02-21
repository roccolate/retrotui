"""Premium Character Map app for RetroTUI."""
from __future__ import annotations

import curses
import unicodedata

from ..ui.window import Window
from ..ui.menu import WindowMenu
from ..utils import safe_addstr, theme_attr, normalize_key_code
from ..core.clipboard import copy_text
from ..core.actions import ActionResult, ActionType, AppAction

try:
    import pyperclip
except Exception:
    pyperclip = None

UNICODE_BLOCKS = [
    ("Basic Latin", 0x0020, 0x007F),
    ("Latin-1 Supplement", 0x00A0, 0x00FF),
    ("Latin Extended-A", 0x0100, 0x017F),
    ("Greek and Coptic", 0x0370, 0x03FF),
    ("Cyrillic", 0x0400, 0x04FF),
    ("Currency Symbols", 0x20A0, 0x20CF),
    ("Letterlike Symbols", 0x2100, 0x214F),
    ("Arrows", 0x2190, 0x21FF),
    ("Mathematical Ops", 0x2200, 0x22FF),
    ("Box Drawing", 0x2500, 0x257F),
    ("Block Elements", 0x2580, 0x259F),
    ("Geometric Shapes", 0x25A0, 0x25FF),
    ("Dingbats", 0x2700, 0x27BF),
    ("Braille Patterns", 0x2800, 0x28FF),
]

class CharacterMapWindow(Window):
    def __init__(self, x, y, w, h):
        # Premium fixed size or responsive
        win_w = max(60, w)
        win_h = max(20, h)
        super().__init__("Character Map", x, y, win_w, win_h, content=[], resizable=True)
        
        self.block_idx = 0
        self.chars = []
        self._load_block()
        
        self.sel_idx = 0
        self.selected_char = self.chars[0] if self.chars else None
        
        # Menu setup
        range_items = []
        for i, (name, _, _) in enumerate(UNICODE_BLOCKS):
            range_items.append((name, f"block_{i}"))
            
        self.window_menu = WindowMenu({
            "Range": range_items,
            "Edit": [
                ("Copy Char    C", "copy_hex"),
                ("Copy Hex     H", "copy_hex_val"),
            ],
            "Help": [
                ("About Map", "about_map"),
            ]
        })

    def _load_block(self):
        name, start, end = UNICODE_BLOCKS[self.block_idx]
        self.chars = [chr(i) for i in range(start, end + 1)]
        self.status_message = f"Block: {name}"

    def _get_grid_dims(self, bw, bh):
        # Grid on the left, details on the right
        grid_w = bw - 22 # Reserved for details
        cols = max(1, grid_w // 3)
        rows = max(1, (bh - 2)) # Leave room for header/footer
        return cols, rows

    def draw(self, stdscr):
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        if bw < 30 or bh < 10:
            safe_addstr(stdscr, by, bx, "Window too small", body_attr)
            return

        cols, rows = self._get_grid_dims(bw, bh)
        per_page = cols * rows
        
        page = self.sel_idx // per_page
        start_idx = page * per_page
        
        # Draw Grid
        for r in range(rows):
            for c in range(cols):
                idx = start_idx + r * cols + c
                if idx >= len(self.chars):
                    break
                
                ch = self.chars[idx]
                cx = bx + c * 3
                cy = by + r + 1
                
                attr = body_attr
                if idx == self.sel_idx:
                    attr = theme_attr("menu_selected")
                
                safe_addstr(stdscr, cy, cx, f" {ch} ", attr)

        # Draw Detail Pane (Right Side)
        detail_x = bx + bw - 20
        # Vertical separator
        for r in range(bh):
            safe_addstr(stdscr, by + r, detail_x - 1, "\u2502", theme_attr("window_border"))
            
        if self.selected_char:
            ch = self.selected_char
            cp = ord(ch)
            try:
                name = unicodedata.name(ch, "UNKNOWN")
            except ValueError:
                name = "UNKNOWN"
            
            # Zoom area
            safe_addstr(stdscr, by + 1, detail_x + 5, "\u250c\u2500\u2500\u2500\u2510", body_attr)
            safe_addstr(stdscr, by + 2, detail_x + 5, f"\u2502 {ch} \u2502", body_attr | curses.A_BOLD)
            safe_addstr(stdscr, by + 3, detail_x + 5, "\u2514\u2500\u2500\u2500\u2518", body_attr)
            
            # Info
            safe_addstr(stdscr, by + 5, detail_x + 1, "Name:", theme_attr("menubar"))
            # Wrap name
            name_parts = [name[i:i+18] for i in range(0, len(name), 18)]
            for i, part in enumerate(name_parts[:3]):
                safe_addstr(stdscr, by + 6 + i, detail_x + 1, part, body_attr)
                
            safe_addstr(stdscr, by + 10, detail_x + 1, "Hex:", theme_attr("menubar"))
            safe_addstr(stdscr, by + 10, detail_x + 6, f"U+{cp:04X}", body_attr)
            
            safe_addstr(stdscr, by + 11, detail_x + 1, "Dec:", theme_attr("menubar"))
            safe_addstr(stdscr, by + 11, detail_x + 6, str(cp), body_attr)
            
            safe_addstr(stdscr, by + bh - 2, detail_x + 1, "Press 'C' to Copy", theme_attr("status"))

        # Footer
        footer = f" {UNICODE_BLOCKS[self.block_idx][0]} | Page {page+1} "
        safe_addstr(stdscr, by + bh - 1, bx, footer[:bw].ljust(bw), theme_attr("status"))

        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def handle_key(self, key):
        key_code = normalize_key_code(key)
        
        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self.execute_action(action)
            return None

        bx, by, bw, bh = self.body_rect()
        cols, rows = self._get_grid_dims(bw, bh)

        if key_code == curses.KEY_RIGHT:
            if self.sel_idx < len(self.chars) - 1:
                self.sel_idx += 1
        elif key_code == curses.KEY_LEFT:
            if self.sel_idx > 0:
                self.sel_idx -= 1
        elif key_code == curses.KEY_DOWN:
            if self.sel_idx + cols < len(self.chars):
                self.sel_idx += cols
        elif key_code == curses.KEY_UP:
            if self.sel_idx - cols >= 0:
                self.sel_idx -= cols
        elif key_code == curses.KEY_NPAGE:
            self.sel_idx = min(len(self.chars) - 1, self.sel_idx + cols * rows)
        elif key_code == curses.KEY_PPAGE:
            self.sel_idx = max(0, self.sel_idx - cols * rows)
        elif key_code in (ord('c'), ord('C')):
            if self.selected_char:
                copy_text(self.selected_char)
                if pyperclip: pyperclip.copy(self.selected_char)
        elif key_code in (ord('h'), ord('H')):
            if self.selected_char:
                hex_val = f"U+{ord(self.selected_char):04X}"
                copy_text(hex_val)
                if pyperclip: pyperclip.copy(hex_val)

        self.selected_char = self.chars[self.sel_idx]
        return None

    def handle_click(self, mx, my):
        if self.window_menu:
            action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
            if action:
                return self.execute_action(action)
        
        bx, by, bw, bh = self.body_rect()
        cols, rows = self._get_grid_dims(bw, bh)
        
        # Check if click in grid
        if bx <= mx < bx + cols * 3 and by + 1 <= my < by + 1 + rows:
            grid_x = (mx - bx) // 3
            grid_y = my - (by + 1)
            
            per_page = cols * rows
            page = self.sel_idx // per_page
            
            idx = page * per_page + grid_y * cols + grid_x
            if 0 <= idx < len(self.chars):
                self.sel_idx = idx
                self.selected_char = self.chars[idx]
                return {'char': self.selected_char, 'index': idx}

        return None

    def handle_hover(self, mx, my):
        if self.window_menu:
            return self.window_menu.handle_hover(mx, my, self.x, self.y, self.w)
        return False

    def execute_action(self, action):
        if action.startswith("block_"):
            self.block_idx = int(action.split("_")[1])
            self._load_block()
            self.sel_idx = 0
            self.selected_char = self.chars[0]
            return ActionResult(ActionType.REFRESH)
        
        if action == "copy_hex":
            if self.selected_char:
                copy_text(self.selected_char)
                if pyperclip: pyperclip.copy(self.selected_char)
            return None
        
        if action == "copy_hex_val":
            if self.selected_char:
                val = f"U+{ord(self.selected_char):04X}"
                copy_text(val)
                if pyperclip: pyperclip.copy(val)
            return None
            
        return None

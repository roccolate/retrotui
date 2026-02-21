"""Standalone App Manager application window."""

import curses

from dataclasses import replace
from ..core.actions import ActionResult, ActionType, AppAction
from ..ui.window import Window
from ..utils import draw_box, normalize_key_code, safe_addstr, theme_attr
from ..constants import ICONS, ICONS_ASCII


class AppManagerWindow(Window):
    """Window displaying apps grouped by categories in columns."""

    def __init__(self, x, y, w, h, app):
        super().__init__('App Manager', x, y, w, h, resizable=False)
        self.app = app
        
        base_icons = ICONS if self.app.use_unicode else ICONS_ASCII
        current_hidden = {x.strip().lower() for x in self.app.config.hidden_icons.split(",")} if self.app.config.hidden_icons else set()
        
        # choices grouped by category: {category: [[label, value, is_checked]]}
        self.categories = ["Apps", "Games"]
        self.choices = {cat: [] for cat in self.categories}
        
        for icon in base_icons:
            label = icon["label"]
            cat = icon.get("category", "Apps")
            if cat not in self.choices:
                self.choices[cat] = []
            self.choices[cat].append([label, label, label.lower() not in current_hidden])
            
        self.active_cat_idx = 0  # Which column is focused
        self.sel_indices = {cat: 0 for cat in self.categories}
        self.offsets = {cat: 0 for cat in self.categories}
        
        self.in_list = True
        self.selected_button = 0
        self.buttons = ['Save', 'Cancel']
        
        # Window dimensions
        self.w = max(60, w)
        self.h = max(20, h)
        self.visible_rows = self.h - 8 # Extra space for column headers
        
    def draw(self, stdscr):
        if not self.visible:
            return
            
        super().draw(stdscr)
        
        attr = theme_attr('window_body')
        sel_attr = attr | curses.A_REVERSE
        hdr_attr = attr | curses.A_BOLD
        
        # Instructions
        safe_addstr(stdscr, self.y + 1, self.x + 2, "Select apps to show on desktop/start menu", attr)
        
        col_w = (self.w - 6) // 2
        for c_idx, cat in enumerate(self.categories):
            col_x = self.x + 2 + c_idx * (col_w + 2)
            list_y = self.y + 4
            
            # Category Header
            header = f" {cat} "
            safe_addstr(stdscr, list_y - 2, col_x + (col_w - len(header)) // 2, header, hdr_attr)
            
            # List Border
            draw_box(stdscr, list_y - 1, col_x - 1, self.visible_rows + 2, col_w + 2, attr, double=False)
            
            items = self.choices[cat]
            offset = self.offsets[cat]
            sel_idx = self.sel_indices[cat]
            
            for i in range(self.visible_rows):
                idx = offset + i
                if idx < len(items):
                    label, _, checked = items[idx]
                    mark = '[x]' if checked else '[ ]'
                    text = f" {mark} {label}"
                    
                    is_focused = (self.in_list and self.active and self.active_cat_idx == c_idx and idx == sel_idx)
                    row_attr = sel_attr if is_focused else attr
                    safe_addstr(stdscr, list_y + i, col_x, text.ljust(col_w)[:col_w], row_attr)
                else:
                    safe_addstr(stdscr, list_y + i, col_x, ' ' * col_w, attr)

            # Scrollbar
            if len(items) > self.visible_rows:
                sb_x = col_x + col_w
                thumb_pos = int(offset / max(1, len(items) - self.visible_rows) * (self.visible_rows - 1))
                for i in range(self.visible_rows):
                    ch = '█' if i == thumb_pos else '░'
                    safe_addstr(stdscr, list_y + i, sb_x, ch, theme_attr('scrollbar'))

        # Buttons
        btn_y = self.y + self.h - 2
        btn_x_start = self.x + (self.w - sum(len(b) + 4 for b in self.buttons) - (len(self.buttons) - 1) * 2) // 2
        self._btn_y = btn_y
        self._btn_x_start = btn_x_start
        
        curr_x = btn_x_start
        for i, btn_text in enumerate(self.buttons):
            btn_w = len(btn_text) + 4
            btn_attr = theme_attr('button_selected') if (self.active and not self.in_list and self.selected_button == i) else theme_attr('button')
            safe_addstr(stdscr, btn_y, curr_x, f"[ {btn_text} ]", btn_attr)
            curr_x += btn_w + 2

    def handle_click(self, mx, my):
        col_w = (self.w - 6) // 2
        list_y = self.y + 4
        
        for c_idx, cat in enumerate(self.categories):
            col_x = self.x + 2 + c_idx * (col_w + 2)
            if col_x <= mx <= col_x + col_w and list_y <= my < list_y + self.visible_rows:
                click_idx = self.offsets[cat] + (my - list_y)
                if click_idx < len(self.choices[cat]):
                    self.in_list = True
                    self.active_cat_idx = c_idx
                    self.sel_indices[cat] = click_idx
                    self.choices[cat][click_idx][2] = not self.choices[cat][click_idx][2]
                    return True
                    
        if my == self._btn_y:
            curr_x = self._btn_x_start
            for i, btn_text in enumerate(self.buttons):
                btn_w = len(btn_text) + 4
                if curr_x <= mx < curr_x + btn_w:
                    self.in_list = False
                    self.selected_button = i
                    return self._activate_button()
                curr_x += btn_w + 2
                
        return False

    def handle_key(self, key):
        key_code = normalize_key_code(key)
        if key_code == 27: return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
            
        cat = self.categories[self.active_cat_idx]
        items = self.choices[cat]
        
        if key_code in (curses.KEY_UP, curses.KEY_DOWN):
            if not self.in_list:
                self.in_list = True
                return None
            if key_code == curses.KEY_UP:
                self.sel_indices[cat] = max(0, self.sel_indices[cat] - 1)
                if self.sel_indices[cat] < self.offsets[cat]:
                    self.offsets[cat] = self.sel_indices[cat]
            else:
                self.sel_indices[cat] = min(len(items) - 1, self.sel_indices[cat] + 1)
                if self.sel_indices[cat] >= self.offsets[cat] + self.visible_rows:
                    self.offsets[cat] = self.sel_indices[cat] - self.visible_rows + 1
            return None
            
        if key_code in (curses.KEY_LEFT, curses.KEY_RIGHT):
            if self.in_list:
                if key_code == curses.KEY_LEFT:
                    self.active_cat_idx = max(0, self.active_cat_idx - 1)
                else:
                    self.active_cat_idx = min(len(self.categories) - 1, self.active_cat_idx + 1)
            else:
                if key_code == curses.KEY_LEFT:
                    self.selected_button = max(0, self.selected_button - 1)
                else:
                    self.selected_button = min(len(self.buttons) - 1, self.selected_button + 1)
            return None
            
        if key_code == 9: # Tab
            self.in_list = not self.in_list
            return None
            
        if key_code in (32, 10, 13, curses.KEY_ENTER):
            if self.in_list:
                if items:
                    idx = self.sel_indices[cat]
                    items[idx][2] = not items[idx][2]
                return None
            else:
                return self._activate_button()
                
        return None

    def _activate_button(self):
        if self.selected_button == 0:  # Save
            # Collect all checked labels from all categories
            selected_set = set()
            for cat in self.categories:
                for label, _, checked in self.choices[cat]:
                    if checked:
                        selected_set.add(label.lower())
            
            base_icons = ICONS if self.app.use_unicode else ICONS_ASCII
            hidden = [icon["label"] for icon in base_icons if icon["label"].lower() not in selected_set]
            
            self.app.config = replace(self.app.config, hidden_icons=",".join(hidden))
            try:
                self.app.persist_config()
                self.app.refresh_icons()
                
                # Refresh Start Menu
                from ..ui.menu import DEFAULT_GLOBAL_ITEMS, Menu
                hidden_labels = {x.strip().lower() for x in self.app.config.hidden_icons.split(",")} if self.app.config.hidden_icons else set()
                filtered_menu_items = {}
                for category, items in DEFAULT_GLOBAL_ITEMS.items():
                    filtered_items = [item for item in items if item[0].split("  ")[0].lower() not in hidden_labels]
                    if filtered_items:
                        filtered_menu_items[category] = filtered_items
                self.app.menu = Menu(filtered_menu_items)
            except OSError as exc:
                return ActionResult(ActionType.SAVE_ERROR, str(exc))
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)

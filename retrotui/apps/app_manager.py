"""Standalone App Manager application window."""

import curses

from ..core.actions import ActionResult, ActionType, AppAction
from ..ui.window import Window
from ..utils import draw_box, normalize_key_code, safe_addstr, theme_attr
from ..constants import ICONS, ICONS_ASCII


class AppManagerWindow(Window):
    """Window displaying a scrollable list of checkboxes to select active desktop apps."""

    def __init__(self, x, y, w, h, app):
        super().__init__('App Manager', x, y, w, h, resizable=False)
        self.app = app
        
        base_icons = ICONS if self.app.use_unicode else ICONS_ASCII
        current_hidden = {x.strip().lower() for x in self.app.config.hidden_icons.split(",")} if self.app.config.hidden_icons else set()
        
        # choices format: [[label, value, is_checked]]
        self.choices = []
        for icon in base_icons:
            label = icon["label"]
            self.choices.append([label, label, label.lower() not in current_hidden])
            
        self.list_offset = 0
        self.list_selected = 0
        self.in_list = True  # Focus starts in list, not on buttons
        
        # We need a predictable height to fit some lines plus buttons
        self.h = max(18, h)
        self.w = max(46, w)
        self.visible_rows = self.h - 6  # Space for title, border and buttons
        
        self.buttons = ['Save', 'Cancel']
        self.selected_button = 0

    def draw(self, stdscr):
        if not self.visible:
            return
            
        super().draw(stdscr)
        
        attr = theme_attr('window_body')
        sel_attr = attr | curses.A_REVERSE
        
        # Draw instructions
        safe_addstr(stdscr, self.y + 1, self.x + 2, "Select apps to show on desktop/start menu", attr)
        
        list_y = self.y + 3
        list_x = self.x + 2
        list_w = self.w - 4
        
        # Draw list background and border
        draw_box(stdscr, list_y - 1, list_x - 1, self.visible_rows + 2, list_w + 2, attr, double=False)
        
        for i in range(self.visible_rows):
            idx = self.list_offset + i
            if idx < len(self.choices):
                label, _, checked = self.choices[idx]
                mark = '[x]' if checked else '[ ]'
                text = f" {mark} {label}"
                
                row_attr = sel_attr if (self.in_list and self.active and idx == self.list_selected) else attr
                safe_addstr(stdscr, list_y + i, list_x, text.ljust(list_w)[:list_w], row_attr)
            else:
                safe_addstr(stdscr, list_y + i, list_x, ' ' * list_w, attr)
                
        # Draw scrollbar if needed
        if len(self.choices) > self.visible_rows:
            sb_x = list_x + list_w
            thumb_pos = int(self.list_offset / max(1, len(self.choices) - self.visible_rows) * (self.visible_rows - 1))
            for i in range(self.visible_rows):
                ch = '█' if i == thumb_pos else '░'
                safe_addstr(stdscr, list_y + i, sb_x, ch, theme_attr('scrollbar'))
                
        # Draw buttons
        btn_y = self.y + self.h - 2
        btn_x_start = self.x + (self.w - sum(len(b) + 4 for b in self.buttons) - (len(self.buttons) - 1) * 2) // 2
        
        self._btn_y = btn_y
        self._btn_x_start = btn_x_start
        
        curr_x = btn_x_start
        for i, btn_text in enumerate(self.buttons):
            btn_w = len(btn_text) + 4
            btn_label = f"[ {btn_text} ]"
            btn_attr = theme_attr('button_selected') if (self.active and not self.in_list and self.selected_button == i) else theme_attr('button')
            safe_addstr(stdscr, btn_y, curr_x, btn_label, btn_attr)
            curr_x += btn_w + 2

    def handle_click(self, mx, my):
        list_y = self.y + 3
        list_x = self.x + 2
        list_w = self.w - 4
        
        # Check list clicks
        if list_x <= mx <= list_x + list_w and list_y <= my < list_y + self.visible_rows:
            click_idx = self.list_offset + (my - list_y)
            if click_idx < len(self.choices):
                self.in_list = True
                self.list_selected = click_idx
                self.choices[click_idx][2] = not self.choices[click_idx][2]
                return True
                
        # Detect clicks on buttons
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

        if key_code == 27: # Esc
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
            
        if key_code in (curses.KEY_UP, curses.KEY_DOWN):
            if not self.in_list:
                self.in_list = True
                return None
                
            if key_code == curses.KEY_UP:
                self.list_selected = max(0, self.list_selected - 1)
                if self.list_selected < self.list_offset:
                    self.list_offset = self.list_selected
            elif key_code == curses.KEY_DOWN:
                self.list_selected = min(len(self.choices) - 1, self.list_selected + 1)
                if self.list_selected >= self.list_offset + self.visible_rows:
                    self.list_offset = self.list_selected - self.visible_rows + 1
            return None
            
        if key_code in (curses.KEY_LEFT, curses.KEY_RIGHT):
            if self.in_list:
                self.in_list = False
                
            if key_code == curses.KEY_LEFT:
                self.selected_button = max(0, self.selected_button - 1)
            else:
                self.selected_button = min(len(self.buttons) - 1, self.selected_button + 1)
            return None
            
        if key_code in (9,): # Tab
            self.in_list = not self.in_list
            return None
            
        if key_code in (32, 10, 13, curses.KEY_ENTER): # Space or Enter
            if self.in_list:
                if self.choices:
                    self.choices[self.list_selected][2] = not self.choices[self.list_selected][2]
                return None
            else:
                return self._activate_button()
                
        return None
        
    def _activate_button(self):
        if self.selected_button == 0:  # Save
            selected_set = {val.lower() for _, val, checked in self.choices if checked}
            base_icons = ICONS if self.app.use_unicode else ICONS_ASCII
            hidden = [icon["label"] for icon in base_icons if icon["label"].lower() not in selected_set]
            
            self.app.config.hidden_icons = ",".join(hidden)
            try:
                self.app.persist_config()
                self.app.refresh_icons()
                # To force a start menu refresh, we rebuild the global menu items
                from ..ui.menu import DEFAULT_GLOBAL_ITEMS, Menu
                
                hidden_labels = {x.strip().lower() for x in self.app.config.hidden_icons.split(",")} if self.app.config.hidden_icons else set()
                filtered_menu_items = {}
                for category, items in DEFAULT_GLOBAL_ITEMS.items():
                    filtered_items = []
                    for item in items:
                        label = item[0].split("  ")[0]
                        if label.lower() not in hidden_labels:
                            filtered_items.append(item)
                    if filtered_items:
                        filtered_menu_items[category] = filtered_items
                        
                # Update the app's global menu with the new structure
                self.app.menu = Menu(filtered_menu_items)
                
            except OSError as exc:
                return ActionResult(ActionType.SAVE_ERROR, str(exc))
                
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
            
        elif self.selected_button == 1:  # Cancel
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
            
        return None

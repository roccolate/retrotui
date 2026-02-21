"""
Menu components.
"""
import curses
import time

from ..constants import SB_H
from ..core.actions import AppAction
from ..utils import draw_box, safe_addstr, theme_attr


DEFAULT_GLOBAL_ITEMS = {
    'File': [
        ('New Window', AppAction.NEW_WINDOW),
        ('Notepad', AppAction.NOTEPAD),
        ('File Manager', AppAction.FILE_MANAGER),
        ('ASCII Video', AppAction.ASCII_VIDEO),
        ('Terminal', AppAction.TERMINAL),
        ('-------------', None),
        ('Exit  Ctrl+Q', AppAction.EXIT),
    ],
    'Games': [
        ('Minesweeper', AppAction.MINESWEEPER),
        ('Solitaire', AppAction.SOLITAIRE),
        ('Snake', AppAction.SNAKE),
        ('Tetris', AppAction.TETRIS),
    ],
    'Apps': [
        ('Calculator', AppAction.CALCULATOR),
        ('Clock / Calendar', AppAction.CLOCK_CALENDAR),
        ('Image Viewer', AppAction.IMAGE_VIEWER),
        ('Character Map', AppAction.CHARMAP),
        ('Clipboard Viewer', AppAction.CLIPBOARD),
        ('WiFi Manager', AppAction.WIFI_MANAGER),
        ('Process Manager', AppAction.PROCESS_MANAGER),
        ('Log Viewer', AppAction.LOG_VIEWER),
        ('Markdown Viewer', AppAction.MARKDOWN_VIEWER),
        ('System Monitor', AppAction.SYSTEM_MONITOR),
        ('RetroNet Explorer', AppAction.RETRONET),
        ('Trash Bin', AppAction.TRASH_BIN),
    ],
    'Edit': [
        ('Control Panel', AppAction.CONTROL_PANEL),
        ('Preferences', AppAction.SETTINGS),
        ('App Manager', AppAction.APP_MANAGER),
    ],
    'Help': [
        ('About RetroTUI', AppAction.ABOUT),
        ('Keyboard Help', AppAction.HELP),
    ],
}


class MenuBar:
    """Unified menu bar used for both global and window menus."""

    def __init__(self, items, mode='global', show_clock=False, show_logo=False):
        self.items = items or {}
        self.menu_names = list(self.items.keys())
        self.mode = mode
        self.show_clock = show_clock
        self.show_logo = show_logo
        self.active = False
        self.selected_menu = 0
        self.selected_item = 0

    def _bar_row(self, win_y=0):
        return 0 if self.mode == 'global' else win_y + 1

    def _menu_start_x(self, win_x=0):
        return 2 if self.mode == 'global' else win_x + 2

    def get_menu_x_positions(self, win_x=0):
        """Calculate absolute x position of each menu name."""
        positions = []
        x = self._menu_start_x(win_x)
        for name in self.menu_names:
            positions.append(x)
            x += len(name) + 3
        return positions

    def _current_items(self):
        if not self.menu_names:
            return []
        menu_name = self.menu_names[self.selected_menu % len(self.menu_names)]
        return self.items.get(menu_name, [])

    @staticmethod
    def _first_selectable(items):
        for idx, (_, action) in enumerate(items):
            if action is not None:
                return idx
        return 0

    def _dropdown_layout(self, win_x=0, win_y=0, win_w=None):
        if not self.menu_names:
            return None

        items = self._current_items()
        positions = self.get_menu_x_positions(win_x)
        x = positions[self.selected_menu]
        y = self._bar_row(win_y) + 1
        max_item_len = max((len(label) for label, _ in items), default=0)
        dropdown_w = max_item_len + 4

        if self.mode == 'window' and win_w is not None:
            right_edge = win_x + win_w
            if x - 1 + dropdown_w + 2 > right_edge:
                x = max(win_x + 2, right_edge - dropdown_w - 2)

        return x, y, dropdown_w, items

    def _move_selected_item(self, delta):
        items = self._current_items()
        if not items:
            return
        for _ in range(len(items)):
            self.selected_item = (self.selected_item + delta) % len(items)
            if items[self.selected_item][1] is not None:
                return

    def draw_bar(self, stdscr, *, width=None, win_x=0, win_y=0, win_w=None, is_active=True):
        """Draw the bar row for either global or window mode."""
        bar_y = self._bar_row(win_y)
        bar_attr = theme_attr("menubar")

        if self.mode == 'global':
            if width is None:
                _, width = stdscr.getmaxyx()
            safe_addstr(stdscr, bar_y, 0, ' ' * width, bar_attr)
            if self.show_logo:
                safe_addstr(stdscr, bar_y, 0, ' =', bar_attr | curses.A_BOLD)
        else:
            if win_w is None:
                return
            safe_addstr(stdscr, bar_y, win_x + 1, ' ' * max(0, win_w - 2), bar_attr)

        positions = self.get_menu_x_positions(win_x)
        for i, name in enumerate(self.menu_names):
            attr = bar_attr
            if self.active and i == self.selected_menu and is_active:
                attr = theme_attr("menu_selected")
            safe_addstr(stdscr, bar_y, positions[i], f' {name} ', attr)

        if self.mode == 'global' and self.show_clock and width:
            clock = time.strftime(' %H:%M:%S ')
            safe_addstr(stdscr, bar_y, width - len(clock) - 1, clock, bar_attr)

    def draw_dropdown(self, stdscr, *, win_x=0, win_y=0, win_w=None):
        """Draw dropdown for currently selected menu."""
        if not self.active:
            return

        layout = self._dropdown_layout(win_x=win_x, win_y=win_y, win_w=win_w)
        if layout is None:
            return
        x, y, dropdown_w, items = layout
        item_attr = theme_attr("menu_item")
        draw_box(stdscr, y, x - 1, len(items) + 2, dropdown_w + 2, item_attr, double=False)

        for i, (label, action) in enumerate(items):
            attr = theme_attr("menu_selected") if i == self.selected_item else item_attr
            if action is None:
                safe_addstr(stdscr, y + 1 + i, x, SB_H * dropdown_w, item_attr)
            else:
                safe_addstr(stdscr, y + 1 + i, x, f' {label.ljust(dropdown_w - 2)} ', attr)

    def get_dropdown_rect(self, *, win_x=0, win_y=0, win_w=None):
        """Return (x, y, w, h) of active dropdown area, or None."""
        if not self.active:
            return None
        layout = self._dropdown_layout(win_x=win_x, win_y=win_y, win_w=win_w)
        if layout is None:
            return None
        x, y, dropdown_w, items = layout
        return x - 1, y, dropdown_w + 2, len(items) + 2

    def hit_test_dropdown(self, mx, my, *, win_x=0, win_y=0, win_w=None):
        """Check if mouse point is inside dropdown area."""
        rect = self.get_dropdown_rect(win_x=win_x, win_y=win_y, win_w=win_w)
        if rect is None:
            return False
        rx, ry, rw, rh = rect
        return rx <= mx < rx + rw and ry <= my < ry + rh

    def on_menu_bar(self, mx, my, *, win_x=0, win_y=0, win_w=None):
        """Check if a point is on this menu bar row."""
        if my != self._bar_row(win_y):
            return False
        if self.mode == 'window' and win_w is not None:
            return win_x + 1 <= mx < win_x + win_w - 1
        return True

    def handle_hover(self, mx, my, *, win_x=0, win_y=0, win_w=None):
        """Handle hover and keep menu active while pointer remains in menu area."""
        if not self.active:
            return False

        bar_y = self._bar_row(win_y)
        if my == bar_y:
            positions = self.get_menu_x_positions(win_x)
            for i, pos in enumerate(positions):
                name = self.menu_names[i]
                if pos <= mx < pos + len(name) + 2:
                    if i != self.selected_menu:
                        self.selected_menu = i
                        self.selected_item = self._first_selectable(self._current_items())
                    return True
            return self.on_menu_bar(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)

        if self.hit_test_dropdown(mx, my, win_x=win_x, win_y=win_y, win_w=win_w):
            items = self._current_items()
            idx = my - (bar_y + 2)
            if 0 <= idx < len(items) and items[idx][1] is not None:
                self.selected_item = idx
            return True

        return False

    def handle_click(self, mx, my, *, win_x=0, win_y=0, win_w=None):
        """Handle click on menu bar/dropdown and return action string or None."""
        bar_y = self._bar_row(win_y)

        if my == bar_y and self.on_menu_bar(mx, my, win_x=win_x, win_y=win_y, win_w=win_w):
            positions = self.get_menu_x_positions(win_x)
            for i, pos in enumerate(positions):
                name = self.menu_names[i]
                if pos <= mx < pos + len(name) + 2:
                    if self.active and self.selected_menu == i:
                        self.active = False
                    else:
                        self.active = True
                        self.selected_menu = i
                        self.selected_item = self._first_selectable(self._current_items())
                    return None
            self.active = False
            return None

        if self.active:
            layout = self._dropdown_layout(win_x=win_x, win_y=win_y, win_w=win_w)
            if layout is None:
                self.active = False
                return None
            x, _, dropdown_w, items = layout

            if x - 1 <= mx < x + dropdown_w + 1 and bar_y + 2 <= my < bar_y + 2 + len(items):
                idx = my - (bar_y + 2)
                if 0 <= idx < len(items) and items[idx][1] is not None:
                    action = items[idx][1]
                    self.active = False
                    return action
            else:
                self.active = False

        return None

    def handle_key(self, key):
        """Handle keyboard navigation and return selected action or None."""
        if not self.active or not self.menu_names:
            return None

        if key == curses.KEY_LEFT:
            self.selected_menu = (self.selected_menu - 1) % len(self.menu_names)
            self.selected_item = self._first_selectable(self._current_items())
            return None

        if key == curses.KEY_RIGHT:
            self.selected_menu = (self.selected_menu + 1) % len(self.menu_names)
            self.selected_item = self._first_selectable(self._current_items())
            return None

        if key == curses.KEY_UP:
            self._move_selected_item(-1)
            return None

        if key == curses.KEY_DOWN:
            self._move_selected_item(1)
            return None

        if key in (curses.KEY_ENTER, 10, 13):
            items = self._current_items()
            if not items:
                return None
            action = items[self.selected_item][1]
            if action:
                self.active = False
                return action
            return None

        if key == 27:  # Escape
            self.active = False
            return None

        return None


class Menu(MenuBar):
    """Backwards-compatible global menu wrapper."""

    def __init__(self, items=None):
        items = items if items is not None else DEFAULT_GLOBAL_ITEMS
        super().__init__(items, mode='global', show_clock=True, show_logo=True)

    def draw_bar(self, stdscr, width):
        super().draw_bar(stdscr, width=width)

    def draw_dropdown(self, stdscr):
        super().draw_dropdown(stdscr)

    def get_dropdown_rect(self, *, win_x=0, win_y=0, win_w=None):
        return super().get_dropdown_rect(win_x=win_x, win_y=win_y, win_w=win_w)

    def hit_test_dropdown(self, mx, my, *, win_x=0, win_y=0, win_w=None):
        return super().hit_test_dropdown(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)

    def handle_hover(self, mx, my, *, win_x=0, win_y=0, win_w=None):
        return super().handle_hover(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)

    def handle_click(self, mx, my, *, win_x=0, win_y=0, win_w=None):
        return super().handle_click(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)


class WindowMenu(MenuBar):
    """Backwards-compatible per-window menu wrapper."""

    def __init__(self, items):
        super().__init__(items, mode='window', show_clock=False, show_logo=False)

    def menu_bar_row(self, win_y):
        return self._bar_row(win_y)

    def get_menu_x_positions(self, win_x):
        return super().get_menu_x_positions(win_x=win_x)

    def draw_bar(self, stdscr, win_x, win_y, win_w, is_active):
        super().draw_bar(
            stdscr,
            win_x=win_x,
            win_y=win_y,
            win_w=win_w,
            is_active=is_active,
        )

    def draw_dropdown(self, stdscr, win_x, win_y, win_w):
        super().draw_dropdown(stdscr, win_x=win_x, win_y=win_y, win_w=win_w)

    def on_menu_bar(self, mx, my, win_x, win_y, win_w):
        return super().on_menu_bar(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)

    def handle_click(self, mx, my, win_x, win_y, win_w):
        return super().handle_click(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)

    def handle_hover(self, mx, my, win_x, win_y, win_w):
        return super().handle_hover(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)

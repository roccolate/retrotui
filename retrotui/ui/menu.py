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
    'Apps': [
        ('Calculator', AppAction.CALCULATOR),
        ('Clipboard Viewer', AppAction.CLIPBOARD),
        ('Process Manager', AppAction.PROCESS_MANAGER),
        ('Log Viewer', AppAction.LOG_VIEWER),
        ('Markdown Viewer', AppAction.MARKDOWN_VIEWER),
        ('System Monitor', AppAction.SYSTEM_MONITOR),
        ('Trash Bin', AppAction.TRASH_BIN),
    ],
    'Edit': [
        ('Control Panel', AppAction.CONTROL_PANEL),
        ('Preferences', AppAction.SETTINGS),
        ('Desktop Icons', AppAction.DESKTOP_ICON_MANAGER),
        ('Icons', AppAction.ICONS),
        ('Menu Editor', AppAction.MENU_EDITOR),
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
        self.dropdown_scroll = 0
        self._viewport_w = None
        self._viewport_h = None
        self._last_layout_args = (0, 0, None)
        self._last_clock_render = None

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

    def _set_viewport(self, width=None, height=None):
        """Cache last known viewport dimensions used to clamp dropdowns."""
        if isinstance(width, int) and width > 0:
            self._viewport_w = width
        if isinstance(height, int) and height > 0:
            self._viewport_h = height

    @staticmethod
    def _read_stdscr_size(stdscr):
        """Return ``(h, w)`` from curses screen-like object when available."""
        getmaxyx = getattr(stdscr, "getmaxyx", None)
        if not callable(getmaxyx):
            return None
        try:
            return getmaxyx()
        except (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError):
            return None

    @staticmethod
    def _first_selectable(items):
        for idx, (_, action) in enumerate(items):
            if action is not None:
                return idx
        return 0

    def _dropdown_layout(self, win_x=0, win_y=0, win_w=None):
        if not self.menu_names:
            return None

        # Keep keyboard/mouse layout stable between draw and event handlers.
        if win_x == 0 and win_y == 0 and win_w is None:
            win_x, win_y, win_w = self._last_layout_args

        full_items = self._current_items()
        positions = self.get_menu_x_positions(win_x)
        x = positions[self.selected_menu]
        y = self._bar_row(win_y) + 1
        max_item_len = max((len(label) for label, _ in full_items), default=0)
        dropdown_w = max_item_len + 4

        if full_items:
            self.selected_item = max(0, min(self.selected_item, len(full_items) - 1))
        else:
            self.selected_item = 0
            self.dropdown_scroll = 0

        viewport_w = self._viewport_w
        viewport_h = self._viewport_h

        if self.mode == 'global' and viewport_w is not None:
            dropdown_w = min(dropdown_w, max(4, viewport_w - 2))

        if self.mode == 'window' and win_w is not None:
            right_edge = win_x + win_w
            if x - 1 + dropdown_w + 2 > right_edge:
                x = max(win_x + 2, right_edge - dropdown_w - 2)
        elif self.mode == 'global' and viewport_w is not None:
            max_x = max(1, viewport_w - dropdown_w - 1)
            x = max(1, min(x, max_x))

        visible_rows = len(full_items)
        if viewport_h is not None:
            visible_rows = min(visible_rows, max(1, viewport_h - y - 2))

        max_scroll = max(0, len(full_items) - visible_rows)
        self.dropdown_scroll = max(0, min(self.dropdown_scroll, max_scroll))
        if self.selected_item < self.dropdown_scroll:
            self.dropdown_scroll = self.selected_item
        elif self.selected_item >= self.dropdown_scroll + max(1, visible_rows):
            self.dropdown_scroll = self.selected_item - visible_rows + 1
        self.dropdown_scroll = max(0, min(self.dropdown_scroll, max_scroll))

        visible_items = full_items[self.dropdown_scroll : self.dropdown_scroll + visible_rows]
        return x, y, dropdown_w, visible_items

    def _move_selected_item(self, delta):
        items = self._current_items()
        if not items:
            return
        for _ in range(len(items)):
            self.selected_item = (self.selected_item + delta) % len(items)
            if items[self.selected_item][1] is not None:
                self._dropdown_layout()
                return

    def _clock_layout(self, width, win_x=0):
        """Return ``(x, text)`` for the global clock when there is free space."""
        if self.mode != 'global' or not self.show_clock or not width:
            return None
        clock = time.strftime(' %H:%M:%S ')
        clock_x = width - len(clock) - 1
        if clock_x < 0:
            return None

        menu_right = 0
        if self.menu_names:
            positions = self.get_menu_x_positions(win_x)
            last_idx = len(self.menu_names) - 1
            menu_right = positions[last_idx] + len(self.menu_names[last_idx]) + 2
        if clock_x <= menu_right + 1:
            return None
        return clock_x, clock

    def refresh_clock(self, stdscr, *, width=None, win_x=0, force=False, frame_size=None):
        """Refresh only the global clock segment when it changed."""
        if self.mode != 'global' or not self.show_clock:
            return False

        if frame_size is not None:
            viewport_h, width = frame_size
            size = None
        else:
            size = self._read_stdscr_size(stdscr)
            if width is None:
                if size is not None:
                    viewport_h, width = size
                else:
                    viewport_h = self._viewport_h
                    width = self._viewport_w
            else:
                viewport_h = size[0] if size is not None else self._viewport_h
        self._set_viewport(width=width, height=viewport_h)

        layout = self._clock_layout(width, win_x=win_x)
        if layout is None:
            self._last_clock_render = None
            return False

        clock_x, clock = layout
        render_key = (clock_x, clock)
        if not force and render_key == self._last_clock_render:
            return False

        safe_addstr(
            stdscr,
            self._bar_row(),
            clock_x,
            clock,
            theme_attr("menubar"),
            _bounds=frame_size,
        )
        self._last_clock_render = render_key
        return True

    def draw_bar(
        self,
        stdscr,
        *,
        width=None,
        win_x=0,
        win_y=0,
        win_w=None,
        is_active=True,
        frame_size=None,
    ):
        """Draw the bar row for either global or window mode."""
        bar_y = self._bar_row(win_y)
        bar_attr = theme_attr("menubar")
        self._last_layout_args = (win_x, win_y, win_w)
        size = frame_size if frame_size is not None else self._read_stdscr_size(stdscr)

        if self.mode == 'global':
            if width is None:
                if size is not None:
                    viewport_h, width = size
                else:
                    viewport_h = self._viewport_h
                    width = self._viewport_w if self._viewport_w is not None else 80
            else:
                viewport_h = size[0] if size is not None else self._viewport_h
            self._set_viewport(width=width, height=viewport_h)
            safe_addstr(stdscr, bar_y, 0, ' ' * width, bar_attr, _bounds=frame_size)
            if self.show_logo:
                safe_addstr(
                    stdscr,
                    bar_y,
                    0,
                    ' =',
                    bar_attr | curses.A_BOLD,
                    _bounds=frame_size,
                )
        else:
            if win_w is None:
                return
            if size is not None:
                viewport_h, viewport_w = size
                self._set_viewport(width=viewport_w, height=viewport_h)
            safe_addstr(
                stdscr,
                bar_y,
                win_x + 1,
                ' ' * max(0, win_w - 2),
                bar_attr,
                _bounds=frame_size,
            )

        positions = self.get_menu_x_positions(win_x)
        for i, name in enumerate(self.menu_names):
            attr = bar_attr
            if self.active and i == self.selected_menu and is_active:
                attr = theme_attr("menu_selected")
            safe_addstr(
                stdscr,
                bar_y,
                positions[i],
                f' {name} ',
                attr,
                _bounds=frame_size,
            )

        if self.mode == 'global':
            self.refresh_clock(
                stdscr, width=width, win_x=win_x, force=True, frame_size=frame_size,
            )

    def draw_dropdown(self, stdscr, *, win_x=0, win_y=0, win_w=None, frame_size=None):
        """Draw dropdown for currently selected menu."""
        if not self.active:
            return

        size = frame_size if frame_size is not None else self._read_stdscr_size(stdscr)
        if size is not None:
            viewport_h, viewport_w = size
            self._set_viewport(width=viewport_w, height=viewport_h)
        layout = self._dropdown_layout(win_x=win_x, win_y=win_y, win_w=win_w)
        if layout is None:
            return
        x, y, dropdown_w, items = layout
        item_attr = theme_attr("menu_item")
        draw_box(stdscr, y, x - 1, len(items) + 2, dropdown_w + 2, item_attr, double=False)

        for i, (label, action) in enumerate(items):
            abs_idx = self.dropdown_scroll + i
            attr = theme_attr("menu_selected") if abs_idx == self.selected_item else item_attr
            if action is None:
                safe_addstr(
                    stdscr,
                    y + 1 + i,
                    x,
                    SB_H * dropdown_w,
                    item_attr,
                    _bounds=frame_size,
                )
            else:
                safe_addstr(
                    stdscr,
                    y + 1 + i,
                    x,
                    f' {label.ljust(dropdown_w - 2)} ',
                    attr,
                    _bounds=frame_size,
                )

        # Draw compact scroll markers when the dropdown is paginated.
        full_items = self._current_items()
        if len(items) < len(full_items):
            if self.dropdown_scroll > 0 and items:
                safe_addstr(
                    stdscr,
                    y + 1,
                    x + dropdown_w - 2,
                    '^',
                    item_attr | curses.A_BOLD,
                    _bounds=frame_size,
                )
            if (self.dropdown_scroll + len(items)) < len(full_items) and items:
                safe_addstr(
                    stdscr,
                    y + len(items),
                    x + dropdown_w - 2,
                    'v',
                    item_attr | curses.A_BOLD,
                    _bounds=frame_size,
                )

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
                        self.dropdown_scroll = 0
                    return True
            return self.on_menu_bar(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)

        if self.hit_test_dropdown(mx, my, win_x=win_x, win_y=win_y, win_w=win_w):
            layout = self._dropdown_layout(win_x=win_x, win_y=win_y, win_w=win_w)
            if layout is None:
                return False
            _, _, _, visible_items = layout
            full_items = self._current_items()
            idx = self.dropdown_scroll + (my - (bar_y + 2))
            if 0 <= idx < len(full_items) and (idx - self.dropdown_scroll) < len(visible_items) and full_items[idx][1] is not None:
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
                        self.dropdown_scroll = 0
                    else:
                        self.active = True
                        self.selected_menu = i
                        self.selected_item = self._first_selectable(self._current_items())
                        self.dropdown_scroll = 0
                    return None
            self.active = False
            self.dropdown_scroll = 0
            return None

        if self.active:
            layout = self._dropdown_layout(win_x=win_x, win_y=win_y, win_w=win_w)
            if layout is None:
                self.active = False
                self.dropdown_scroll = 0
                return None
            x, _, dropdown_w, visible_items = layout
            full_items = self._current_items()

            if x - 1 <= mx < x + dropdown_w + 1 and bar_y + 2 <= my < bar_y + 2 + len(visible_items):
                idx = self.dropdown_scroll + (my - (bar_y + 2))
                if 0 <= idx < len(full_items) and full_items[idx][1] is not None:
                    action = full_items[idx][1]
                    self.active = False
                    self.dropdown_scroll = 0
                    return action
            else:
                self.active = False
                self.dropdown_scroll = 0

        return None

    def handle_key(self, key):
        """Handle keyboard navigation and return selected action or None."""
        if not self.active or not self.menu_names:
            return None

        if key == curses.KEY_LEFT:
            self.selected_menu = (self.selected_menu - 1) % len(self.menu_names)
            self.selected_item = self._first_selectable(self._current_items())
            self.dropdown_scroll = 0
            return None

        if key == curses.KEY_RIGHT:
            self.selected_menu = (self.selected_menu + 1) % len(self.menu_names)
            self.selected_item = self._first_selectable(self._current_items())
            self.dropdown_scroll = 0
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
                self.dropdown_scroll = 0
                return action
            return None

        if key == 27:  # Escape
            self.active = False
            self.dropdown_scroll = 0
            return None

        return None


class Menu(MenuBar):
    """Backwards-compatible global menu wrapper."""

    def __init__(self, items=None):
        items = items if items is not None else DEFAULT_GLOBAL_ITEMS
        super().__init__(items, mode='global', show_clock=True, show_logo=True)

    def draw_bar(self, stdscr, width, *, frame_size=None):
        super().draw_bar(stdscr, width=width, frame_size=frame_size)

    def draw_dropdown(self, stdscr, *, frame_size=None):
        super().draw_dropdown(stdscr, frame_size=frame_size)

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

    def draw_bar(self, stdscr, win_x, win_y, win_w, is_active, *, frame_size=None):
        super().draw_bar(
            stdscr,
            win_x=win_x,
            win_y=win_y,
            win_w=win_w,
            is_active=is_active,
            frame_size=frame_size,
        )

    def draw_dropdown(self, stdscr, win_x, win_y, win_w, *, frame_size=None):
        super().draw_dropdown(
            stdscr, win_x=win_x, win_y=win_y, win_w=win_w, frame_size=frame_size,
        )

    def on_menu_bar(self, mx, my, win_x, win_y, win_w):
        return super().on_menu_bar(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)

    def handle_click(self, mx, my, win_x, win_y, win_w):
        return super().handle_click(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)

    def handle_hover(self, mx, my, win_x, win_y, win_w):
        return super().handle_hover(mx, my, win_x=win_x, win_y=win_y, win_w=win_w)

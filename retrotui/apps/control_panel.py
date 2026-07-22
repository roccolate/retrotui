"""Unified Control Panel for RetroTUI."""
import curses
from retrotui import __version__ as APP_VERSION
from ..core.actions import AppAction, ActionResult, ActionType
from ..theme import list_themes
from ..ui.window import Window
from ..utils import safe_addstr, theme_attr, normalize_key_code
from .settings import SettingsWindow

class ControlPanelWindow(Window):
    """Visual center for all system settings."""

    CATEGORIES = [
        ("Appearance", "Theme & Palette"),
        ("Desktop", "Icons & Layout"),
        ("Regional", "Clock & Calendar"),
        ("System", "Version & Welcome"),
    ]
    _TOGGLE_TWO = [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ]

    def __init__(self, x, y, w, h, app):
        super().__init__('Control Panel', x, y, 60, 18, resizable=False)
        self.app = app
        self.selected_cat = 0

        # We reuse some state from SettingsWindow eventually, but start fresh for UI logic
        self.theme_name = app.theme_name
        self.show_hidden = bool(app.default_show_hidden)
        self.word_wrap_default = bool(app.default_word_wrap)
        self.sunday_first = bool(app.config.sunday_first)
        self.show_welcome = bool(getattr(app, "show_welcome", app.config.show_welcome))

        # For Theme selection
        self._themes = list_themes()

    def draw(self, stdscr):
        if not self.visible:
            return

        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        
        # Draw background split
        # Left pane: Categories (w=18)
        # Right pane: Options
        pane_divider_x = bx + 18
        
        for i in range(bh):
            safe_addstr(stdscr, by + i, bx, ' ' * 18, theme_attr('window_inactive'))
            safe_addstr(stdscr, by + i, pane_divider_x, ' ' * (bw - 18), body_attr)
            safe_addstr(stdscr, by + i, pane_divider_x, '│', theme_attr('window_border'))

        # Draw Categories
        for i, (title, desc) in enumerate(self.CATEGORIES):
            y = by + 1 + i * 3
            attr = theme_attr('button_selected') if self.selected_cat == i else theme_attr('window_inactive')
            safe_addstr(stdscr, y, bx + 1, f" {title.ljust(15)} ", attr)
            safe_addstr(stdscr, y + 1, bx + 2, desc[:14], theme_attr('status') if self.selected_cat != i else attr)

        # Draw Right Content based on selection
        rx = pane_divider_x + 2
        rw = bw - 22
        ry = by + 1
        
        if self.selected_cat == 0: # Appearance
            safe_addstr(stdscr, ry, rx, "Select Color Theme:", body_attr | curses.A_BOLD)
            for i, theme in enumerate(self._themes):
                ty = ry + 2 + i
                checked = "●" if theme.key == self.theme_name else "○"
                line = f"{checked} {theme.label}"
                safe_addstr(stdscr, ty, rx, line.ljust(rw), body_attr)
        
        elif self.selected_cat == 1: # Desktop
            safe_addstr(stdscr, ry, rx, "Desktop Options:", body_attr | curses.A_BOLD)
            h_mark = "[x]" if self.show_hidden else "[ ]"
            w_mark = "[x]" if self.word_wrap_default else "[ ]"
            safe_addstr(stdscr, ry + 2, rx, f"{h_mark} Show hidden files", body_attr)
            safe_addstr(stdscr, ry + 4, rx, f"{w_mark} Word wrap in Notepad", body_attr)

        elif self.selected_cat == 2: # Regional
            safe_addstr(stdscr, ry, rx, "Regional Settings:", body_attr | curses.A_BOLD)
            s_mark = "[x]" if self.sunday_first else "[ ]"
            safe_addstr(stdscr, ry + 2, rx, f"{s_mark} Calendar: Sunday first", body_attr)

        elif self.selected_cat == 3: # System
            safe_addstr(stdscr, ry, rx, "System Configuration:", body_attr | curses.A_BOLD)
            w_mark = "[x]" if self.show_welcome else "[ ]"
            safe_addstr(stdscr, ry + 2, rx, f"{w_mark} Show Welcome Screen", body_attr)
            safe_addstr(stdscr, ry + 6, rx, f"RetroTUI Version: {APP_VERSION}", theme_attr('status'))

        # Buttons at bottom right
        btn_y = by + bh - 2
        safe_addstr(stdscr, btn_y, bx + bw - 18, " [ Apply ] ", theme_attr('button'))
        safe_addstr(stdscr, btn_y, bx + bw - 8, " [ OK ] ", theme_attr('button_selected'))

    def _cycle_theme(self, delta):
        """Move to the previous/next theme and apply it."""
        if not self._themes:
            return
        idx = next(
            (i for i, t in enumerate(self._themes) if t.key == self.theme_name),
            0,
        )
        self.theme_name = self._themes[(idx + delta) % len(self._themes)].key
        self.app.apply_theme(self.theme_name)
        self.app.persist_config()

    @staticmethod
    def _checkbox_hit(mx, my, *, x, y, label):
        """Return whether a click falls on the rendered checkbox row."""
        return my == y and x <= mx < x + len(label)

    def _toggle_show_hidden(self):
        self.show_hidden = not self.show_hidden
        self.app.apply_preferences(show_hidden=self.show_hidden)
        self.app.persist_config()
        return ActionResult(ActionType.REFRESH)

    def _toggle_word_wrap_default(self):
        self.word_wrap_default = not self.word_wrap_default
        self.app.apply_preferences(word_wrap_default=self.word_wrap_default)
        self.app.persist_config()
        return ActionResult(ActionType.REFRESH)

    def _toggle_sunday_first(self):
        self.sunday_first = not self.sunday_first
        self.app.apply_preferences(
            sunday_first=self.sunday_first,
            apply_to_open_windows=True,
        )
        self.app.persist_config()
        return ActionResult(ActionType.REFRESH)

    def _toggle_welcome(self):
        self.show_welcome = not self.show_welcome
        self.app.apply_preferences(
            show_welcome=self.show_welcome,
            apply_to_open_windows=True,
        )
        self.app.persist_config()
        return ActionResult(ActionType.REFRESH)

    def handle_key(self, key):
        code = normalize_key_code(key)
        if self.selected_cat == 0 and code in (curses.KEY_LEFT, curses.KEY_RIGHT):
            # On Appearance, Left/Right selects a specific theme so the
            # user no longer has to cycle with Space.
            self._cycle_theme(-1 if code == curses.KEY_LEFT else 1)
            return None
        if code == curses.KEY_UP:
            self.selected_cat = (self.selected_cat - 1) % len(self.CATEGORIES)
        elif code == curses.KEY_DOWN:
            self.selected_cat = (self.selected_cat + 1) % len(self.CATEGORIES)
        elif code in (ord(' '), 10, 13):
            # Toggle logic or save logic based on selection
            if self.selected_cat == 0:
                self._cycle_theme(1)
            elif self.selected_cat == 1:
                # Cycle hidden / word-wrap defaults so both are reachable.
                idx = next(
                    (i for i, t in enumerate(self._TOGGLE_TWO) if t == (self.show_hidden, self.word_wrap_default)),
                    0,
                )
                self.show_hidden, self.word_wrap_default = self._TOGGLE_TWO[(idx + 1) % len(self._TOGGLE_TWO)]
                self.app.apply_preferences(
                    show_hidden=self.show_hidden,
                    word_wrap_default=self.word_wrap_default,
                )
            elif self.selected_cat == 2:
                self.sunday_first = not self.sunday_first
                self.app.apply_preferences(
                    sunday_first=self.sunday_first,
                    apply_to_open_windows=True,
                )
            elif self.selected_cat == 3:
                return self._toggle_welcome()

            # Auto-save when changing
            self.app.persist_config()

        return super().handle_key(key)

    def handle_click(self, mx, my):
        bx, by, bw, bh = self.body_rect()
        pane_divider_x = bx + 18
        rx = pane_divider_x + 2
        ry = by + 1

        # Click on category
        if bx <= mx < pane_divider_x:
            for i in range(len(self.CATEGORIES)):
                y = by + 1 + i * 3
                if y <= my < y + 3:
                    self.selected_cat = i
                    return None

        # Click on a theme row in the Appearance pane
        if self.selected_cat == 0 and pane_divider_x <= mx:
            row = (my - by - 3)  # themes start at by + 2 (+1 for the header)
            if 0 <= row < len(self._themes) and my >= by + 2:
                self.theme_name = self._themes[row].key
                self.app.apply_theme(self.theme_name)
                self.app.persist_config()
                return None

        if self.selected_cat == 1:
            hidden_label = "[ ] Show hidden files"
            wrap_label = "[ ] Word wrap in Notepad"
            if self._checkbox_hit(mx, my, x=rx, y=ry + 2, label=hidden_label):
                return self._toggle_show_hidden()
            if self._checkbox_hit(mx, my, x=rx, y=ry + 4, label=wrap_label):
                return self._toggle_word_wrap_default()

        if self.selected_cat == 2:
            sunday_label = "[ ] Calendar: Sunday first"
            if self._checkbox_hit(mx, my, x=rx, y=ry + 2, label=sunday_label):
                return self._toggle_sunday_first()

        if self.selected_cat == 3:
            welcome_label = "[ ] Show Welcome Screen"
            if self._checkbox_hit(mx, my, x=rx, y=ry + 2, label=welcome_label):
                return self._toggle_welcome()

        # Check buttons
        btn_y = by + bh - 2
        if my == btn_y:
            if bx + bw - 18 <= mx < bx + bw - 8: # Apply
                self.app.persist_config()
                return ActionResult(ActionType.REFRESH)
            if bx + bw - 8 <= mx < bx + bw: # OK
                self.app.persist_config()
                return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)

        return super().handle_click(mx, my)

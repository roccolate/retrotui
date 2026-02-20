"""Functional settings window with live theme preview."""

import curses

from ..core.actions import ActionResult, ActionType, AppAction
from ..theme import list_themes
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr


class SettingsWindow(Window):
    """Interactive settings window for theme and editor/file defaults."""

    def __init__(self, x, y, w, h, app):
        super().__init__('Settings', x, y, w, h, content=[], resizable=False)
        self.app = app
        self._themes = list_themes()
        self.theme_name = app.theme_name
        self.show_hidden = bool(app.default_show_hidden)
        self.word_wrap_default = bool(app.default_word_wrap)
        self.sunday_first = bool(app.config.sunday_first)
        self.show_welcome = bool(app.config.show_welcome)
        self.hidden_icons = str(app.config.hidden_icons)
        self._initial_state = (
            app.theme_name,
            app.default_show_hidden,
            app.default_word_wrap,
            app.config.sunday_first,
            app.config.show_welcome,
            app.config.hidden_icons,
        )
        self._selection = 0
        self._committed = False
        self._control_rows = {}
        self._button_bounds = {}
        self.h = max(self.h, 17)
        self.w = max(self.w, 54)

    def _theme_count(self):
        return len(self._themes)

    def _controls_count(self):
        return self._theme_count() + 7  # theme rows + 4 toggles + 1 button + save + cancel

    def _toggle_show_hidden_index(self):
        return self._theme_count()

    def _toggle_wrap_index(self):
        return self._theme_count() + 1

    def _toggle_sunday_first_index(self):
        return self._theme_count() + 2
        
    def _toggle_show_welcome_index(self):
        return self._theme_count() + 3

    def _edit_hidden_icons_index(self):
        return self._theme_count() + 4

    def _save_index(self):
        return self._theme_count() + 5

    def _cancel_index(self):
        return self._theme_count() + 6

    def _apply_runtime(self):
        self.app.apply_theme(self.theme_name)
        self.app.apply_preferences(
            show_hidden=self.show_hidden,
            word_wrap_default=self.word_wrap_default,
            sunday_first=self.sunday_first,
            apply_to_open_windows=True,
        )
        self.app.show_welcome = self.show_welcome
        self.app.config.hidden_icons = self.hidden_icons
        self.app.refresh_icons()

    def _revert_runtime(self):
        initial_theme, initial_hidden, initial_wrap, initial_sunday, initial_welcome, initial_icons = self._initial_state
        self.theme_name = initial_theme
        self.show_hidden = bool(initial_hidden)
        self.word_wrap_default = bool(initial_wrap)
        self.sunday_first = bool(initial_sunday)
        self.show_welcome = bool(initial_welcome)
        self.hidden_icons = str(initial_icons)
        self._apply_runtime()

    def _activate_selection(self):
        idx = self._selection
        if idx < self._theme_count():
            self.theme_name = self._themes[idx].key
            self.app.apply_theme(self.theme_name)  # live preview
            return None
        if idx == self._toggle_show_hidden_index():
            self.show_hidden = not self.show_hidden
            self.app.apply_preferences(show_hidden=self.show_hidden, apply_to_open_windows=True)
            return None
        if idx == self._toggle_wrap_index():
            self.word_wrap_default = not self.word_wrap_default
            self.app.apply_preferences(word_wrap_default=self.word_wrap_default, apply_to_open_windows=True)
            return None
        if idx == self._toggle_sunday_first_index():
            self.sunday_first = not self.sunday_first
            self.app.apply_preferences(sunday_first=self.sunday_first, apply_to_open_windows=True)
            return None
        if idx == self._toggle_show_welcome_index():
            self.show_welcome = not self.show_welcome
            return None
        if idx == self._edit_hidden_icons_index():
            from ..ui.dialog import InputDialog
            
            def on_submit(value):
                self.hidden_icons = value.strip()
                
            dialog = InputDialog(
                "Hidden Desktop Icons",
                "Comma-separated list (e.g. Hex,Logs,Clock):",
                self.hidden_icons,
            )
            dialog.callback = on_submit
            self.app.dialog = dialog
            return None
        if idx == self._save_index():
            self._committed = True
            self._apply_runtime()
            try:
                self.app.persist_config()
            except OSError as exc:
                self._committed = False
                return ActionResult(ActionType.SAVE_ERROR, str(exc))
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        if idx == self._cancel_index():
            self._committed = True
            self._revert_runtime()
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

    def draw(self, stdscr):
        if not self.visible:
            return

        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, ' ' * bw, body_attr)

        self._control_rows = {}
        self._button_bounds = {}
        row = by

        safe_addstr(stdscr, row, bx + 1, 'Theme (preview live)', theme_attr('window_title') | curses.A_BOLD)
        row += 1
        for i, theme in enumerate(self._themes):
            checked = '(x)' if theme.key == self.theme_name else '( )'
            line = f' {checked} {theme.label}'
            attr = body_attr | curses.A_REVERSE if self._selection == i else body_attr
            safe_addstr(stdscr, row, bx, line.ljust(bw)[:bw], attr)
            self._control_rows[i] = row
            row += 1

        row += 1
        hidden_idx = self._toggle_show_hidden_index()
        hidden_mark = '[x]' if self.show_hidden else '[ ]'
        hidden_attr = body_attr | curses.A_REVERSE if self._selection == hidden_idx else body_attr
        safe_addstr(stdscr, row, bx, f' {hidden_mark} Show hidden files by default'.ljust(bw)[:bw], hidden_attr)
        self._control_rows[hidden_idx] = row
        row += 1

        wrap_idx = self._toggle_wrap_index()
        wrap_mark = '[x]' if self.word_wrap_default else '[ ]'
        wrap_attr = body_attr | curses.A_REVERSE if self._selection == wrap_idx else body_attr
        safe_addstr(stdscr, row, bx, f' {wrap_mark} Word wrap enabled by default'.ljust(bw)[:bw], wrap_attr)
        self._control_rows[wrap_idx] = row
        row += 1

        sunday_idx = self._toggle_sunday_first_index()
        sunday_mark = '[x]' if self.sunday_first else '[ ]'
        sunday_attr = body_attr | curses.A_REVERSE if self._selection == sunday_idx else body_attr
        safe_addstr(stdscr, row, bx, f' {sunday_mark} Calendar: Week starts on Sunday'.ljust(bw)[:bw], sunday_attr)
        self._control_rows[sunday_idx] = row
        row += 1

        welcome_idx = self._toggle_show_welcome_index()
        welcome_mark = '[x]' if self.show_welcome else '[ ]'
        welcome_attr = body_attr | curses.A_REVERSE if self._selection == welcome_idx else body_attr
        safe_addstr(stdscr, row, bx, f' {welcome_mark} Show welcome screen on startup'.ljust(bw)[:bw], welcome_attr)
        self._control_rows[welcome_idx] = row
        row += 1
        
        icons_idx = self._edit_hidden_icons_index()
        icons_label = '[ Edit Hidden Desktop Icons... ]'
        icons_attr = theme_attr('button_selected') if self._selection == icons_idx else theme_attr('button')
        safe_addstr(stdscr, row, bx + 1, icons_label, icons_attr)
        self._control_rows[icons_idx] = row
        self._button_bounds[icons_idx] = (bx + 1, bx + 1 + len(icons_label), row)
        row += 2

        save_idx = self._save_index()
        cancel_idx = self._cancel_index()
        save_label = '[ Save ]'
        cancel_label = '[ Cancel ]'
        save_x = bx + 2
        cancel_x = save_x + len(save_label) + 2
        save_attr = theme_attr('button_selected') if self._selection == save_idx else theme_attr('button')
        cancel_attr = theme_attr('button_selected') if self._selection == cancel_idx else theme_attr('button')
        safe_addstr(stdscr, row, save_x, save_label, save_attr)
        safe_addstr(stdscr, row, cancel_x, cancel_label, cancel_attr)
        self._control_rows[save_idx] = row
        self._control_rows[cancel_idx] = row
        self._button_bounds[save_idx] = (save_x, save_x + len(save_label), row)
        self._button_bounds[cancel_idx] = (cancel_x, cancel_x + len(cancel_label), row)

        hint = 'Use arrows + Enter. Save persists to ~/.config/retrotui/config.toml'
        safe_addstr(stdscr, by + bh - 1, bx, hint.ljust(bw)[:bw], theme_attr('status'))

    def handle_key(self, key):
        key_code = normalize_key_code(key)
        if key_code is None:
            return None

        if key_code == curses.KEY_UP:
            self._selection = (self._selection - 1) % self._controls_count()
            return None
        if key_code == curses.KEY_DOWN:
            self._selection = (self._selection + 1) % self._controls_count()
            return None
        if key_code == curses.KEY_LEFT:
            if self._selection < self._theme_count():
                self._selection = (self._selection - 1) % self._theme_count()
                return self._activate_selection()
            if self._selection == self._toggle_show_hidden_index() and self.show_hidden:
                self.show_hidden = False
            if self._selection == self._toggle_wrap_index() and self.word_wrap_default:
                self.word_wrap_default = False
                self.app.apply_preferences(word_wrap_default=False, apply_to_open_windows=True)
            if self._selection == self._toggle_sunday_first_index() and self.sunday_first:
                self.sunday_first = False
            if self._selection == self._toggle_show_welcome_index() and self.show_welcome:
                self.show_welcome = False
            return None
        if key_code == curses.KEY_RIGHT:
            if self._selection < self._theme_count():
                self._selection = (self._selection + 1) % self._theme_count()
                return self._activate_selection()
            if self._selection == self._toggle_show_hidden_index() and not self.show_hidden:
                self.show_hidden = True
            if self._selection == self._toggle_wrap_index() and not self.word_wrap_default:
                self.word_wrap_default = True
                self.app.apply_preferences(word_wrap_default=True, apply_to_open_windows=True)
            if self._selection == self._toggle_sunday_first_index() and not self.sunday_first:
                self.sunday_first = True
            if self._selection == self._toggle_show_welcome_index() and not self.show_welcome:
                self.show_welcome = True
            return None
        if key_code in (curses.KEY_ENTER, 10, 13, 32):
            return self._activate_selection()
        return None

    def handle_click(self, mx, my):
        for idx, (x0, x1, row) in self._button_bounds.items():
            if my == row and x0 <= mx < x1:
                self._selection = idx
                return self._activate_selection()

        for idx, row in self._control_rows.items():
            if my == row:
                self._selection = idx
                return self._activate_selection()
        return None

    def close(self):
        """Revert preview state when window closes without save/cancel."""
        if not self._committed:
            self._revert_runtime()
        self._committed = True

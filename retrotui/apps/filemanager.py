"""
File Manager Application.
"""
import os
import curses
from ..ui.window import Window
from ..ui.menu import WindowMenu
from ..core.actions import ActionResult, ActionType, AppAction
from ..utils import safe_addstr, check_unicode_support, normalize_key_code
from ..constants import C_FM_SELECTED

class FileEntry:
    """Represents a file or directory entry in the file manager."""
    __slots__ = ('name', 'is_dir', 'full_path', 'size', 'display_text', 'use_unicode')

    def __init__(self, name, is_dir, full_path, size=0, use_unicode=True):
        self.name = name
        self.is_dir = is_dir
        self.full_path = full_path
        self.size = size
        self.use_unicode = use_unicode

        dir_icon = '📁' if use_unicode else '[D]'
        file_icon = '📄' if use_unicode else '[F]'
        if name == '..':
            self.display_text = f'  {dir_icon} ..'
        elif is_dir:
            self.display_text = f'  {dir_icon} {name}/'
        else:
            self.display_text = f'  {file_icon} {name:<30} {self._format_size():>8}'

    def _format_size(self):
        if self.size > 1048576:
            return f'{self.size / 1048576:.1f}M'
        elif self.size > 1024:
            return f'{self.size / 1024:.1f}K'
        else:
            return f'{self.size}B'


class FileManagerWindow(Window):
    """Interactive file manager window with directory navigation."""

    def __init__(self, x, y, w, h, start_path=None):
        super().__init__('File Manager', x, y, w, h, content=[])
        self.current_path = os.path.realpath(start_path or os.path.expanduser('~'))
        self.use_unicode = check_unicode_support()
        self.entries = []           # List[FileEntry]
        self.selected_index = 0
        self.show_hidden = False
        self.error_message = None
        self.window_menu = WindowMenu({
            'File': [
                ('Open       Enter', AppAction.FM_OPEN),
                ('Parent Dir  Bksp', AppAction.FM_PARENT),
                ('─────────────',    None),
                ('Close',            AppAction.FM_CLOSE),
            ],
            'View': [
                ('Hidden Files   H', AppAction.FM_TOGGLE_HIDDEN),
                ('Refresh',          AppAction.FM_REFRESH),
            ],
        })
        self.h = max(self.h, 8)
        self._rebuild_content()

    def _header_lines(self):
        """Number of non-entry header lines at top of content."""
        return 2  # path line + separator line

    def _entry_to_content_index(self, entry_idx):
        """Convert entry index to content list index."""
        return self._header_lines() + entry_idx

    def _content_to_entry_index(self, content_idx):
        """Convert content list index to entry index, or -1 if on header."""
        idx = content_idx - self._header_lines()
        if 0 <= idx < len(self.entries):
            return idx
        return -1

    def _rebuild_content(self):
        """Scan current directory and rebuild content + entries lists."""
        self.entries = []
        self.content = []
        self.error_message = None

        # Header: path bar + separator
        path_icon = '📂' if self.use_unicode else '[P]'
        error_icon = '⛔' if self.use_unicode else '[!]'
        self.content.append(f' {path_icon} {self.current_path}')
        self.content.append(' ' + '─' * (self.w - 4))

        # Parent directory entry (unless at filesystem root)
        if self.current_path != '/' and os.path.dirname(self.current_path) != self.current_path:
            entry = FileEntry('..', True, os.path.dirname(self.current_path), use_unicode=self.use_unicode)
            self.entries.append(entry)
            self.content.append(entry.display_text)

        try:
            raw_entries = sorted(os.listdir(self.current_path), key=str.lower)
        except PermissionError:
            self.error_message = 'Permission denied'
            self.content.append(f'  {error_icon} Permission denied')
            self._update_title()
            return
        except OSError as e:
            self.error_message = str(e)
            self.content.append(f'  {error_icon} {e}')
            self._update_title()
            return

        dirs = []
        files = []
        for name in raw_entries:
            if not self.show_hidden and name.startswith('.'):
                continue
            full_path = os.path.join(self.current_path, name)
            try:
                if os.path.isdir(full_path):
                    dirs.append(FileEntry(name, True, full_path, use_unicode=self.use_unicode))
                elif os.path.isfile(full_path):
                    size = os.path.getsize(full_path)
                    files.append(FileEntry(name, False, full_path, size, use_unicode=self.use_unicode))
            except OSError:
                continue

        for entry in dirs:
            self.entries.append(entry)
            self.content.append(entry.display_text)
        for entry in files:
            self.entries.append(entry)
            self.content.append(entry.display_text)

        if not self.entries:
            self.content.append('  (empty directory)')

        self._update_title()
        self.selected_index = 0
        self.scroll_offset = 0

    def _update_title(self):
        """Update window title to show path basename and entry count."""
        basename = os.path.basename(self.current_path) or '/'
        count = len([e for e in self.entries if e.name != '..'])
        self.title = f'File Manager - {basename} ({count} items)'

    def draw(self, stdscr):
        """Draw file manager with selection highlight."""
        super().draw(stdscr)
        if not self.visible or not self.entries:
            return

        bx, by, bw, bh = self.body_rect()
        sel_content_idx = self._entry_to_content_index(self.selected_index)
        visible_start = self.scroll_offset
        visible_end = self.scroll_offset + bh

        if visible_start <= sel_content_idx < visible_end:
            screen_row = by + (sel_content_idx - self.scroll_offset)
            sel_attr = curses.color_pair(C_FM_SELECTED) | curses.A_BOLD
            display = self.content[sel_content_idx][:bw] if sel_content_idx < len(self.content) else ''
            safe_addstr(stdscr, screen_row, bx, display.ljust(bw), sel_attr)

        # Redraw dropdown ON TOP of selection highlight
        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def navigate_to(self, path):
        """Navigate to a new directory path."""
        real_path = os.path.realpath(path)
        if os.path.isdir(real_path):
            self.current_path = real_path
            self._rebuild_content()

    def navigate_parent(self):
        """Go to parent directory, re-selecting the dir we came from."""
        parent = os.path.dirname(self.current_path)
        if parent != self.current_path:
            old_name = os.path.basename(self.current_path)
            self.navigate_to(parent)
            for i, entry in enumerate(self.entries):
                if entry.name == old_name:
                    self.selected_index = i
                    self._ensure_visible()
                    break

    def activate_selected(self):
        """Activate currently selected entry and return optional ActionResult."""
        if not self.entries:
            return None
        if self.selected_index >= len(self.entries):
            return None
        entry = self.entries[self.selected_index]
        if entry.is_dir:
            self.navigate_to(entry.full_path)
            return None
        else:
            return ActionResult(ActionType.OPEN_FILE, entry.full_path)

    def select_up(self):
        """Move selection up by one entry."""
        if self.selected_index > 0:
            self.selected_index -= 1
            self._ensure_visible()

    def select_down(self):
        """Move selection down by one entry."""
        if self.selected_index < len(self.entries) - 1:
            self.selected_index += 1
            self._ensure_visible()

    def _ensure_visible(self):
        """Auto-scroll to keep the selected entry visible."""
        _, _, _, bh = self.body_rect()
        sel_content = self._entry_to_content_index(self.selected_index)
        if sel_content < self.scroll_offset:
            self.scroll_offset = sel_content
        elif sel_content >= self.scroll_offset + bh:
            self.scroll_offset = sel_content - bh + 1

    def toggle_hidden(self):
        """Toggle show/hide hidden files."""
        self.show_hidden = not self.show_hidden
        self._rebuild_content()

    def _execute_menu_action(self, action):
        """Execute a window menu action. Returns signal or None."""
        if action == AppAction.FM_OPEN:
            return self.activate_selected()
        elif action == AppAction.FM_PARENT:
            self.navigate_parent()
        elif action == AppAction.FM_TOGGLE_HIDDEN:
            self.toggle_hidden()
        elif action == AppAction.FM_REFRESH:
            self._rebuild_content()
        elif action == AppAction.FM_CLOSE:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

    def handle_click(self, mx, my):
        """Handle a click within the window body. Returns action result or None."""
        # Window menu intercept
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if action:
                    return self._execute_menu_action(action)
                return None

        bx, by, bw, bh = self.body_rect()
        if not (bx <= mx < bx + bw and by <= my < by + bh):
            return None
        content_idx = self.scroll_offset + (my - by)
        entry_idx = self._content_to_entry_index(content_idx)
        if entry_idx >= 0:
            self.selected_index = entry_idx
            return self.activate_selected()
        return None

    def handle_key(self, key):
        """Handle keyboard input for the file manager.
        Returns ActionResult when needed, else None."""
        key_code = normalize_key_code(key)

        # Window menu keyboard handling
        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self._execute_menu_action(action)
            return None

        if key_code == curses.KEY_UP:
            self.select_up()
        elif key_code == curses.KEY_DOWN:
            self.select_down()
        elif key_code in (curses.KEY_ENTER, 10, 13):
            return self.activate_selected()
        elif key_code in (curses.KEY_BACKSPACE, 127, 8):
            self.navigate_parent()
        elif key_code == curses.KEY_PPAGE:
            _, _, _, bh = self.body_rect()
            for _ in range(max(1, bh - 2)):
                self.select_up()
        elif key_code == curses.KEY_NPAGE:
            _, _, _, bh = self.body_rect()
            for _ in range(max(1, bh - 2)):
                self.select_down()
        elif key_code == curses.KEY_HOME:
            self.selected_index = 0
            self._ensure_visible()
        elif key_code == curses.KEY_END:
            if self.entries:
                self.selected_index = len(self.entries) - 1
                self._ensure_visible()
        elif key_code in (ord('h'), ord('H')):
            self.toggle_hidden()
        return None

    def handle_scroll(self, direction, steps=1):
        """Scroll wheel moves selection instead of only viewport."""
        count = max(1, steps)
        if direction == 'up':
            for _ in range(count):
                self.select_up()
        elif direction == 'down':
            for _ in range(count):
                self.select_down()

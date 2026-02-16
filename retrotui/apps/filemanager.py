"""
File Manager Application.
"""
import os
import shutil
import curses
import unicodedata
import stat
import subprocess
from datetime import datetime

try:
    import pwd
except ImportError:  # pragma: no cover - unavailable on Windows
    pwd = None
from ..ui.window import Window
from ..ui.menu import WindowMenu
from ..core.actions import ActionResult, ActionType, AppAction
from ..core.clipboard import copy_text
from ..utils import safe_addstr, check_unicode_support, normalize_key_code, theme_attr
from ..constants import C_FM_SELECTED


def _cell_width(ch):
    """Return terminal cell width for a single character."""
    if not ch:
        return 0
    if unicodedata.combining(ch):
        return 0
    if unicodedata.east_asian_width(ch) in ('W', 'F'):
        return 2
    return 1


def _fit_text_to_cells(text, max_cells):
    """Clip/pad text so rendered width does not exceed max_cells."""
    if max_cells <= 0:
        return ''
    out = []
    used = 0
    for ch in text:
        w = _cell_width(ch)
        if used + w > max_cells:
            break
        out.append(ch)
        used += w
    if used < max_cells:
        out.append(' ' * (max_cells - used))
    return ''.join(out)


class FileEntry:
    """Represents a file or directory entry in the file manager."""
    __slots__ = ('name', 'is_dir', 'full_path', 'size', 'display_text', 'use_unicode')

    def __init__(self, name, is_dir, full_path, size=0, use_unicode=True):
        self.name = name
        self.is_dir = is_dir
        self.full_path = full_path
        self.size = size
        self.use_unicode = use_unicode

        dir_icon = '[D]'
        file_icon = '[F]'
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

    KEY_F4 = getattr(curses, 'KEY_F4', -1)
    KEY_F5 = getattr(curses, 'KEY_F5', -1)
    KEY_F2 = getattr(curses, 'KEY_F2', -1)
    KEY_F6 = getattr(curses, 'KEY_F6', -1)
    KEY_F7 = getattr(curses, 'KEY_F7', -1)
    KEY_F8 = getattr(curses, 'KEY_F8', -1)
    KEY_INSERT = getattr(curses, 'KEY_IC', -1)
    PREVIEW_MIN_WIDTH = 64
    IMAGE_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'
    }

    def __init__(self, x, y, w, h, start_path=None, show_hidden_default=False):
        super().__init__('File Manager', x, y, w, h, content=[])
        self.current_path = os.path.realpath(start_path or os.path.expanduser('~'))
        self.use_unicode = check_unicode_support()
        self.entries = []           # List[FileEntry]
        self.selected_index = 0
        self.show_hidden = bool(show_hidden_default)
        self.error_message = None
        self.window_menu = WindowMenu({
            'File': [
                ('Open       Enter', AppAction.FM_OPEN),
                ('Copy          F5', AppAction.FM_COPY),
                ('Move          F4', AppAction.FM_MOVE),
                ('Rename        F2', AppAction.FM_RENAME),
                ('Delete       Del', AppAction.FM_DELETE),
                ('Undo Delete    U', AppAction.FM_UNDO_DELETE),
                ('New Folder    F7', AppAction.FM_NEW_DIR),
                ('New File      F8', AppAction.FM_NEW_FILE),
                ('Parent Dir  Bksp', AppAction.FM_PARENT),
                ('-------------',    None),
                ('Close',            AppAction.FM_CLOSE),
            ],
            'View': [
                ('Hidden Files   H', AppAction.FM_TOGGLE_HIDDEN),
                ('Dual Pane      D', 'fm_toggle_dual'),
                ('Refresh',          AppAction.FM_REFRESH),
            ],
            'Bookmarks': [
                ('Go Home         1', AppAction.FM_BOOKMARK_1),
                ('Go Root         2', AppAction.FM_BOOKMARK_2),
                ('Go /var/log     3', AppAction.FM_BOOKMARK_3),
                ('Go /etc         4', AppAction.FM_BOOKMARK_4),
                ('-------------',      None),
                ('Set #1 (here)   !', AppAction.FM_SET_BOOKMARK_1),
                ('Set #2 (here)   @', AppAction.FM_SET_BOOKMARK_2),
                ('Set #3 (here)   #', AppAction.FM_SET_BOOKMARK_3),
                ('Set #4 (here)   $', AppAction.FM_SET_BOOKMARK_4),
            ],
        })
        self.h = max(self.h, 8)
        self._pending_drag_payload = None
        self._pending_drag_origin = None
        self.bookmarks = self._default_bookmarks()
        self._last_trash_move = None
        self._preview_cache = {'key': None, 'lines': []}
        self._image_preview_backend = None
        self.dual_pane_enabled = self.w >= 92
        self.active_pane = 0
        self.secondary_path = self.current_path
        self.secondary_entries = []
        self.secondary_content = []
        self.secondary_selected_index = 0
        self.secondary_scroll_offset = 0
        self.secondary_error_message = None
        self._rebuild_content()
        if self.dual_pane_enabled:
            self._rebuild_secondary_content()

    @staticmethod
    def _dual_pane_min_width():
        """Minimum window width needed to render two panes cleanly."""
        return 92

    def _dual_pane_available(self):
        """Return True when current window size supports dual-pane layout."""
        return self.w >= self._dual_pane_min_width()

    def toggle_dual_pane(self):
        """Toggle dual-pane mode on/off, validating minimum width."""
        if self.dual_pane_enabled:
            self.dual_pane_enabled = False
            self.active_pane = 0
            return None

        if not self._dual_pane_available():
            return ActionResult(
                ActionType.ERROR,
                f'Dual-pane requires window width >= {self._dual_pane_min_width()} columns.',
            )

        self.dual_pane_enabled = True
        self.active_pane = 0
        self._rebuild_secondary_content()
        return None

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

    def _drag_payload_for_entry(self, entry):
        """Build drag payload for one entry, or None when entry is not draggable."""
        if entry is None or entry.name == '..' or entry.is_dir:
            return None
        return {
            'type': 'file_path',
            'path': entry.full_path,
            'name': entry.name,
        }

    def _set_pending_drag(self, payload, mx, my):
        """Store a drag candidate until pointer moves with button pressed."""
        self._pending_drag_payload = payload
        self._pending_drag_origin = (mx, my)

    def clear_pending_drag(self):
        """Drop any pending drag candidate state."""
        self._pending_drag_payload = None
        self._pending_drag_origin = None

    def consume_pending_drag(self, mx, my, bstate):
        """Activate pending drag once pointer moves while button stays pressed."""
        payload = self._pending_drag_payload
        origin = self._pending_drag_origin
        if payload is None or origin is None:
            return None
        if not (bstate & curses.BUTTON1_PRESSED):
            self.clear_pending_drag()
            return None
        report_flag = getattr(curses, 'REPORT_MOUSE_POSITION', 0)
        if not (bstate & report_flag):
            return None
        if (mx, my) == origin:
            return None
        self.clear_pending_drag()
        return payload

    @staticmethod
    def _slot_set_key(slot):
        """Return shifted key character for bookmark slot assignment."""
        return {1: '!', 2: '@', 3: '#', 4: '$'}.get(slot)

    @staticmethod
    def _trash_base_dir():
        """Return platform-local trash directory used for undoable delete."""
        return os.path.join(os.path.expanduser('~'), '.local', 'share', 'Trash', 'files')

    @staticmethod
    def _owner_name(uid):
        """Resolve uid to a displayable owner name."""
        if pwd is None:
            return str(uid)
        try:
            return pwd.getpwuid(uid).pw_name
        except KeyError:
            return str(uid)

    @staticmethod
    def _default_bookmarks():
        """Build default bookmark slots 1..4."""
        candidates = {
            1: os.path.expanduser('~'),
            2: os.path.sep,
            3: os.path.join(os.path.sep, 'var', 'log'),
            4: os.path.join(os.path.sep, 'etc'),
        }
        bookmarks = {}
        for slot, raw_path in candidates.items():
            path = os.path.realpath(os.path.expanduser(raw_path))
            if os.path.isdir(path):
                bookmarks[slot] = path
        if 1 not in bookmarks:
            home = os.path.realpath(os.path.expanduser('~'))
            bookmarks[1] = home if os.path.isdir(home) else os.path.sep
        return bookmarks

    def _invalidate_preview_cache(self):
        """Reset cached preview payload."""
        self._preview_cache = {'key': None, 'lines': []}

    def _panel_layout(self):
        """Return (list_width, separator_x, preview_x, preview_width)."""
        bx, _, bw, _ = self.body_rect()
        if bw < self.PREVIEW_MIN_WIDTH:
            return bw, None, None, 0
        preview_w = min(36, max(24, bw // 3))
        list_w = bw - preview_w - 1
        if list_w < 20:
            return bw, None, None, 0
        separator_x = bx + list_w
        preview_x = separator_x + 1
        return list_w, separator_x, preview_x, preview_w

    def _preview_stat_key(self, path):
        """Build cache key for preview contents from path+mtime+size."""
        try:
            st = os.stat(path)
        except OSError:
            return (path, None, None)
        mtime_ns = getattr(st, 'st_mtime_ns', int(st.st_mtime * 1_000_000_000))
        return (path, mtime_ns, st.st_size)

    def _read_text_preview(self, path, max_lines):
        """Read preview lines from text file, safely handling binary data."""
        if max_lines <= 0:
            return []
        try:
            with open(path, 'rb') as stream:
                raw = stream.read(16 * 1024)
        except OSError:
            return ['[preview unavailable]']

        if b'\x00' in raw:
            return ['[binary file]']

        text = raw.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
        lines = text.split('\n')
        if not lines:
            return ['[empty file]']
        result = [line.replace('\t', '    ') for line in lines[:max_lines]]
        if not any(result):
            return ['[empty file]']
        return result

    def _detect_image_preview_backend(self):
        """Select available command backend for image preview."""
        if self._image_preview_backend is not None:
            return self._image_preview_backend
        if shutil.which('chafa'):
            self._image_preview_backend = 'chafa'
            return self._image_preview_backend
        if shutil.which('timg'):
            self._image_preview_backend = 'timg'
            return self._image_preview_backend
        self._image_preview_backend = ''
        return self._image_preview_backend

    def _read_image_preview(self, path, max_lines, max_cols):
        """Read image preview using chafa/timg when available."""
        if max_lines <= 0 or max_cols <= 0:
            return []
        backend = self._detect_image_preview_backend()
        if not backend:
            return ['[image preview unavailable: install chafa/timg]']

        if backend == 'chafa':
            cmd = [
                'chafa',
                '--format=symbols',
                '--size', f'{max_cols}x{max_lines}',
                '--colors=none',
                path,
            ]
        else:
            cmd = [
                'timg',
                '-g', f'{max_cols}x{max_lines}',
                path,
            ]

        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2.0,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return [f'[image preview failed via {backend}]']

        if completed.returncode != 0:
            return [f'[image preview failed via {backend}]']

        lines = completed.stdout.splitlines()
        if not lines:
            return ['[empty image output]']
        return lines[:max_lines]

    def _entry_preview_lines(self, entry, max_lines, max_cols=0):
        """Return preview lines for selected entry."""
        if max_lines <= 0:
            return []
        if entry is None:
            return ['No selection.']
        if entry.name == '..':
            return ['Parent directory entry.']
        if entry.is_dir:
            try:
                names = sorted(os.listdir(entry.full_path), key=str.lower)
            except OSError:
                return ['[directory not readable]']
            if not names:
                return ['[empty directory]']
            result = []
            for name in names[:max_lines]:
                marker = '/' if os.path.isdir(os.path.join(entry.full_path, name)) else ''
                result.append(f'{name}{marker}')
            return result

        ext = os.path.splitext(entry.full_path)[1].lower()
        if ext in self.IMAGE_EXTENSIONS:
            return self._read_image_preview(entry.full_path, max_lines=max_lines, max_cols=max_cols)

        cache_key = self._preview_stat_key(entry.full_path)
        if self._preview_cache['key'] == cache_key:
            return self._preview_cache['lines'][:max_lines]
        lines = self._read_text_preview(entry.full_path, max_lines=max_lines)
        self._preview_cache = {'key': cache_key, 'lines': list(lines)}
        return lines

    def _entry_info_lines(self, entry):
        """Return short metadata lines for selected entry."""
        if entry is None:
            return ['Type: -', 'Name: -']
        try:
            st = os.stat(entry.full_path)
        except OSError:
            return [f'Name: {entry.name}', 'Type: unreadable']

        type_label = 'Directory' if entry.is_dir else 'File'
        if entry.name == '..':
            type_label = 'Parent'
        mode = stat.filemode(st.st_mode)
        owner = self._owner_name(getattr(st, 'st_uid', 0))
        mtime = datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M')
        size = '-' if entry.is_dir else FileEntry(entry.name, False, entry.full_path, st.st_size)._format_size()
        return [
            f'Name: {entry.name}',
            f'Type: {type_label}',
            f'Size: {size}',
            f'Perm: {mode}',
            f'Owner: {owner}',
            f'Mod: {mtime}',
        ]

    def _preview_lines(self, max_lines, max_cols=0):
        """Compose preview pane lines (info + content)."""
        if max_lines <= 0:
            return []
        entry = self._selected_entry()
        head = ['Preview']
        info = self._entry_info_lines(entry)
        sep = ['--------']
        body_budget = max(0, max_lines - len(head) - len(info) - len(sep))
        body = self._entry_preview_lines(entry, body_budget, max_cols=max_cols)
        return head + info + sep + body

    def _next_trash_path(self, original_path):
        """Build a non-colliding destination path inside trash directory."""
        trash_dir = self._trash_base_dir()
        os.makedirs(trash_dir, exist_ok=True)
        base_name = os.path.basename(original_path.rstrip(os.sep)) or 'item'
        candidate = os.path.join(trash_dir, base_name)
        if not os.path.exists(candidate):
            return candidate
        index = 1
        while True:
            alt = os.path.join(trash_dir, f'{base_name}.{index}')
            if not os.path.exists(alt):
                return alt
            index += 1

    def set_bookmark(self, slot, path=None):
        """Assign bookmark slot to provided path or current path."""
        if slot not in (1, 2, 3, 4):
            return ActionResult(ActionType.ERROR, 'Invalid bookmark slot.')
        target = os.path.realpath(path or self.current_path)
        if not os.path.isdir(target):
            return ActionResult(ActionType.ERROR, 'Bookmark target is not a directory.')
        self.bookmarks[slot] = target
        return None

    def navigate_bookmark(self, slot):
        """Navigate to a bookmark slot."""
        target = self.bookmarks.get(slot)
        if not target:
            return ActionResult(ActionType.ERROR, f'Bookmark {slot} is not set.')
        if not os.path.isdir(target):
            return ActionResult(ActionType.ERROR, f"Bookmark {slot} path no longer exists.")
        self.navigate_to(target)
        return None

    def undo_last_delete(self):
        """Restore last trashed path back to its original location."""
        if not self._last_trash_move:
            return ActionResult(ActionType.ERROR, 'Nothing to undo.')
        source = self._last_trash_move.get('source')
        trash_path = self._last_trash_move.get('trash')
        if not source or not trash_path or not os.path.exists(trash_path):
            self._last_trash_move = None
            return ActionResult(ActionType.ERROR, 'Undo state is no longer available.')
        if os.path.exists(source):
            return ActionResult(ActionType.ERROR, 'Cannot undo: destination already exists.')
        parent = os.path.dirname(source) or os.path.sep
        if not os.path.isdir(parent):
            return ActionResult(ActionType.ERROR, 'Cannot undo: parent directory does not exist.')
        try:
            shutil.move(trash_path, source)
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))
        self._last_trash_move = None
        self._rebuild_content()
        self._select_entry_by_name(os.path.basename(source))
        return None

    def _build_listing(self, path):
        """Scan directory and return (entries, content, error_message)."""
        entries = []
        content = []
        error_message = None

        path_icon = '[P]'
        error_icon = '[!]'
        content.append(f' {path_icon} {path}')
        content.append(' ' + '-' * (self.w - 4))

        if path != os.path.sep and os.path.dirname(path) != path:
            entry = FileEntry('..', True, os.path.dirname(path), use_unicode=self.use_unicode)
            entries.append(entry)
            content.append(entry.display_text)

        try:
            raw_entries = sorted(os.listdir(path), key=str.lower)
        except PermissionError:
            error_message = 'Permission denied'
            content.append(f'  {error_icon} Permission denied')
            return entries, content, error_message
        except OSError as exc:
            error_message = str(exc)
            content.append(f'  {error_icon} {exc}')
            return entries, content, error_message

        dirs = []
        files = []
        for name in raw_entries:
            if not self.show_hidden and name.startswith('.'):
                continue
            full_path = os.path.join(path, name)
            try:
                if os.path.isdir(full_path):
                    dirs.append(FileEntry(name, True, full_path, use_unicode=self.use_unicode))
                elif os.path.isfile(full_path):
                    size = os.path.getsize(full_path)
                    files.append(FileEntry(name, False, full_path, size, use_unicode=self.use_unicode))
            except OSError:
                continue

        for entry in dirs:
            entries.append(entry)
            content.append(entry.display_text)
        for entry in files:
            entries.append(entry)
            content.append(entry.display_text)

        if not entries:
            content.append('  (empty directory)')

        return entries, content, error_message

    def _rebuild_secondary_content(self):
        """Rebuild listing for right pane when dual-pane mode is enabled."""
        entries, content, error = self._build_listing(self.secondary_path)
        self.secondary_entries = entries
        self.secondary_content = content
        self.secondary_error_message = error
        if self.secondary_entries:
            self.secondary_selected_index = min(self.secondary_selected_index, len(self.secondary_entries) - 1)
        else:
            self.secondary_selected_index = 0
        self.secondary_scroll_offset = max(0, min(self.secondary_scroll_offset, max(0, len(self.secondary_content) - 1)))

    def _rebuild_content(self):
        """Scan current directory and rebuild content + entries lists."""
        self._invalidate_preview_cache()
        self.entries, self.content, self.error_message = self._build_listing(self.current_path)
        self._update_title()
        self.selected_index = 0
        self.scroll_offset = 0
        if self.dual_pane_enabled:
            self._rebuild_secondary_content()

    def _update_title(self):
        """Update window title to show path basename and entry count."""
        basename = os.path.basename(self.current_path) or '/'
        count = len([e for e in self.entries if e.name != '..'])
        self.title = f'File Manager - {basename} ({count} items)'

    @staticmethod
    def _draw_pane_contents(stdscr, x, y, h, width, content, scroll_offset, selected_content_idx, body_attr, selected_attr):
        """Render one list pane body and selection highlight."""
        for row in range(h):
            idx = scroll_offset + row
            line = content[idx] if idx < len(content) else ''
            safe_addstr(stdscr, y + row, x, _fit_text_to_cells(line, width), body_attr)

        if scroll_offset <= selected_content_idx < scroll_offset + h:
            screen_row = y + (selected_content_idx - scroll_offset)
            line = content[selected_content_idx] if selected_content_idx < len(content) else ''
            safe_addstr(stdscr, screen_row, x, _fit_text_to_cells(line, width), selected_attr)

    def _draw_dual_pane(self, stdscr, bx, by, bw, bh):
        """Draw two independent directory panes."""
        body_attr = theme_attr('window_body') if self.active else theme_attr('window_inactive')
        selected_attr = theme_attr('file_selected') | curses.A_BOLD

        left_w = max(1, (bw - 1) // 2)
        right_w = max(1, bw - left_w - 1)
        sep_x = bx + left_w
        right_x = sep_x + 1

        left_sel_content = self._entry_to_content_index(self.selected_index)
        right_sel_content = self._entry_to_content_index(self.secondary_selected_index)

        self._draw_pane_contents(
            stdscr,
            bx,
            by,
            bh,
            left_w,
            self.content,
            self.scroll_offset,
            left_sel_content,
            body_attr,
            selected_attr if self.active_pane == 0 else body_attr | curses.A_BOLD,
        )
        self._draw_pane_contents(
            stdscr,
            right_x,
            by,
            bh,
            right_w,
            self.secondary_content,
            self.secondary_scroll_offset,
            right_sel_content,
            body_attr,
            selected_attr if self.active_pane == 1 else body_attr | curses.A_BOLD,
        )

        for row in range(bh):
            safe_addstr(stdscr, by + row, sep_x, '|', body_attr | curses.A_BOLD)

    def draw(self, stdscr):
        """Draw file manager with selection highlight and optional preview pane."""
        super().draw(stdscr)
        if not self.visible:
            return
        if self.dual_pane_enabled and not self._dual_pane_available():
            # Auto-fallback when resized below split threshold.
            self.dual_pane_enabled = False
            self.active_pane = 0
        if not self.dual_pane_enabled and not self.entries:
            return

        bx, by, bw, bh = self.body_rect()
        if self.dual_pane_enabled:
            self._draw_dual_pane(stdscr, bx, by, bw, bh)
            if self.window_menu:
                self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)
            return

        list_w, separator_x, preview_x, preview_w = self._panel_layout()
        body_attr = theme_attr('window_body') if self.active else theme_attr('window_inactive')

        for row in range(bh):
            idx = self.scroll_offset + row
            line = self.content[idx] if idx < len(self.content) else ''
            safe_addstr(stdscr, by + row, bx, _fit_text_to_cells(line, list_w), body_attr)
            if preview_w > 0:
                separator_char = '|'
                safe_addstr(stdscr, by + row, separator_x, separator_char, body_attr | curses.A_BOLD)
                safe_addstr(stdscr, by + row, preview_x, ' ' * preview_w, body_attr)

        sel_content_idx = self._entry_to_content_index(self.selected_index)
        if self.scroll_offset <= sel_content_idx < self.scroll_offset + bh:
            screen_row = by + (sel_content_idx - self.scroll_offset)
            sel_attr = theme_attr('file_selected') | curses.A_BOLD
            display = self.content[sel_content_idx] if sel_content_idx < len(self.content) else ''
            safe_addstr(stdscr, screen_row, bx, _fit_text_to_cells(display, list_w), sel_attr)

        if preview_w > 0:
            lines = self._preview_lines(bh, preview_w)
            for row, line in enumerate(lines[:bh]):
                safe_addstr(stdscr, by + row, preview_x, _fit_text_to_cells(line, preview_w), body_attr)

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

    def _selected_entry(self):
        """Return selected FileEntry or None."""
        if not self.entries or self.selected_index < 0 or self.selected_index >= len(self.entries):
            return None
        return self.entries[self.selected_index]

    def selected_entry_for_operation(self):
        """Return active-pane selected entry for app-level operation routing."""
        if self.dual_pane_enabled and self.active_pane == 1:
            return self._secondary_selected_entry()
        return self._selected_entry()

    def _secondary_selected_entry(self):
        """Return selected FileEntry from right pane or None."""
        if (
            not self.secondary_entries
            or self.secondary_selected_index < 0
            or self.secondary_selected_index >= len(self.secondary_entries)
        ):
            return None
        return self.secondary_entries[self.secondary_selected_index]

    def _secondary_ensure_visible(self):
        """Auto-scroll right pane to keep selected entry visible."""
        _, _, bw, bh = self.body_rect()
        pane_w = max(1, (bw - 1) // 2)
        _ = pane_w  # reserved for future width-aware clipping
        sel_content = self._entry_to_content_index(self.secondary_selected_index)
        if sel_content < self.secondary_scroll_offset:
            self.secondary_scroll_offset = sel_content
        elif sel_content >= self.secondary_scroll_offset + bh:
            self.secondary_scroll_offset = sel_content - bh + 1

    def _select_secondary_entry_by_name(self, name):
        """Select first right-pane entry by name."""
        for idx, candidate in enumerate(self.secondary_entries):
            if candidate.name == name:
                self.secondary_selected_index = idx
                self._secondary_ensure_visible()
                return True
        return False

    def _secondary_navigate_to(self, path):
        """Navigate right pane to a directory path."""
        real_path = os.path.realpath(path)
        if not os.path.isdir(real_path):
            return
        self.secondary_path = real_path
        self._rebuild_secondary_content()

    def _secondary_navigate_parent(self):
        """Navigate right pane to parent and keep previous folder selected."""
        parent = os.path.dirname(self.secondary_path)
        if parent == self.secondary_path:
            return
        old_name = os.path.basename(self.secondary_path)
        self._secondary_navigate_to(parent)
        self._select_secondary_entry_by_name(old_name)

    def _secondary_activate_selected(self):
        """Activate selected entry in right pane."""
        entry = self._secondary_selected_entry()
        if entry is None:
            return None
        if entry.is_dir:
            self._secondary_navigate_to(entry.full_path)
            return None
        return ActionResult(ActionType.OPEN_FILE, entry.full_path)

    def _dual_copy_move_between_panes(self, move=False):
        """Copy/move selected entry from active pane to inactive pane directory."""
        if not self.dual_pane_enabled:
            return None

        source_entry = self._selected_entry() if self.active_pane == 0 else self._secondary_selected_entry()
        target_dir = self.secondary_path if self.active_pane == 0 else self.current_path
        if source_entry is None:
            return ActionResult(ActionType.ERROR, 'No item selected.')
        if source_entry.name == '..':
            return ActionResult(ActionType.ERROR, 'Cannot copy/move parent entry.')

        target_path, error = self._resolve_destination_path(source_entry, target_dir)
        if error:
            return error

        try:
            if move:
                shutil.move(source_entry.full_path, target_path)
            elif source_entry.is_dir:
                shutil.copytree(source_entry.full_path, target_path)
            else:
                shutil.copy2(source_entry.full_path, target_path)
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        self._rebuild_content()
        self._rebuild_secondary_content()
        if move and self.active_pane == 0:
            self._select_secondary_entry_by_name(os.path.basename(target_path))
        elif move and self.active_pane == 1:
            self._select_entry_by_name(os.path.basename(target_path))
        return None

    def rename_selected(self, new_name):
        """Rename selected file/directory to new_name."""
        entry = self._selected_entry()
        if entry is None:
            return ActionResult(ActionType.ERROR, 'No item selected.')
        if entry.name == '..':
            return ActionResult(ActionType.ERROR, 'Cannot rename parent entry.')

        target_name = (new_name or '').strip()
        if not target_name:
            return ActionResult(ActionType.ERROR, 'Name cannot be empty.')
        if os.sep in target_name or (os.altsep and os.altsep in target_name):
            return ActionResult(ActionType.ERROR, 'Name cannot contain path separators.')

        old_path = entry.full_path
        new_path = os.path.join(self.current_path, target_name)
        if old_path == new_path:
            return None
        if os.path.exists(new_path):
            return ActionResult(ActionType.ERROR, f"'{target_name}' already exists.")

        try:
            os.rename(old_path, new_path)
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        self._rebuild_content()
        for idx, candidate in enumerate(self.entries):
            if candidate.name == target_name:
                self.selected_index = idx
                break
        self._ensure_visible()
        return None

    def delete_selected(self):
        """Move selected file/directory to local trash."""
        entry = self._selected_entry()
        if entry is None:
            return ActionResult(ActionType.ERROR, 'No item selected.')
        if entry.name == '..':
            return ActionResult(ActionType.ERROR, 'Cannot delete parent entry.')

        selected = self.selected_index
        source_path = entry.full_path
        trash_path = self._next_trash_path(source_path)
        try:
            shutil.move(source_path, trash_path)
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        self._last_trash_move = {'source': source_path, 'trash': trash_path}
        self._rebuild_content()
        if self.entries:
            self.selected_index = min(selected, len(self.entries) - 1)
            self._ensure_visible()
        return None

    def _select_entry_by_name(self, name):
        """Select first entry matching name when available."""
        for idx, candidate in enumerate(self.entries):
            if candidate.name == name:
                self.selected_index = idx
                self._ensure_visible()
                self._invalidate_preview_cache()
                return True
        return False

    def _normalize_new_name(self, name):
        """Validate plain filename (no path components)."""
        target = (name or '').strip()
        if not target:
            return None, ActionResult(ActionType.ERROR, 'Name cannot be empty.')
        if os.sep in target or (os.altsep and os.altsep in target):
            return None, ActionResult(ActionType.ERROR, 'Name cannot contain path separators.')
        return target, None

    def create_directory(self, name):
        """Create a new directory in current path."""
        folder_name, error = self._normalize_new_name(name)
        if error:
            return error

        new_path = os.path.join(self.current_path, folder_name)
        if os.path.exists(new_path):
            return ActionResult(ActionType.ERROR, f"'{folder_name}' already exists.")

        try:
            os.mkdir(new_path)
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        self._rebuild_content()
        self._select_entry_by_name(folder_name)
        return None

    def create_file(self, name):
        """Create a new empty file in current path."""
        file_name, error = self._normalize_new_name(name)
        if error:
            return error

        new_path = os.path.join(self.current_path, file_name)
        if os.path.exists(new_path):
            return ActionResult(ActionType.ERROR, f"'{file_name}' already exists.")

        try:
            with open(new_path, 'x', encoding='utf-8'):
                pass
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        self._rebuild_content()
        self._select_entry_by_name(file_name)
        return None

    def _resolve_destination_path(self, entry, destination):
        """Resolve destination path for copy/move operations."""
        raw = (destination or '').strip()
        if not raw:
            return None, ActionResult(ActionType.ERROR, 'Destination cannot be empty.')

        dest_path = os.path.abspath(os.path.expanduser(raw))
        if os.path.isdir(dest_path):
            target_path = os.path.join(dest_path, entry.name)
        else:
            target_path = dest_path

        source_real = os.path.realpath(entry.full_path)
        target_real = os.path.realpath(target_path)
        if source_real == target_real:
            return None, ActionResult(ActionType.ERROR, 'Source and destination are the same.')

        parent = os.path.dirname(target_path) or '.'
        if not os.path.isdir(parent):
            return None, ActionResult(ActionType.ERROR, 'Destination directory does not exist.')
        if os.path.exists(target_path):
            return None, ActionResult(ActionType.ERROR, 'Destination already exists.')

        if entry.is_dir and target_real.startswith(source_real + os.sep):
            return None, ActionResult(ActionType.ERROR, 'Cannot copy/move a directory into itself.')

        return target_path, None

    def copy_selected(self, destination):
        """Copy selected entry to destination path or directory."""
        entry = self._selected_entry()
        if entry is None:
            return ActionResult(ActionType.ERROR, 'No item selected.')
        if entry.name == '..':
            return ActionResult(ActionType.ERROR, 'Cannot copy parent entry.')

        target_path, error = self._resolve_destination_path(entry, destination)
        if error:
            return error

        try:
            if entry.is_dir:
                shutil.copytree(entry.full_path, target_path)
            else:
                shutil.copy2(entry.full_path, target_path)
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        self._rebuild_content()
        self._select_entry_by_name(entry.name)
        return None

    def move_selected(self, destination):
        """Move selected entry to destination path or directory."""
        entry = self._selected_entry()
        if entry is None:
            return ActionResult(ActionType.ERROR, 'No item selected.')
        if entry.name == '..':
            return ActionResult(ActionType.ERROR, 'Cannot move parent entry.')

        selected = self.selected_index
        target_path, error = self._resolve_destination_path(entry, destination)
        if error:
            return error

        try:
            shutil.move(entry.full_path, target_path)
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        self._rebuild_content()
        target_parent = os.path.realpath(os.path.dirname(target_path) or '.')
        if target_parent == self.current_path:
            self._select_entry_by_name(os.path.basename(target_path))
        elif self.entries:
            self.selected_index = min(selected, len(self.entries) - 1)
            self._ensure_visible()
        return None

    def select_up(self):
        """Move selection up by one entry."""
        if self.selected_index > 0:
            self.selected_index -= 1
            self._ensure_visible()
            self._invalidate_preview_cache()

    def select_down(self):
        """Move selection down by one entry."""
        if self.selected_index < len(self.entries) - 1:
            self.selected_index += 1
            self._ensure_visible()
            self._invalidate_preview_cache()

    def _secondary_select_up(self):
        """Move right-pane selection up by one entry."""
        if self.secondary_selected_index > 0:
            self.secondary_selected_index -= 1
            self._secondary_ensure_visible()

    def _secondary_select_down(self):
        """Move right-pane selection down by one entry."""
        if self.secondary_selected_index < len(self.secondary_entries) - 1:
            self.secondary_selected_index += 1
            self._secondary_ensure_visible()

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
            if self.dual_pane_enabled and self.active_pane == 1:
                return self._secondary_activate_selected()
            return self.activate_selected()
        elif action == AppAction.FM_COPY:
            if self.dual_pane_enabled:
                return self._dual_copy_move_between_panes(move=False)
            return ActionResult(ActionType.REQUEST_COPY_ENTRY)
        elif action == AppAction.FM_MOVE:
            if self.dual_pane_enabled:
                return self._dual_copy_move_between_panes(move=True)
            return ActionResult(ActionType.REQUEST_MOVE_ENTRY)
        elif action == AppAction.FM_RENAME:
            return ActionResult(ActionType.REQUEST_RENAME_ENTRY)
        elif action == AppAction.FM_DELETE:
            return ActionResult(ActionType.REQUEST_DELETE_CONFIRM)
        elif action == AppAction.FM_UNDO_DELETE:
            return self.undo_last_delete()
        elif action == AppAction.FM_NEW_DIR:
            return ActionResult(ActionType.REQUEST_NEW_DIR)
        elif action == AppAction.FM_NEW_FILE:
            return ActionResult(ActionType.REQUEST_NEW_FILE)
        elif action == AppAction.FM_PARENT:
            if self.dual_pane_enabled and self.active_pane == 1:
                self._secondary_navigate_parent()
            else:
                self.navigate_parent()
        elif action == AppAction.FM_TOGGLE_HIDDEN:
            self.toggle_hidden()
        elif action == 'fm_toggle_dual':
            return self.toggle_dual_pane()
        elif action == AppAction.FM_REFRESH:
            self._rebuild_content()
        elif action == AppAction.FM_BOOKMARK_1:
            return self.navigate_bookmark(1)
        elif action == AppAction.FM_BOOKMARK_2:
            return self.navigate_bookmark(2)
        elif action == AppAction.FM_BOOKMARK_3:
            return self.navigate_bookmark(3)
        elif action == AppAction.FM_BOOKMARK_4:
            return self.navigate_bookmark(4)
        elif action == AppAction.FM_SET_BOOKMARK_1:
            return self.set_bookmark(1)
        elif action == AppAction.FM_SET_BOOKMARK_2:
            return self.set_bookmark(2)
        elif action == AppAction.FM_SET_BOOKMARK_3:
            return self.set_bookmark(3)
        elif action == AppAction.FM_SET_BOOKMARK_4:
            return self.set_bookmark(4)
        elif action == AppAction.FM_CLOSE:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

    def handle_click(self, mx, my, bstate=None):
        """Handle a click within the window body. Single-click selects; double-click opens."""
        # Window menu intercept
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if action:
                    self.clear_pending_drag()
                    return self._execute_menu_action(action)
                self.clear_pending_drag()
                return None

        bx, by, bw, bh = self.body_rect()
        if not (bx <= mx < bx + bw and by <= my < by + bh):
            self.clear_pending_drag()
            return None

        if self.dual_pane_enabled:
            left_w = max(1, (bw - 1) // 2)
            right_x = bx + left_w + 1
            in_right = mx >= right_x

            if in_right:
                self.active_pane = 1
                content_idx = self.secondary_scroll_offset + (my - by)
                entry_idx = self._content_to_entry_index(content_idx)
                if entry_idx >= 0:
                    self.secondary_selected_index = entry_idx
                    entry = self.secondary_entries[entry_idx]
                    if bstate and (bstate & curses.BUTTON1_DOUBLE_CLICKED):
                        self.clear_pending_drag()
                        return self._secondary_activate_selected()
                    if bstate and (bstate & curses.BUTTON1_PRESSED):
                        payload = self._drag_payload_for_entry(entry)
                        if payload is not None:
                            self._set_pending_drag(payload, mx, my)
                        else:
                            self.clear_pending_drag()
                else:
                    self.clear_pending_drag()
                return None

            self.active_pane = 0

        content_idx = self.scroll_offset + (my - by)
        entry_idx = self._content_to_entry_index(content_idx)
        if entry_idx >= 0:
            changed = entry_idx != self.selected_index
            self.selected_index = entry_idx
            if changed:
                self._invalidate_preview_cache()
            entry = self.entries[entry_idx]
            if bstate and (bstate & curses.BUTTON1_PRESSED):
                payload = self._drag_payload_for_entry(entry)
                if payload is not None:
                    self._set_pending_drag(payload, mx, my)
                else:
                    self.clear_pending_drag()
            if bstate and (bstate & curses.BUTTON1_DOUBLE_CLICKED):
                self.clear_pending_drag()
                return self.activate_selected()
            if bstate and not (bstate & curses.BUTTON1_PRESSED):
                self.clear_pending_drag()
        else:
            self.clear_pending_drag()
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

        if key_code == 9 and self.dual_pane_enabled:
            self.active_pane = 1 - self.active_pane
            return None

        nav_up = self.select_up if self.active_pane == 0 else self._secondary_select_up
        nav_down = self.select_down if self.active_pane == 0 else self._secondary_select_down
        activate = self.activate_selected if self.active_pane == 0 else self._secondary_activate_selected
        parent_nav = self.navigate_parent if self.active_pane == 0 else self._secondary_navigate_parent

        if key_code == curses.KEY_UP:
            nav_up()
        elif key_code == curses.KEY_DOWN:
            nav_down()
        elif key_code in (curses.KEY_ENTER, 10, 13):
            return activate()
        elif key_code in (curses.KEY_BACKSPACE, 127, 8):
            parent_nav()
        elif key_code == curses.KEY_PPAGE:
            _, _, _, bh = self.body_rect()
            for _ in range(max(1, bh - 2)):
                nav_up()
        elif key_code == curses.KEY_NPAGE:
            _, _, _, bh = self.body_rect()
            for _ in range(max(1, bh - 2)):
                nav_down()
        elif key_code == curses.KEY_HOME:
            if self.active_pane == 0:
                self.selected_index = 0
                self._ensure_visible()
            else:
                self.secondary_selected_index = 0
                self._secondary_ensure_visible()
        elif key_code == curses.KEY_END:
            if self.active_pane == 0 and self.entries:
                self.selected_index = len(self.entries) - 1
                self._ensure_visible()
            elif self.active_pane == 1 and self.secondary_entries:
                self.secondary_selected_index = len(self.secondary_entries) - 1
                self._secondary_ensure_visible()
        elif key_code in (ord('h'), ord('H')):
            self.toggle_hidden()
        elif key_code in (ord('d'), ord('D')):
            return self.toggle_dual_pane()
        elif key_code in (ord('u'), ord('U'), 26):
            return self.undo_last_delete()
        elif key_code in (ord('1'), ord('2'), ord('3'), ord('4')):
            slot = int(chr(key_code))
            return self.navigate_bookmark(slot)
        elif key_code in (ord('!'), ord('@'), ord('#'), ord('$')):
            mapping = {ord('!'): 1, ord('@'): 2, ord('#'): 3, ord('$'): 4}
            return self.set_bookmark(mapping[key_code])
        elif key_code == self.KEY_F5:
            if self.dual_pane_enabled:
                return self._dual_copy_move_between_panes(move=False)
            return ActionResult(ActionType.REQUEST_COPY_ENTRY)
        elif key_code == self.KEY_F4:
            if self.dual_pane_enabled:
                return self._dual_copy_move_between_panes(move=True)
            return ActionResult(ActionType.REQUEST_MOVE_ENTRY)
        elif key_code == self.KEY_F2:
            if self.dual_pane_enabled and self.active_pane == 1:
                return ActionResult(ActionType.ERROR, 'Use left pane for rename/new/delete dialogs.')
            return ActionResult(ActionType.REQUEST_RENAME_ENTRY)
        elif key_code == curses.KEY_DC:
            if self.dual_pane_enabled and self.active_pane == 1:
                return ActionResult(ActionType.ERROR, 'Use left pane for rename/new/delete dialogs.')
            return ActionResult(ActionType.REQUEST_DELETE_CONFIRM)
        elif key_code == self.KEY_F7:
            if self.dual_pane_enabled and self.active_pane == 1:
                return ActionResult(ActionType.ERROR, 'Use left pane for rename/new/delete dialogs.')
            return ActionResult(ActionType.REQUEST_NEW_DIR)
        elif key_code == self.KEY_F8:
            if self.dual_pane_enabled and self.active_pane == 1:
                return ActionResult(ActionType.ERROR, 'Use left pane for rename/new/delete dialogs.')
            return ActionResult(ActionType.REQUEST_NEW_FILE)
        elif key_code in (self.KEY_F6, self.KEY_INSERT):
            if self.active_pane == 0 and 0 <= self.selected_index < len(self.entries):
                copy_text(self.entries[self.selected_index].full_path)
            elif self.active_pane == 1 and 0 <= self.secondary_selected_index < len(self.secondary_entries):
                copy_text(self.secondary_entries[self.secondary_selected_index].full_path)
        return None

    def handle_tab_key(self):
        """Handle Tab locally when dual-pane mode is enabled."""
        if not self.dual_pane_enabled:
            return False
        self.active_pane = 1 - self.active_pane
        return True

    def handle_scroll(self, direction, steps=1):
        """Scroll wheel moves selection instead of only viewport."""
        count = max(1, steps)
        up = self.select_up if self.active_pane == 0 else self._secondary_select_up
        down = self.select_down if self.active_pane == 0 else self._secondary_select_down
        if direction == 'up':
            for _ in range(count):
                up()
        elif direction == 'down':
            for _ in range(count):
                down()

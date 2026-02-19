"""
File Manager Window UI.
"""
import os
import curses
import shutil
import time
from ...ui.window import Window
from ...ui.menu import WindowMenu
from ...core.actions import ActionResult, ActionType, AppAction
from ...utils import safe_addstr, check_unicode_support, theme_attr, normalize_key_code
from ...constants import WIN_MIN_WIDTH, WIN_MIN_HEIGHT
from .core import FileEntry, _fit_text_to_cells, _cell_width
from .operations import (
    _trash_base_dir, perform_copy, perform_move, perform_delete, perform_undo,
    create_directory, create_file, _is_long_file_operation, next_trash_path
)
from .preview import get_preview_lines, get_entry_info_lines, IMAGE_EXTENSIONS, _read_text_preview, _read_image_preview
from .bookmarks import get_default_bookmarks, set_bookmark, navigate_bookmark

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
    IMAGE_EXTENSIONS = IMAGE_EXTENSIONS
    DUAL_PANE_MIN_WIDTH = 92
    PAGE_SCROLL_STEP = 10
    PREVIEW_MAX_WIDTH = 36
    PREVIEW_PANEL_MIN_WIDTH = 24
    PANE_MIN_RENDER_WIDTH = 4
    HEADER_SEP_MARGIN = 4

    _MENU_ACTION_MAP = {
        AppAction.FM_OPEN: 'activate_selected',
        AppAction.FM_COPY: lambda self: ActionResult(ActionType.REQUEST_COPY_ENTRY),
        AppAction.FM_MOVE: lambda self: ActionResult(ActionType.REQUEST_MOVE_ENTRY),
        AppAction.FM_RENAME: lambda self: ActionResult(ActionType.REQUEST_RENAME_ENTRY),
        AppAction.FM_DELETE: lambda self: ActionResult(ActionType.REQUEST_DELETE_CONFIRM),
        AppAction.FM_NEW_DIR: lambda self: ActionResult(ActionType.REQUEST_NEW_DIR),
        AppAction.FM_NEW_FILE: lambda self: ActionResult(ActionType.REQUEST_NEW_FILE),
        AppAction.FM_UNDO_DELETE: 'undo_delete',
        AppAction.FM_REFRESH: '_action_refresh',
        AppAction.FM_TOGGLE_HIDDEN: 'toggle_hidden',
        AppAction.FM_PARENT: '_action_parent',
        AppAction.FM_CLOSE: lambda self: ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW),
        'fm_toggle_dual': 'toggle_dual_pane',
        AppAction.FM_BOOKMARK_1: lambda self: self.navigate_bookmark(1),
        AppAction.FM_BOOKMARK_2: lambda self: self.navigate_bookmark(2),
        AppAction.FM_BOOKMARK_3: lambda self: self.navigate_bookmark(3),
        AppAction.FM_BOOKMARK_4: lambda self: self.navigate_bookmark(4),
        AppAction.FM_SET_BOOKMARK_1: lambda self: self.set_bookmark(1),
        AppAction.FM_SET_BOOKMARK_2: lambda self: self.set_bookmark(2),
        AppAction.FM_SET_BOOKMARK_3: lambda self: self.set_bookmark(3),
        AppAction.FM_SET_BOOKMARK_4: lambda self: self.set_bookmark(4),
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
        self.h = max(self.h, WIN_MIN_HEIGHT)
        self._pending_drag_payload = None
        self._pending_drag_origin = None
        self.bookmarks = get_default_bookmarks()
        self._last_trash_move = None
        self._preview_cache = {'key': None, 'lines': []}
        self.dual_pane_enabled = self.w >= self.DUAL_PANE_MIN_WIDTH
        self.active_pane = 0
        self.secondary_path = self.current_path
        self.secondary_entries = []
        self.secondary_content = []
        self.secondary_selected_index = 0
        self.secondary_scroll_offset = 0
        self.secondary_error_message = None
        self.last_click_time = 0
        self.last_click_index = -1
        self._rebuild_content()
        if self.dual_pane_enabled:
            self._rebuild_secondary_content()

    @staticmethod
    def _dual_pane_min_width():
        """Minimum window width needed to render two panes cleanly."""
        return FileManagerWindow.DUAL_PANE_MIN_WIDTH

    def _dual_pane_available(self):
        """Return True when current window size supports dual-pane layout."""
        return self.w >= self._dual_pane_min_width()

    def toggle_dual_pane(self):
        """Toggle dual-pane mode on/off, validating minimum width."""
        if self.dual_pane_enabled:
            self.dual_pane_enabled = False
            self.active_pane = 0
            return ActionResult(ActionType.REFRESH)

        if not self._dual_pane_available():
            return ActionResult(
                ActionType.ERROR,
                f'Dual-pane requires window width >= {self._dual_pane_min_width()} columns.',
            )

        self.dual_pane_enabled = True
        self.active_pane = 0
        self._rebuild_secondary_content()
        return ActionResult(ActionType.REFRESH)

    def _header_lines(self):
        return 2

    def _entry_to_content_index(self, entry_idx):
        return self._header_lines() + entry_idx

    def _content_to_entry_index(self, content_idx):
        idx = content_idx - self._header_lines()
        if 0 <= idx < len(self.entries):
            return idx
        return -1

    def _drag_payload_for_entry(self, entry):
        if entry is None or entry.name == '..' or entry.is_dir:
            return None
        return {
            'type': 'file_path',
            'path': entry.full_path,
            'name': entry.name,
        }

    def _set_pending_drag(self, payload, mx, my):
        self._pending_drag_payload = payload
        self._pending_drag_origin = (mx, my)

    def clear_pending_drag(self):
        self._pending_drag_payload = None
        self._pending_drag_origin = None

    def consume_pending_drag(self, mx, my, bstate):
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

    def _invalidate_preview_cache(self):
        self._preview_cache = {'key': None, 'lines': []}

    def _panel_layout(self):
        bx, _, bw, _ = self.body_rect()
        if bw < self.PREVIEW_MIN_WIDTH:
            return bw, None, None, 0
        preview_w = min(self.PREVIEW_MAX_WIDTH, max(self.PREVIEW_PANEL_MIN_WIDTH, bw // 3))
        list_w = bw - preview_w - 1
        if list_w < WIN_MIN_WIDTH:
            return bw, None, None, 0
        separator_x = bx + list_w
        preview_x = separator_x + 1
        return list_w, separator_x, preview_x, preview_w

    def _preview_stat_key(self, path):
        try:
            st = os.stat(path)
        except OSError:
            return (path, None, None)
        mtime_ns = getattr(st, 'st_mtime_ns', int(st.st_mtime * 1_000_000_000))
        return (path, mtime_ns, st.st_size)

    def _entry_preview_lines(self, entry, max_lines, max_cols=0):
        if max_lines <= 0:
            return []
        if entry is None or entry.name == '..':
             return get_preview_lines(entry, max_lines, max_cols)

        cache_key = self._preview_stat_key(entry.full_path)
        if self._preview_cache['key'] == cache_key:
            return self._preview_cache['lines'][:max_lines]

        lines = get_preview_lines(entry, max_lines, max_cols)
        self._preview_cache = {'key': cache_key, 'lines': list(lines)}
        return lines

    def _preview_lines(self, max_lines, max_cols=0):
        if max_lines <= 0:
            return []
        entry = self._selected_entry()
        head = ['Preview']
        info = get_entry_info_lines(entry)
        sep = ['--------']
        body_budget = max(0, max_lines - len(head) - len(info) - len(sep))
        body = self._entry_preview_lines(entry, body_budget, max_cols=max_cols)
        return head + info + sep + body

    def _build_listing(self, path):
        entries = []
        content = []
        error_message = None

        path_icon = '[P]'
        error_icon = '[!]'
        content.append(f' {path_icon} {path}')
        content.append(' ' + '-' * (self.w - self.HEADER_SEP_MARGIN))

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
        old_selection = self._selected_entry()
        old_name = old_selection.name if old_selection else None
        
        self._invalidate_preview_cache()
        self.entries, self.content, self.error_message = self._build_listing(self.current_path)
        basename = os.path.basename(self.current_path) or '/'
        count = len([e for e in self.entries if e.name != '..'])
        self.title = f'File Manager - {basename} ({count} items)'
        
        self.selected_index = 0
        if old_name:
            for i, e in enumerate(self.entries):
                if e.name == old_name:
                    self.selected_index = i
                    break
                    
        self.scroll_offset = 0
        if self.selected_index >= (self.h - self._header_lines()):
             self.scroll_offset = max(0, self.selected_index - (self.h - self._header_lines()) + 1)
        if self.dual_pane_enabled:
            self._rebuild_secondary_content()

    def _select_entry_by_name(self, name):
        for i, entry in enumerate(self.entries):
             if entry.name == name:
                 self.selected_index = i
                 display_h = self.h - self._header_lines()
                 if self.selected_index >= display_h:
                      self.scroll_offset = max(0, self.selected_index - display_h + 1)
                 else:
                      self.scroll_offset = 0
                 return True
        return False

    def _ensure_visible(self):
        """Ensure the selected index is within the visible scroll area."""
        display_h = self.h - self._header_lines()
        if display_h <= 0: return
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + display_h:
            self.scroll_offset = self.selected_index - display_h + 1

    def navigate_to(self, path):
        real_path = os.path.realpath(path)
        if os.path.isdir(real_path):
            self.current_path = real_path
            self._rebuild_content()

    def navigate_parent(self):
        old_path = self.current_path
        parent = os.path.dirname(self.current_path)
        if parent == self.current_path:
            return None
        self.navigate_to(parent)
        
        # Restore selection
        basename = os.path.basename(old_path)
        for i, entry in enumerate(self.entries):
             if entry.name == basename:
                 self.selected_index = i
                 display_h = self.h - self._header_lines()
                 if self.selected_index >= display_h:
                      self.scroll_offset = max(0, self.selected_index - display_h + 1)
                 break

    def _selected_entry(self):
        if self.active_pane == 1:
            if 0 <= self.secondary_selected_index < len(self.secondary_entries):
                return self.secondary_entries[self.secondary_selected_index]
            return None
        if 0 <= self.selected_index < len(self.entries):
            return self.entries[self.selected_index]
        return None

    def selected_entry_for_operation(self):
        """Return entry to operate on (file or dir), or None."""
        return self._selected_entry()

    def activate_selected(self):
        entry = self._selected_entry()
        if not entry:
            return None
        if entry.name == '..':
            if self.active_pane == 0:
                self.navigate_parent()
            else:
                self._secondary_navigate_parent()
            return ActionResult(ActionType.REFRESH)
        if entry.is_dir:
            if self.active_pane == 0:
                self.navigate_to(entry.full_path)
            else:
                self._secondary_navigate_to(entry.full_path)
            return ActionResult(ActionType.REFRESH)
        
        return ActionResult(ActionType.OPEN_FILE, entry.full_path)

    def _secondary_navigate_to(self, path):
        real_path = os.path.realpath(path)
        if os.path.isdir(real_path):
            self.secondary_path = real_path
            self._rebuild_secondary_content()

    def _secondary_navigate_parent(self):
        parent = os.path.dirname(self.secondary_path)
        if parent == self.secondary_path:
            return None
        self._secondary_navigate_to(parent)

    # --- Actions ---

    def delete_selected(self):
        entry = self._selected_entry()
        if not entry:
            return ActionResult(ActionType.ERROR, 'No item selected.')
        return self.perform_delete_entry(entry.full_path)

    def perform_delete_entry(self, path):
        result_path = perform_delete(path)
        if result_path:
            self._last_trash_move = {'source': path, 'trash': result_path}
            self._rebuild_content()
            return ActionResult(ActionType.REFRESH, f'Moved to trash: {os.path.basename(path)}')
        return ActionResult(ActionType.ERROR, 'Failed to delete item.')

    def perform_undo_delete(self):
        if not self._last_trash_move:
             return ActionResult(ActionType.ERROR, 'Nothing to undo.')
        error = perform_undo(self._last_trash_move)
        if error:
            return error
        restored = self._last_trash_move['source']
        self._last_trash_move = None
        self._rebuild_content()
        return ActionResult(ActionType.REFRESH, f'Restored: {os.path.basename(restored)}')

    def undo_delete(self):
        return self.perform_undo_delete()

    def undo_last_delete(self):
        """Alias for tests."""
        return self.undo_delete()

    def create_directory(self, name):
        if self.active_pane == 1:
            base = self.secondary_path
        else:
            base = self.current_path
        res = create_directory(base, name)
        self._rebuild_content()
        return res

    def create_file(self, name):
        if self.active_pane == 1:
            base = self.secondary_path
        else:
            base = self.current_path
        res = create_file(base, name)
        self._rebuild_content()
        return res

    def _normalize_new_name(self, name):
        """Strip and validate a new file/folder name."""
        clean = name.strip()
        if not clean:
             return None, ActionResult(ActionType.ERROR, 'Name cannot be empty.')
        return clean, None

    def _trash_base_dir(self):
        """Proxy for trash base directory, allows monkeypatching in tests."""
        return _trash_base_dir()

    def _next_trash_path(self, path):
        """Satisfy tests for trash path generation."""
        return next_trash_path(path, trash_dir=self._trash_base_dir())

    def _read_text_preview(self, path, max_lines):
        """Wrap preview helper for tests."""
        return _read_text_preview(path, max_lines)

    def _read_image_preview(self, path, max_lines, max_cols):
        """Wrap preview helper for tests."""
        return _read_image_preview(path, max_lines, max_cols)

    def _entry_preview_lines(self, entry, max_lines, max_cols=20):
        """Wrap preview helper for tests with caching."""
        cache_key = (entry.full_path, entry.size if not entry.is_dir else 0, max_lines, max_cols)
        if self._preview_cache.get('key') == cache_key:
            return self._preview_cache['lines']
        
        lines = get_preview_lines(entry, max_lines, max_cols)
        self._preview_cache = {'key': cache_key, 'lines': lines}
        return lines

    def _entry_info_lines(self, entry):
        """Proxy for metadata info lines."""
        return get_entry_info_lines(entry)

    def _invalidate_preview_cache(self):
        """Clear the preview cache."""
        self._preview_cache = {'key': None, 'lines': []}

    def _resolve_destination_path(self, entry, dest_path):
        """Check if destination is valid and return full target path."""
        if not entry:
            return None, ActionResult(ActionType.ERROR, 'No entry selected.')
        
        if not dest_path:
            return None, ActionResult(ActionType.ERROR, 'Destination path cannot be empty.')

        target = dest_path
        if os.path.exists(dest_path) and os.path.isdir(dest_path):
            target = os.path.join(dest_path, entry.name)

        p1 = os.path.normcase(os.path.realpath(entry.full_path))
        p2 = os.path.normcase(os.path.realpath(target))
            
        if entry.is_dir and (p1 == p2 or p2.startswith(p1 + os.sep)):
             return None, ActionResult(ActionType.ERROR, 'Cannot copy/move a directory into itself or its children.')

        if p1 == p2:
             return None, ActionResult(ActionType.ERROR, 'Source and destination are the same.')

        if os.path.exists(target):
            return None, ActionResult(ActionType.ERROR, 'Destination already exists.')

        parent = os.path.dirname(target)
        if parent and not os.path.isdir(parent):
            return None, ActionResult(ActionType.ERROR, 'Destination directory does not exist.')
            
        return target, None

    def _drag_payload_for_entry(self, entry):
        """Build drag payload for an entry."""
        if not entry or entry.name == '..' or entry.is_dir:
            return None
        return {'type': 'file', 'path': entry.full_path, 'name': entry.name}

    def _set_pending_drag(self, payload, x, y):
        """Record start of a potential drag operation."""
        self._pending_drag_payload = payload
        self._pending_drag_origin = (x, y)


    def rename_selected(self, new_name):
        entry = self._selected_entry()
        if not entry:
            return ActionResult(ActionType.ERROR, 'No item selected.')
        base = os.path.dirname(entry.full_path)
        dest = os.path.join(base, new_name)
        res = perform_move(entry.full_path, dest)
        self._rebuild_content()
        if res.type == ActionType.REFRESH:
             self._select_entry_by_name(new_name)
        return res

    def copy_selected(self, dest_path):
        entry = self._selected_entry()
        if not entry:
            return ActionResult(ActionType.ERROR, 'No item selected.')
        
        target, error = self._resolve_destination_path(entry, dest_path)
        if error:
            return error

        res = perform_copy(entry.full_path, target)
        self._rebuild_content()
        return res

    def move_selected(self, dest_path):
        entry = self._selected_entry()
        if not entry:
            return ActionResult(ActionType.ERROR, 'No item selected.')
        
        target, error = self._resolve_destination_path(entry, dest_path)
        if error:
            return error

        res = perform_move(entry.full_path, target)
        self._rebuild_content()
        return res

    def _dual_copy_move_between_panes(self, move=False):
        if not self.dual_pane_enabled:
            return ActionResult(ActionType.ERROR, 'Dual pane not enabled.')
        
        source = self._selected_entry()
        if not source or source.name == '..':
            return ActionResult(ActionType.ERROR, 'No item selected.')
        
        if self.active_pane == 0:
            dest_dir = self.secondary_path
        else:
            dest_dir = self.current_path
            
        if move:
            dest_path = os.path.join(dest_dir, source.name)
            if os.path.exists(dest_path):
                return ActionResult(ActionType.ERROR, f'Destination exists: {source.name}')
            perform_move(source.full_path, dest_path)
            self._rebuild_content()
            return ActionResult(ActionType.REFRESH, f'Moved {source.name}')
        else:
            if _is_long_file_operation(source, 10 * 1024 * 1024):
                return ActionResult(ActionType.REQUEST_COPY_BETWEEN_PANES, {'source': source.full_path, 'dest': dest_dir})
            
            dest_path = os.path.join(dest_dir, source.name)
            if os.path.exists(dest_path):
                 return ActionResult(ActionType.ERROR, f'Destination exists: {source.name}')
            perform_copy(source.full_path, dest_path)
            self._rebuild_content()
            return ActionResult(ActionType.REFRESH, f'Copied {source.name}')

    def _dual_copy_move(self, move=False):
        """Alias for compatibility."""
        return self._dual_copy_move_between_panes(move)

    def refresh(self):
        self._rebuild_content()

    def toggle_hidden(self):
        """Toggle display of hidden files."""
        self.show_hidden = not self.show_hidden
        self._rebuild_content()
        return ActionResult(ActionType.REFRESH)

    def open_path(self, path):
        self.navigate_to(path)

    def navigate_bookmark(self, slot):
        res = navigate_bookmark(self.bookmarks, slot)
        if isinstance(res, str):
            self.navigate_to(res)
            return ActionResult(ActionType.REFRESH)
        else:
            return res

    def set_bookmark(self, slot, path=None):
        if path is None:
            path = self.secondary_path if self.active_pane == 1 else self.current_path
        res = set_bookmark(self.bookmarks, slot, path)
        return ActionResult(ActionType.REFRESH) if res is None else res

    def draw(self, stdscr):
        min_w = self._dual_pane_min_width()
        if self.dual_pane_enabled and self.w < min_w:
             self.dual_pane_enabled = False
             self.active_pane = 0

        border_attr = theme_attr('window_border')
        if self.active:
            border_attr = theme_attr('window_border')

        self.draw_frame(stdscr)

        if self.dual_pane_enabled:
            self._draw_dual_pane(stdscr, border_attr)
        else:
            self._draw_single_pane(stdscr, border_attr)

        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)



    def _draw_single_pane(self, stdscr, border_attr):
        list_w, sep_x, prev_x, prev_w = self._panel_layout()
        bx, by, bw, bh = self.body_rect()
        
        if sep_x:
            for i in range(bh):
                safe_addstr(stdscr, by + i, sep_x, '\u2502', border_attr)
            safe_addstr(stdscr, by - 1, sep_x, '\u252c', border_attr)
            safe_addstr(stdscr, by + bh, sep_x, '\u2534', border_attr)

        self._draw_pane_contents(stdscr, 0, bx, by, list_w, bh, self.content, self.scroll_offset, self.selected_index, self.error_message)

        if prev_x:
            lines = self._preview_lines(bh, max_cols=prev_w)
            for i in range(bh):
                if i < len(lines):
                     safe_addstr(stdscr, by + i, prev_x, _fit_text_to_cells(lines[i], prev_w), theme_attr('window_body'))
                else:
                     safe_addstr(stdscr, by + i, prev_x, ' ' * prev_w, theme_attr('window_body'))

    def _draw_dual_pane(self, stdscr, border_attr):
        bx, by, bw, bh = self.body_rect()
        mid_x = bx + (bw // 2)
        pane1_w = mid_x - bx
        pane2_w = bw - pane1_w - 1
        
        for i in range(bh):
            safe_addstr(stdscr, by + i, mid_x, '\u2502', border_attr)
        safe_addstr(stdscr, by - 1, mid_x, '\u252c', border_attr)
        safe_addstr(stdscr, by + bh, mid_x, '\u2534', border_attr)

        self._draw_pane_contents(
            stdscr, 0, bx, by, pane1_w, bh, 
            self.content, self.scroll_offset, self.selected_index, self.error_message,
            is_active=(self.active_pane == 0)
        )
        self._draw_pane_contents(
            stdscr, 1, mid_x + 1, by, pane2_w, bh, 
            self.secondary_content, self.secondary_scroll_offset, self.secondary_selected_index, self.secondary_error_message,
            is_active=(self.active_pane == 1)
        )

    def _entry_display_attr(self, entry_obj, is_selected, is_active_pane):
        """Compute the curses display attribute for a file entry."""
        if is_selected and is_active_pane and self.active:
            return theme_attr('menu_selected')
        if entry_obj is None:
            return theme_attr('window_body')
        if entry_obj.is_dir:
            return theme_attr('file_directory')
        if getattr(entry_obj, 'size', 0) > 0 and (entry_obj.size & 0x111):
            try:
                if os.access(entry_obj.full_path, os.X_OK):
                    return theme_attr('window_body') | curses.A_BOLD
            except Exception:
                pass
        return theme_attr('window_body')

    def _draw_pane_contents(self, stdscr, pane_id, x, y, w, h, content, scroll, selected, error_msg, is_active=True):
        if w < self.PANE_MIN_RENDER_WIDTH: return
        
        bar_attr = theme_attr('window_title' if is_active and self.active else 'window_inactive')
        path_line = content[0] if content else ''
        safe_addstr(stdscr, y, x, _fit_text_to_cells(path_line, w), bar_attr)
        
        sep_line = content[1] if len(content) > 1 else ''
        dir_attr = theme_attr('file_directory')
        safe_addstr(stdscr, y + 1, x, _fit_text_to_cells(sep_line, w), dir_attr)

        if error_msg:
             safe_addstr(stdscr, y + 2, x + 2, f'Error: {error_msg}'[:w-2], theme_attr('window_body'))
             return

        items = content[self._header_lines():]
        display_h = h - self._header_lines()
        
        for k in range(display_h):
             line_y = y + self._header_lines() + k
             idx = scroll + k
             if idx >= len(items):
                 safe_addstr(stdscr, line_y, x, ' ' * w, theme_attr('window_body'))
                 continue
             
             line_str = _fit_text_to_cells(items[idx], w)
             
             is_sel = (idx == selected)

             entries_src = self.entries if pane_id == 0 else self.secondary_entries
             entry_obj = entries_src[idx] if 0 <= idx < len(entries_src) else None

             attr = self._entry_display_attr(entry_obj, is_sel, is_active)

             safe_addstr(stdscr, line_y, x, line_str, attr)

    def handle_scroll(self, direction, amount=3):
        if self.active_pane == 1:
            if direction == 'up':
                self.secondary_scroll_offset = max(0, self.secondary_scroll_offset - amount)
            else:
                max_scroll = max(0, len(self.secondary_entries) - 1)
                self.secondary_scroll_offset = min(max_scroll, self.secondary_scroll_offset + amount)
            return True
        else:
            return super().handle_scroll(direction, amount)

    def handle_click(self, mx, my, bstate=None):
        self._pending_drag_payload = None  # Clear any previous pending drag
        
        # Window menu intercept
        if self.window_menu:
             if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                 action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                 if action:
                     return self.execute_action(action)
                 return None

        bx, by, bw, bh = self.body_rect()
        
        clicked_pane = 0
        if self.dual_pane_enabled:
            mid_x = bx + (bw // 2)
            if mx > mid_x:
                clicked_pane = 1
        
        if clicked_pane != self.active_pane:
            self.active_pane = clicked_pane
            return ActionResult(ActionType.REFRESH)

        row = my - by
        if row < self._header_lines():
             return None
             
        list_idx = row - self._header_lines()
        
        now = time.time()
        is_double = False
        
        if clicked_pane == 1:
             new_sel = self.secondary_scroll_offset + list_idx
             if 0 <= new_sel < len(self.secondary_entries):
                 click_id = 10000 + new_sel
                 if click_id == self.last_click_index and (now - self.last_click_time < 0.5):
                     is_double = True
                 self.last_click_time = now
                 self.last_click_index = click_id
                 
                 self.secondary_selected_index = new_sel
                 if is_double:
                     return self.activate_selected()
                 return ActionResult(ActionType.REFRESH)
        else:
             new_sel = self.scroll_offset + list_idx
             if 0 <= new_sel < len(self.entries):
                 click_id = new_sel
                 if click_id == self.last_click_index and (now - self.last_click_time < 0.5):
                     is_double = True
                 self.last_click_time = now
                 self.last_click_index = click_id
                 
                 self.selected_index = new_sel
                 
                 # Check for drag start
                 if bstate is not None and (bstate & curses.BUTTON1_PRESSED):
                     entry = self.entries[new_sel]
                     payload = self._drag_payload_for_entry(entry)
                     if payload:
                         self._set_pending_drag(payload, mx, my)
                         
                 if is_double:
                     return self.activate_selected()
                 return ActionResult(ActionType.REFRESH)
        
        return None

    def handle_right_click(self, mx, my, bstate):
        bx, by, bw, bh = self.body_rect()
        if not (bx <= mx < bx + bw and by <= my < by + bh):
            return False

        clicked_pane = 0
        if self.dual_pane_enabled:
            left_w = max(1, (bw - 1) // 2)
            if mx > bx + left_w:
                clicked_pane = 1

        row = my - by
        if row >= self._header_lines():
            if clicked_pane == 0:
                self.active_pane = 0
                new_idx = self.scroll_offset + (row - self._header_lines())
                if 0 <= new_idx < len(self.entries):
                    self.selected_index = new_idx
            else:
                 self.active_pane = 1
                 new_idx = self.secondary_scroll_offset + (row - self._header_lines())
                 if 0 <= new_idx < len(self.secondary_entries):
                     self.secondary_selected_index = new_idx

        entry = self.selected_entry_for_operation()
        
        items = []
        if entry:
             if entry.name != '..':
                 items.append({'label': 'Open', 'action': AppAction.FM_OPEN})
                 items.append({'separator': True})
                 items.append({'label': 'Copy', 'action': AppAction.FM_COPY})
                 items.append({'label': 'Move', 'action': AppAction.FM_MOVE})
                 items.append({'label': 'Rename', 'action': AppAction.FM_RENAME})
                 items.append({'separator': True})
                 items.append({'label': 'Delete', 'action': AppAction.FM_DELETE})
             else:
                 items.append({'label': 'Up', 'action': AppAction.FM_PARENT})
        
        items.append({'separator': True})
        items.append({'label': 'New Folder', 'action': AppAction.FM_NEW_DIR})
        items.append({'label': 'New File', 'action': AppAction.FM_NEW_FILE})
        items.append({'separator': True})
        items.append({'label': 'Refresh', 'action': AppAction.FM_REFRESH})
        items.append({'label': 'Hidden Files', 'action': AppAction.FM_TOGGLE_HIDDEN})

        return items

    def _handle_pane_navigation(self, key):
        """Handle arrow/page/home/end navigation for the active pane."""
        if self.active_pane == 1:
            entries = self.secondary_entries
            selected = self.secondary_selected_index
            scroll = self.secondary_scroll_offset
        else:
            entries = self.entries
            selected = self.selected_index
            scroll = self.scroll_offset

        count = len(entries)
        if count == 0:
            return None

        new_selected = selected
        new_scroll = scroll

        if key == curses.KEY_UP:
            if selected > 0:
                new_selected = selected - 1
                if new_selected < scroll:
                    new_scroll = new_selected
        elif key == curses.KEY_DOWN:
            if selected < count - 1:
                new_selected = selected + 1
                display_h = self.h - self._header_lines() - 1
                if new_selected >= scroll + display_h:
                    new_scroll = scroll + 1
        elif key == curses.KEY_PPAGE:
            new_selected = max(0, selected - self.PAGE_SCROLL_STEP)
            new_scroll = max(0, scroll - self.PAGE_SCROLL_STEP)
        elif key == curses.KEY_NPAGE:
            new_selected = min(count - 1, selected + self.PAGE_SCROLL_STEP)
            new_scroll = min(max(0, count - 1), scroll + self.PAGE_SCROLL_STEP)
        elif key == curses.KEY_HOME:
            new_selected = 0
            new_scroll = 0
        elif key == curses.KEY_END:
            new_selected = count - 1
            new_scroll = max(0, count - self.PAGE_SCROLL_STEP)
        else:
            return None  # Not a navigation key

        # Write back to the appropriate pane
        if self.active_pane == 1:
            self.secondary_selected_index = new_selected
            self.secondary_scroll_offset = new_scroll
        else:
            self.selected_index = new_selected
            self.scroll_offset = new_scroll

        return ActionResult(ActionType.REFRESH)

    def _handle_letter_shortcut(self, norm_key):
        """Handle single-letter keyboard shortcuts."""
        _LETTER_ACTIONS = {
            ord('h'): AppAction.FM_TOGGLE_HIDDEN,
            ord('H'): AppAction.FM_TOGGLE_HIDDEN,
            ord('u'): AppAction.FM_UNDO_DELETE,
            ord('U'): AppAction.FM_UNDO_DELETE,
        }
        action = _LETTER_ACTIONS.get(norm_key)
        if action is not None:
            return self.execute_action(action)
        if norm_key in (ord('d'), ord('D')):
            return self.toggle_dual_pane()
        return None

    def _handle_fkey(self, key):
        """Handle function key shortcuts. Returns ActionResult or None."""
        if key == self.KEY_F5:
            if self.dual_pane_enabled:
                return self._dual_copy_move_between_panes(move=False)
            return self.execute_action(AppAction.FM_COPY)
        if key == self.KEY_F4:
            if self.dual_pane_enabled:
                return self._dual_copy_move_between_panes(move=True)
            return self.execute_action(AppAction.FM_MOVE)
        # Simple F-key -> action mapping
        _simple_fkeys = {
            self.KEY_F2: AppAction.FM_RENAME,
            self.KEY_F6: AppAction.FM_MOVE,
            self.KEY_F7: AppAction.FM_NEW_DIR,
            self.KEY_F8: AppAction.FM_NEW_FILE,
        }
        action = _simple_fkeys.get(key)
        if action is not None:
            return self.execute_action(action)
        if key == self.KEY_INSERT:
            return ActionResult(ActionType.EXECUTE, AppAction.FM_TOGGLE_SELECT)
        return None

    def handle_key(self, key):
        key_code = normalize_key_code(key)


        # Window menu keyboard handling
        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self.execute_action(action)
            return None

        # Navigation keys (unified for both panes)
        nav_result = self._handle_pane_navigation(key)
        if nav_result is not None:
            return nav_result

        # Shared keys and actions
        if key == 10: # Enter
            return self.activate_selected()
        elif key == 9: # Tab
            return self.handle_tab_key()

        fkey_result = self._handle_fkey(key)
        if fkey_result is not None:
            return fkey_result

        norm_key = normalize_key_code(key)

        # Shortcuts for specific letters (case-insensitive via ASCII values)
        letter_result = self._handle_letter_shortcut(norm_key)
        if letter_result is not None:
            return letter_result

        # Backspace handling
        if norm_key in (127, 8):
            self.navigate_parent()
            return ActionResult(ActionType.REFRESH)

        return super().handle_key(key)

    def _action_refresh(self):
        self._rebuild_content()
        return ActionResult(ActionType.REFRESH)

    def _action_parent(self):
        self.navigate_parent()
        return ActionResult(ActionType.REFRESH)

    def execute_action(self, action):
        """Execute a window menu action via dispatch table."""
        handler = self._MENU_ACTION_MAP.get(action)
        if handler is None:
            return None
        if isinstance(handler, str):
            return getattr(self, handler)()
        return handler(self)

    def handle_tab_key(self):
        """Handle Tab key for pane switching (active window hook)."""
        return self._handle_tab_switch()

    def _handle_tab_switch(self):
        """Internal tab handling logic."""
        if self.dual_pane_enabled:
            self.active_pane = 1 - self.active_pane
            return ActionResult(ActionType.REFRESH)
        return None

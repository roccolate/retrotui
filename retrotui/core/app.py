"""
Main RetroTUI Application Class.
"""
import os
import logging
import threading
import time

from ..constants import (
    ICONS, ICONS_ASCII
)
from ..utils import (
    check_unicode_support, init_colors,
    is_video_file, play_ascii_video
)
from ..theme import get_theme
from ..ui.menu import Menu
from ..ui.dialog import Dialog, InputDialog, ProgressDialog
from ..ui.window import Window
from ..apps.notepad import NotepadWindow
from ..apps.logviewer import LogViewerWindow
from ..apps.image_viewer import ImageViewerWindow
from ..apps.hexviewer import HexViewerWindow
from .config import AppConfig, load_config, save_config
from .actions import ActionResult, ActionType, AppAction
from .action_runner import execute_app_action
from .content import build_welcome_content
from .mouse_router import (
    _invoke_mouse_handler,
    handle_drag_resize_mouse,
    handle_global_menu_mouse,
    handle_window_mouse,
    handle_desktop_mouse,
    handle_mouse_event,
)
from pathlib import Path
from .config import default_config_path
from .key_router import (
    normalize_app_key,
    handle_menu_hotkeys,
    handle_global_menu_key,
    cycle_focus,
    handle_active_window_key,
    handle_key_event,
)
from .rendering import (
    draw_desktop,
    draw_icons,
    draw_taskbar,
    draw_statusbar,
)
from .event_loop import run_app_loop
from .bootstrap import (
    configure_terminal,
    disable_flow_control,
    enable_mouse_support,
    disable_mouse_support,
)

LOGGER = logging.getLogger(__name__)

APP_VERSION = '0.9.0'

class RetroTUI:
    """Main application class."""
    MIN_TERM_WIDTH = 80
    MIN_TERM_HEIGHT = 24
    LONG_FILE_OPERATION_BYTES = 8 * 1024 * 1024
    BACKGROUND_OPERATION_JOIN_TIMEOUT = 5.0

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.running = True
        self.windows = []
        self.menu = Menu()
        self.context_menu = None
        self.dialog = None
        self.selected_icon = -1
        self.use_unicode = check_unicode_support()
        self.icons = ICONS if self.use_unicode else ICONS_ASCII

        self.config = load_config()
        self.theme_name = self.config.theme
        self.theme = get_theme(self.theme_name)
        self.default_show_hidden = bool(self.config.show_hidden)
        self.default_word_wrap = bool(self.config.word_wrap_default)
        self.default_sunday_first = bool(self.config.sunday_first)
        self.show_welcome = bool(self.config.show_welcome)
        self.drag_payload = None
        self.drag_source_window = None
        self.drag_target_window = None
        # Movable desktop icon positions: mapping icon_key -> (x, y)
        self.icon_positions = {}
        self._background_operation = None

        # Setup terminal
        configure_terminal(stdscr, timeout_ms=500)
        self._validate_terminal_size()

        disable_flow_control()
        self.click_flags, self.stop_drag_flags, self.scroll_down_mask = enable_mouse_support()
        self.button1_pressed = False  # Track physical button state for TTY drags

        init_colors(self.theme)

        # Create a welcome window if enabled
        if self.show_welcome:
            h, w = stdscr.getmaxyx()
            welcome_content = build_welcome_content(APP_VERSION)
            win = Window('Welcome to RetroTUI', w // 2 - 25, h // 2 - 10, 52, 22,
                          content=welcome_content)
            
            # Custom handler to process "Don't show again"
            def _welcome_handle_key(key):
                if getattr(curses, "KEY_F9", -1) == key or key == "KEY_F9":
                    self.show_welcome = False
                    self.persist_config()
                    self.close_window(win)
                    return ActionResult(ActionType.REFRESH)
                return Window.handle_key(win, key)

            win.handle_key = _welcome_handle_key
            win.active = True
            self.windows.append(win)
        # load persisted icon positions (if any)
        try:
            self._load_icon_positions()
        except Exception:
            # don't fail startup on parse errors
            LOGGER.debug('failed to load icon positions', exc_info=True)

    def apply_theme(self, theme_name):
        """Apply a theme immediately to current runtime."""
        self.theme = get_theme(theme_name)
        self.theme_name = self.theme.key
        init_colors(self.theme)

    def apply_preferences(self, *, show_hidden=None, word_wrap_default=None, sunday_first=None, apply_to_open_windows=False):
        """Apply runtime preferences used by app windows and defaults."""
        if show_hidden is not None:
            self.default_show_hidden = bool(show_hidden)
        if word_wrap_default is not None:
            self.default_word_wrap = bool(word_wrap_default)
        if sunday_first is not None:
            self.default_sunday_first = bool(sunday_first)

        if not apply_to_open_windows:
            return

        for win in list(self.windows):
            if hasattr(win, 'show_hidden') and hasattr(win, '_rebuild_content'):
                if win.show_hidden != self.default_show_hidden:
                    win.show_hidden = self.default_show_hidden
                    win._rebuild_content()
            if hasattr(win, 'wrap_mode') and hasattr(win, '_invalidate_wrap'):
                if win.wrap_mode != self.default_word_wrap:
                    win.wrap_mode = self.default_word_wrap
                    win.view_left = 0
                    win._invalidate_wrap()
                    ensure_visible = getattr(win, '_ensure_cursor_visible', None)
                    if callable(ensure_visible):
                        ensure_visible()

    def persist_config(self):
        """Persist current runtime preferences to ~/.config/retrotui/config.toml."""
        # Sync back clock preferences from any open Clock window
        from ..apps.clock import ClockCalendarWindow
        for win in self.windows:
            if isinstance(win, ClockCalendarWindow):
                self.default_sunday_first = win.week_starts_sunday
                break
        self.config = AppConfig(
            theme=self.theme_name,
            show_hidden=self.default_show_hidden,
            word_wrap_default=self.default_word_wrap,
            sunday_first=self.default_sunday_first,
            show_welcome=self.show_welcome,
        )
        path = save_config(self.config)
        try:
            self._save_icon_positions(path)
        except Exception:
            LOGGER.debug('failed to save icon positions', exc_info=True)
        return path

    def _load_icon_positions(self):
        """Load icon positions from config TOML under [icons]."""
        cfg_path = default_config_path()
        if not Path(cfg_path).exists():
            return {}
        text = Path(cfg_path).read_text(encoding='utf-8')
        section = None
        icons = {}
        for raw in text.splitlines():
            line = raw.split('#', 1)[0].strip()
            if not line:
                continue
            if line.startswith('[') and line.endswith(']'):
                section = line[1:-1].strip()
                continue
            if section != 'icons':
                continue
            if '=' not in line:
                continue
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            try:
                x_str, y_str = val.split(',')
                icons[key] = (int(x_str.strip()), int(y_str.strip()))
            except Exception:
                continue
        self.icon_positions = icons
        return icons

    def _save_icon_positions(self, cfg_path=None):
        """Save icon positions into the config TOML under [icons], preserving other sections."""
        cfg_path = Path(cfg_path) if cfg_path is not None else Path(default_config_path())
        existing = ''
        if cfg_path.exists():
            existing = cfg_path.read_text(encoding='utf-8')

        # Remove any existing [icons] section
        lines = existing.splitlines()
        out_lines = []
        skip = False
        for raw in lines:
            line = raw.strip()
            if line.startswith('[') and line.endswith(']'):
                sect = line[1:-1].strip()
                if sect == 'icons':
                    skip = True
                    continue
                else:
                    skip = False
            if skip:
                continue
            out_lines.append(raw)

        # Append icons section
        out_lines.append('')
        out_lines.append('[icons]')
        for name, (x, y) in sorted(self.icon_positions.items()):
            out_lines.append(f'{name} = "{x},{y}"')

        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text('\n'.join(out_lines) + '\n', encoding='utf-8', newline='\n')

    def handle_right_click(self, mx, my, bstate):
        """Dispatch right-clicks to windows or desktop. Return True if handled."""
        # Check if right-click is on an existing context menu (unlikely but safe)
        if self.context_menu and self.context_menu.active:
            # Let the menu handle it or close? Usually clicking outside closes it.
            pass

        # Try windows first (topmost)
        for win in reversed(self.windows):
            if not getattr(win, 'visible', False):
                continue
            contains = getattr(win, 'contains', None)
            if not callable(contains) or not contains(mx, my):
                continue
            
            # Convert screen coordinates to window-relative for the handler
            # But handle_right_click usually expects screen coords in RetroTUI pattern?
            # Let's pass screen coords and let window decide.
            handler = getattr(win, 'handle_right_click', None)
            if callable(handler):
                try:
                    res = _invoke_mouse_handler(handler, mx, my, bstate)
                except Exception:
                    res = None
                
                # If window handled it (returned True or ActionResult), we stop.
                if isinstance(res, list):
                     from ..ui.context_menu import ContextMenu
                     self.context_menu = ContextMenu(self.theme)
                     self.context_menu.show(mx, my, res)
                     return True
                
                if res:
                    self._dispatch_window_result(res, win)
                    return True

        # Desktop hook
        try:
            return bool(self._handle_desktop_right_click(mx, my, bstate))
        except Exception:
            return False

    def _handle_desktop_right_click(self, mx, my, bstate):
        """Open a desktop context menu or icon-specific menu at (mx,my)."""
        icon_idx = self.get_icon_at(mx, my)
        from ..ui.context_menu import ContextMenu

        if icon_idx >= 0:
            # Icon menu
            # Select the icon first
            self.selected_icon = icon_idx
            
            items = [
                {'label': 'Open', 'action': self.icons[icon_idx].get('action')},
                {'separator': True},
                {'label': 'Properties', 'action': None}, # Placeholder
            ]
        else:
            # Desktop menu
            items = [
                {'label': 'New Terminal', 'action': AppAction.TERMINAL},
                {'label': 'New Notepad', 'action': AppAction.NOTEPAD},
                {'separator': True},
                {'label': 'Theme', 'action': AppAction.SETTINGS},
                {'label': 'Settings', 'action': AppAction.SETTINGS},
                {'separator': True},
                {'label': 'About', 'action': AppAction.ABOUT},
                {'label': 'Exit', 'action': AppAction.EXIT},
            ]

        self.context_menu = ContextMenu(self.theme)
        self.context_menu.show(mx, my, items)
        return True

    def _validate_terminal_size(self):
        """Fail fast when terminal is too small for the base desktop layout."""
        h, w = self.stdscr.getmaxyx()
        if h < self.MIN_TERM_HEIGHT or w < self.MIN_TERM_WIDTH:
            raise ValueError(
                f'Terminal too small ({w}x{h}). '
                f'Minimum supported size is {self.MIN_TERM_WIDTH}x{self.MIN_TERM_HEIGHT}.'
            )

    def cleanup(self):
        """Restore terminal state."""
        op_state = getattr(self, '_background_operation', None)
        if op_state:
            thread = op_state.get('thread')
            if thread and thread.is_alive():
                thread.join(timeout=self.BACKGROUND_OPERATION_JOIN_TIMEOUT)
                if thread.is_alive():
                    LOGGER.warning(
                        'Background operation did not finish within %.1fs during shutdown.',
                        self.BACKGROUND_OPERATION_JOIN_TIMEOUT,
                    )
        for win in list(self.windows):
            closer = getattr(win, 'close', None)
            if callable(closer):
                try:
                    closer()
                except Exception:  # pragma: no cover - defensive cleanup path
                    LOGGER.debug('Window cleanup failed for %r', win, exc_info=True)
        disable_mouse_support()

    def draw_desktop(self):
        """Draw the desktop background pattern."""
        return draw_desktop(self)

    def draw_icons(self):
        """Draw desktop icons (3x4 art + label)."""
        return draw_icons(self)

    def draw_taskbar(self):
        """Draw taskbar row with minimized window buttons."""
        return draw_taskbar(self)

    def draw_statusbar(self):
        """Draw the bottom status bar."""
        return draw_statusbar(self, APP_VERSION)

    def get_icon_screen_pos(self, index):
        """Return (x, y) for icon at index, checking persisted positions then default grid."""
        if not (0 <= index < len(self.icons)):
             return (0, 0)
        
        KEY_LABEL = self.icons[index].get('label')
        if KEY_LABEL in self.icon_positions:
            return self.icon_positions[KEY_LABEL]
            
        # Default vertical layout
        start_x = 3
        start_y = 3
        spacing_y = 5
        return (start_x, start_y + index * spacing_y)

    def get_icon_at(self, mx, my):
        """Return icon index at mouse position, or -1."""
        for i, icon in enumerate(self.icons):
            x, y = self.get_icon_screen_pos(i)
            # Dimensions from draw_icons: 3x4 art? 
            # Actually standard ascii art is usually 3-4 lines high.
            # Let's assume a bounding box. 
            # In draw_icons (rendering.py), it usually takes ~5 lines height (art+label) and some width.
            # Let's approximate 8 width x 4 height based on standard ascii icons.
            # Or better, check the actual art width.
            art = icon.get('art', [])
            w = max(len(line) for line in art) if art else 8
            h = len(art) + 1 # +1 for label
            
            if y <= my < y + h and x <= mx < x + w:
                return i
        return -1

    def set_active_window(self, win):
        """Set a window as active (bring to front)."""
        for w in self.windows:
            w.active = False
        win.active = True
        # Move to top of its layer.
        self.windows.remove(win)
        self.normalize_window_layers()
        if getattr(win, 'always_on_top', False):
            self.windows.append(win)
            return

        insert_at = len(self.windows)
        for i, candidate in enumerate(self.windows):
            if getattr(candidate, 'always_on_top', False):
                insert_at = i
                break
        self.windows.insert(insert_at, win)

    def normalize_window_layers(self):
        """Keep always-on-top windows above regular windows preserving order."""
        normal = [w for w in self.windows if not getattr(w, 'always_on_top', False)]
        pinned = [w for w in self.windows if getattr(w, 'always_on_top', False)]
        self.windows = normal + pinned

    def close_window(self, win):
        """Close a window."""
        closer = getattr(win, 'close', None)
        if callable(closer):
            try:
                closer()
            except Exception:  # pragma: no cover - defensive window cleanup path
                LOGGER.debug('Window close hook failed for %r', win, exc_info=True)
        self.windows.remove(win)
        self._activate_last_visible_window()

    def _activate_last_visible_window(self):
        """Activate topmost visible window after z-order/window-list changes."""
        for candidate in self.windows:
            candidate.active = False
        for candidate in reversed(self.windows):
            if getattr(candidate, 'visible', True):
                candidate.active = True
                return candidate
        return None

    @staticmethod
    def _normalize_action(action):
        """Convert legacy string actions to AppAction when possible."""
        if isinstance(action, AppAction):
            return action
        if isinstance(action, str):
            try:
                return AppAction(action)
            except ValueError:
                return action
        return action

    def _spawn_window(self, win):
        """Append a window and make it active."""
        self.windows.append(win)
        self.set_active_window(win)

    def _next_window_offset(self, base_x, base_y, step_x=2, step_y=1):
        """Return staggered window coordinates based on open window count."""
        count = len(self.windows)
        return base_x + count * step_x, base_y + count * step_y

    def execute_action(self, action):
        """Execute a menu/icon action."""
        action = self._normalize_action(action)
        LOGGER.debug('execute_action: %s', action)
        execute_app_action(self, action, LOGGER, version=APP_VERSION)

    def open_file_viewer(self, filepath):
        """Open file in best viewer: ASCII video or Notepad."""
        h, w = self.stdscr.getmaxyx()
        lower_path = filepath.lower()

        if is_video_file(filepath):
            self._play_ascii_video(filepath)
            return

        if (
            lower_path.endswith(('.log', '.out', '.err'))
            or '/log/' in lower_path
            or '\\log\\' in lower_path
        ):
            offset_x = 16 + len(self.windows) * 2
            offset_y = 4 + len(self.windows)
            win_w = min(74, w - 4)
            win_h = min(22, h - 4)
            win = LogViewerWindow(offset_x, offset_y, win_w, win_h, filepath=filepath)
            self._spawn_window(win)
            return

        image_ext = os.path.splitext(lower_path)[1]
        if image_ext in ImageViewerWindow.IMAGE_EXTENSIONS:
            offset_x = 14 + len(self.windows) * 2
            offset_y = 3 + len(self.windows)
            win_w = min(84, w - 4)
            win_h = min(26, h - 4)
            win = ImageViewerWindow(offset_x, offset_y, win_w, win_h, filepath=filepath)
            self._spawn_window(win)
            return

        # Check if file seems to be binary
        try:
            with open(filepath, 'rb') as f:
                chunk = f.read(1024)
                if b'\x00' in chunk:
                    offset_x = 12 + len(self.windows) * 2
                    offset_y = 3 + len(self.windows)
                    win_w = min(92, w - 4)
                    win_h = min(26, h - 4)
                    win = HexViewerWindow(offset_x, offset_y, win_w, win_h, filepath=filepath)
                    self._spawn_window(win)
                    return
        except OSError:
            pass

        # Create NotepadWindow with file
        offset_x = 18 + len(self.windows) * 2
        offset_y = 3 + len(self.windows)
        win_w = min(70, w - 4)
        win_h = min(25, h - 4)
        win = NotepadWindow(
            offset_x,
            offset_y,
            win_w,
            win_h,
            filepath=filepath,
            wrap_default=getattr(self, 'default_word_wrap', False),
        )
        self._spawn_window(win)

    def _play_ascii_video(self, filepath, subtitle_path=None):
        """Run ASCII video playback and surface backend errors in a dialog."""
        success, error = play_ascii_video(self.stdscr, filepath, subtitle_path=subtitle_path)
        if not success:
            self.dialog = Dialog('ASCII Video Error', error, ['OK'], width=58)

    def show_video_open_dialog(self):
        """Open dialog flow to play a video path without using File Manager."""
        dialog = InputDialog('Open Video', 'Enter video path:', width=64)
        dialog.callback = self._handle_video_path_input
        self.dialog = dialog

    def _handle_video_path_input(self, filepath):
        """Validate selected video path and request optional subtitle path."""
        raw_path = str(filepath or '').strip()
        if not raw_path:
            return ActionResult(ActionType.ERROR, 'Video path cannot be empty.')
        video_path = os.path.abspath(os.path.expanduser(raw_path))
        if not os.path.isfile(video_path):
            return ActionResult(ActionType.ERROR, f'Video file not found:\n{video_path}')
        if not is_video_file(video_path):
            return ActionResult(ActionType.ERROR, f'Unsupported video format:\n{video_path}')

        dialog = InputDialog(
            'Subtitles (Optional)',
            'Enter subtitle path (.srt/.ass/.vtt) or leave empty:',
            width=70,
        )
        dialog.callback = (
            lambda subtitle_path, selected_video=video_path: self._handle_subtitle_path_input(
                selected_video,
                subtitle_path,
            )
        )
        self.dialog = dialog
        return None

    def _handle_subtitle_path_input(self, video_path, subtitle_path):
        """Validate optional subtitle path and start playback."""
        subtitle = str(subtitle_path or '').strip()
        if subtitle:
            subtitle = os.path.abspath(os.path.expanduser(subtitle))
            if not os.path.isfile(subtitle):
                return ActionResult(ActionType.ERROR, f'Subtitle file not found:\n{subtitle}')
        else:
            subtitle = None
        self._play_ascii_video(video_path, subtitle_path=subtitle)
        return None

    def show_save_as_dialog(self, win):
        """Show dialog to get filename for saving."""
        dialog = InputDialog('Save As', 'Enter filename:', width=40)
        dialog.callback = lambda filename, target=win: target.save_as(filename)
        self.dialog = dialog

    def show_open_dialog(self, win):
        """Show dialog to get filename/path for opening in current window."""
        dialog = InputDialog('Open File', 'Enter filename/path:', width=52)
        dialog.callback = lambda filepath, target=win: target.open_path(filepath)
        self.dialog = dialog

    def show_rename_dialog(self, win):
        """Show dialog to rename selected File Manager entry."""
        entry = getattr(win, '_selected_entry', lambda: None)()
        if entry is None:
            self.dialog = Dialog('Rename Error', 'No item selected.', ['OK'], width=44)
            return
        if entry.name == '..':
            self.dialog = Dialog('Rename Error', 'Cannot rename parent entry.', ['OK'], width=44)
            return

        prompt = f"Rename:\n{entry.name}"
        dialog = InputDialog('Rename', prompt, initial_value=entry.name, width=56)
        dialog.callback = lambda new_name, target=win: target.rename_selected(new_name)
        self.dialog = dialog

    def show_delete_confirm_dialog(self, win):
        """Show confirmation dialog before deleting selected File Manager entry."""
        entry = self._window_selected_entry(win)
        if entry is None:
            self.dialog = Dialog('Delete Error', 'No item selected.', ['OK'], width=44)
            return
        if entry.name == '..':
            self.dialog = Dialog('Delete Error', 'Cannot delete parent entry.', ['OK'], width=44)
            return

        kind = 'directory' if entry.is_dir else 'file'
        message = (
            f"Delete {kind}:\n{entry.name}\n\n"
            "Item will be moved to Trash.\n"
            "Use Undo Delete (U) to restore."
        )
        dialog = Dialog('Confirm Delete', message, ['Delete', 'Cancel'], width=58)
        dialog.callback = lambda target=win: self._run_file_operation_with_progress(
            target,
            operation='delete',
        )
        self.dialog = dialog

    def show_copy_dialog(self, win):
        """Show destination input for copy operation in File Manager."""
        entry = self._window_selected_entry(win)
        if entry is None or entry.name == '..':
            self.dialog = Dialog('Copy Error', 'Select a valid item to copy.', ['OK'], width=48)
            return

        prompt = f"Copy:\n{entry.name}\n\nDestination path:"
        dialog = InputDialog('Copy To', prompt, initial_value=win.current_path, width=62)
        dialog.callback = lambda dest, target=win: self._run_file_operation_with_progress(
            target,
            operation='copy',
            destination=dest,
        )
        self.dialog = dialog

    def show_move_dialog(self, win):
        """Show destination input for move operation in File Manager."""
        entry = self._window_selected_entry(win)
        if entry is None or entry.name == '..':
            self.dialog = Dialog('Move Error', 'Select a valid item to move.', ['OK'], width=48)
            return

        prompt = f"Move:\n{entry.name}\n\nDestination path:"
        dialog = InputDialog('Move To', prompt, initial_value=win.current_path, width=62)
        dialog.callback = lambda dest, target=win: self._run_file_operation_with_progress(
            target,
            operation='move',
            destination=dest,
        )
        self.dialog = dialog

    def show_new_dir_dialog(self, win):
        """Show input dialog to create a new directory in current path."""
        dialog = InputDialog('New Folder', 'Enter folder name:', width=52)
        dialog.callback = lambda name, target=win: target.create_directory(name)
        self.dialog = dialog

    def show_new_file_dialog(self, win):
        """Show input dialog to create a new file in current path."""
        dialog = InputDialog('New File', 'Enter file name:', width=52)
        dialog.callback = lambda name, target=win: target.create_file(name)
        self.dialog = dialog

    def show_kill_confirm_dialog(self, win, payload):
        """Show confirmation dialog before sending signal to a process."""
        data = payload or {}
        pid = data.get('pid')
        command = data.get('command', '')
        if not pid:
            self.dialog = Dialog('Kill Error', 'No process selected.', ['OK'], width=44)
            return

        title = 'Confirm Kill'
        message = (
            f"Kill process PID {pid}?\n"
            f"{command[:40]}\n\n"
            "Signal: SIGTERM (15)"
        )
        dialog = Dialog(title, message, ['Kill', 'Cancel'], width=58)
        dialog.callback = (
            lambda target=win, data=data: target.kill_process(data)
            if callable(getattr(target, 'kill_process', None))
            else ActionResult(ActionType.ERROR, 'Window does not support process kill.')
        )
        self.dialog = dialog

    @staticmethod
    def _window_selected_entry(win):
        """Resolve selected entry accessor from supported window APIs."""
        selector = getattr(win, 'selected_entry_for_operation', None)
        if callable(selector):
            return selector()
        selector = getattr(win, '_selected_entry', None)
        if callable(selector):
            return selector()
        return None

    @staticmethod
    def _resolve_between_panes_destination(win, payload):
        """Resolve destination path for copy/move between panes requests."""
        if isinstance(payload, dict):
            destination = str(payload.get('destination') or '').strip()
            if destination:
                return destination

        if not win or not getattr(win, 'dual_pane_enabled', False):
            return None
        active_pane = int(getattr(win, 'active_pane', 0) or 0)
        if active_pane == 0:
            return getattr(win, 'secondary_path', None)
        return getattr(win, 'current_path', None)

    def _is_long_file_operation(self, entry):
        """Return True when operation should show a modal progress dialog."""
        if entry is None or getattr(entry, 'name', None) == '..':
            return False
        if getattr(entry, 'is_dir', False):
            return True

        size = getattr(entry, 'size', None)
        if size is None:
            full_path = getattr(entry, 'full_path', None)
            if not full_path:
                return False
            try:
                size = os.path.getsize(full_path)
            except OSError:
                return False
        return int(size) >= self.LONG_FILE_OPERATION_BYTES

    def _start_background_operation(self, *, title, message, worker, source_win):
        """Run blocking filesystem operation in a worker thread and show progress."""
        state = getattr(self, '_background_operation', None)
        if state:
            return ActionResult(ActionType.ERROR, 'Another operation is already running.')

        progress_dialog = ProgressDialog(title, message, width=62)
        op_state = {
            'dialog': progress_dialog,
            'source_win': source_win,
            'worker_result': None,
            'done': False,
            'started_at': time.monotonic(),
            'thread': None,
        }

        def _runner():
            try:
                op_state['worker_result'] = worker()
            except Exception as exc:  # pragma: no cover - defensive worker path
                op_state['worker_result'] = ActionResult(ActionType.ERROR, str(exc))
            finally:
                op_state['done'] = True

        thread = threading.Thread(target=_runner, name='retrotui-file-op')
        op_state['thread'] = thread
        self._background_operation = op_state
        self.dialog = progress_dialog
        thread.start()
        return None

    def has_background_operation(self):
        """Return whether a background file operation is currently running."""
        return bool(getattr(self, '_background_operation', None))

    def poll_background_operation(self):
        """Advance progress state and dispatch completion when worker finishes."""
        state = getattr(self, '_background_operation', None)
        if not state:
            return

        elapsed = max(0.0, time.monotonic() - state['started_at'])
        dialog = state.get('dialog')
        if dialog and hasattr(dialog, 'set_elapsed'):
            dialog.set_elapsed(elapsed)

        if not state.get('done'):
            return

        if self.dialog is dialog:
            self.dialog = None

        self._background_operation = None
        result = state.get('worker_result')
        if result is not None:
            self._dispatch_window_result(result, state.get('source_win'))

    def _run_file_operation_with_progress(self, win, *, operation, destination=None):
        """Run file operation directly or via background worker with progress dialog."""
        entry = self._window_selected_entry(win)
        operation = str(operation).lower()

        if operation == 'copy':
            worker = lambda target=win, dest=destination: target.copy_selected(dest)
            title = 'Copying'
            details = f"Copying:\n{getattr(entry, 'name', 'item')}"
        elif operation == 'move':
            worker = lambda target=win, dest=destination: target.move_selected(dest)
            title = 'Moving'
            details = f"Moving:\n{getattr(entry, 'name', 'item')}"
        elif operation == 'delete':
            worker = lambda target=win: target.delete_selected()
            title = 'Deleting'
            details = f"Deleting:\n{getattr(entry, 'name', 'item')}"
        else:
            return ActionResult(ActionType.ERROR, f'Unsupported file operation: {operation}')

        if not self._is_long_file_operation(entry):
            return worker()

        message = f'{details}\n\nPlease wait...'
        return self._start_background_operation(
            title=title,
            message=message,
            worker=worker,
            source_win=win,
        )

    def get_active_window(self):
        """Return the active window, if any."""
        return next((w for w in self.windows if w.active), None)

    def _dispatch_window_result(self, result, source_win):
        """Handle ActionResult returned by window/dialog callbacks."""
        if not result or result is True:
            return

        if not isinstance(result, ActionResult):
            LOGGER.debug('Ignoring non-ActionResult return from window callback: %r', result)
            return

        LOGGER.debug('Dispatching window result: type=%s payload=%r', result.type, result.payload)

        if result.type == ActionType.OPEN_FILE and result.payload:
            self.open_file_viewer(result.payload)
            return

        if result.type == ActionType.EXECUTE:
            exec_action = self._normalize_action(result.payload)
            if exec_action == AppAction.CLOSE_WINDOW and source_win:
                self.close_window(source_win)
            elif exec_action:
                self.execute_action(exec_action)
            return

        if result.type == ActionType.REQUEST_SAVE_AS and source_win:
            self.show_save_as_dialog(source_win)
            return

        if result.type == ActionType.REQUEST_OPEN_PATH and source_win:
            self.show_open_dialog(source_win)
            return

        if result.type == ActionType.REQUEST_RENAME_ENTRY and source_win:
            self.show_rename_dialog(source_win)
            return

        if result.type == ActionType.REQUEST_DELETE_CONFIRM and source_win:
            self.show_delete_confirm_dialog(source_win)
            return

        if result.type == ActionType.REQUEST_COPY_ENTRY and source_win:
            self.show_copy_dialog(source_win)
            return

        if result.type == ActionType.REQUEST_MOVE_ENTRY and source_win:
            self.show_move_dialog(source_win)
            return

        if result.type in (
            ActionType.REQUEST_COPY_BETWEEN_PANES,
            ActionType.REQUEST_MOVE_BETWEEN_PANES,
        ):
            operation = (
                'copy'
                if result.type == ActionType.REQUEST_COPY_BETWEEN_PANES
                else 'move'
            )
            destination = self._resolve_between_panes_destination(source_win, result.payload)
            if not source_win:
                self.dialog = Dialog(
                    'Operation Error',
                    f'Cannot {operation}: no source window context.',
                    ['OK'],
                    width=54,
                )
                return
            if not destination:
                self.dialog = Dialog(
                    'Operation Error',
                    f'Cannot {operation}: destination pane path is unavailable.',
                    ['OK'],
                    width=62,
                )
                return
            op_result = self._run_file_operation_with_progress(
                source_win,
                operation=operation,
                destination=destination,
            )
            if op_result is not None:
                self._dispatch_window_result(op_result, source_win)
            return

        if result.type == ActionType.REQUEST_NEW_DIR and source_win:
            self.show_new_dir_dialog(source_win)
            return

        if result.type == ActionType.REQUEST_NEW_FILE and source_win:
            self.show_new_file_dialog(source_win)
            return

        if result.type == ActionType.REQUEST_KILL_CONFIRM and source_win:
            self.show_kill_confirm_dialog(source_win, result.payload)
            return

        if result.type == ActionType.SAVE_ERROR:
            message = result.payload or 'Unknown save error.'
            self.dialog = Dialog('Save Error', str(message), ['OK'], width=50)
            return

        if result.type == ActionType.ERROR:
            message = result.payload or 'Unknown error.'
            self.dialog = Dialog('Error', str(message), ['OK'], width=50)
            return

        if result.type == ActionType.UPDATE_CONFIG:
            payload = result.payload or {}
            self.apply_preferences(**payload, apply_to_open_windows=False)
            self.persist_config()
            return

        LOGGER.debug('Unhandled ActionResult type: %s', result.type)

    def _resolve_dialog_result(self, result_idx):
        """Apply dialog button result and run dialog callback when needed."""
        if result_idx < 0 or not self.dialog:
            return

        dialog = self.dialog
        btn_text = dialog.buttons[result_idx] if result_idx < len(dialog.buttons) else ''
        callback_result = None

        if dialog.title == 'Exit RetroTUI' and btn_text == 'Yes':
            self.running = False
        elif result_idx == 0:
            callback = getattr(dialog, 'callback', None)
            if callable(callback):
                if isinstance(dialog, InputDialog):
                    callback_result = callback(dialog.value)
                else:
                    callback_result = callback()

        if self.dialog is dialog:
            self.dialog = None
        if callback_result is not None:
            self._dispatch_window_result(callback_result, self.get_active_window())

    def _handle_dialog_mouse(self, mx, my, bstate):
        """Handle mouse events when a modal dialog is open."""
        if not self.dialog:
            return False
        if not (bstate & self.click_flags):
            return True
        result = self.dialog.handle_click(mx, my)
        self._resolve_dialog_result(result)
        return True

    def _handle_dialog_key(self, key):
        """Handle keyboard events when a modal dialog is open."""
        if not self.dialog:
            return False
        result = self.dialog.handle_key(key)
        self._resolve_dialog_result(result)
        return True

    def handle_taskbar_click(self, mx, my):
        """Handle click on taskbar row. Returns True if handled."""
        h, w = self.stdscr.getmaxyx()
        taskbar_y = h - 2
        if my != taskbar_y:
            return False
        minimized = [win for win in self.windows if win.minimized]
        if not minimized:
            return False
        x = 1
        for win in minimized:
            label = win.title[:15]
            btn_w = len(label) + 2  # [label]
            if x <= mx < x + btn_w:
                win.toggle_minimize()
                self.set_active_window(win)
                return True
            x += btn_w + 1
        return False

    def _handle_drag_resize_mouse(self, mx, my, bstate):
        """Handle active drag or resize operations."""
        return handle_drag_resize_mouse(self, mx, my, bstate)

    def _handle_global_menu_mouse(self, mx, my, bstate):
        """Handle mouse interaction when the global menu is active."""
        return handle_global_menu_mouse(self, mx, my, bstate)

    def _handle_window_mouse(self, mx, my, bstate):
        """Route mouse events to windows in z-order."""
        return handle_window_mouse(self, mx, my, bstate)

    def _handle_desktop_mouse(self, mx, my, bstate):
        """Handle desktop icon interactions and deselection."""
        return handle_desktop_mouse(self, mx, my, bstate)

    def handle_mouse(self, event):
        """Handle mouse events."""
        return handle_mouse_event(self, event)

    @staticmethod
    def _key_code(key):
        """Normalize key values from get_wch()/getch() into common control codes."""
        return normalize_app_key(key)

    def _handle_menu_hotkeys(self, key_code):
        """Handle F10 and Escape interactions for menus."""
        return handle_menu_hotkeys(self, key_code)

    def _handle_global_menu_key(self, key_code):
        """Handle keyboard navigation for the global menu."""
        return handle_global_menu_key(self, key_code)

    def _cycle_focus(self):
        """Cycle focus through visible windows."""
        return cycle_focus(self)

    def _handle_active_window_key(self, key):
        """Delegate key input to active window."""
        return handle_active_window_key(self, key)

    def handle_key(self, key):
        """Handle keyboard input."""
        return handle_key_event(self, key)

    def run(self):
        """Main event loop."""
        return run_app_loop(self)

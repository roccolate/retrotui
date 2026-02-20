"""
Main RetroTUI Application Class.
"""
import os
import curses
import logging
import threading
import time

from ..constants import (
    ICONS, ICONS_ASCII, TASKBAR_TITLE_MAX_LEN, BINARY_DETECT_CHUNK_SIZE,
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
from .drag_drop import DragDropManager
from .file_operations import FileOperationManager
from .icon_manager import IconPositionManager
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

    # Dispatch table for _dispatch_window_result: ActionType -> method name
    # Methods are called as self.<method>(source_win) for entries requiring source_win
    _RESULT_DISPATCH = {
        ActionType.REQUEST_SAVE_AS: 'show_save_as_dialog',
        ActionType.REQUEST_OPEN_PATH: 'show_open_dialog',
        ActionType.REQUEST_RENAME_ENTRY: 'show_rename_dialog',
        ActionType.REQUEST_DELETE_CONFIRM: 'show_delete_confirm_dialog',
        ActionType.REQUEST_COPY_ENTRY: 'show_copy_dialog',
        ActionType.REQUEST_MOVE_ENTRY: 'show_move_dialog',
        ActionType.REQUEST_NEW_DIR: 'show_new_dir_dialog',
        ActionType.REQUEST_NEW_FILE: 'show_new_file_dialog',
    }

    @property
    def file_ops(self):
        """Return the FileOperationManager, creating it lazily when needed."""
        try:
            return self._file_ops
        except AttributeError:
            self._file_ops = FileOperationManager(self)
            return self._file_ops

    @file_ops.setter
    def file_ops(self, value):
        self._file_ops = value

    @property
    def icon_positions(self):
        try:
            return self._icon_mgr.positions
        except AttributeError:
            self._icon_mgr = IconPositionManager(self)
            return self._icon_mgr.positions

    @icon_positions.setter
    def icon_positions(self, value):
        try:
            self._icon_mgr.positions = value
        except AttributeError:
            self._icon_mgr = IconPositionManager(self)
            self._icon_mgr.positions = value

    def _ensure_drag_drop(self):
        """Lazily create DragDropManager when accessed before __init__ completes."""
        try:
            return self.drag_drop
        except AttributeError:
            self.drag_drop = DragDropManager(self)
            return self.drag_drop

    @property
    def drag_payload(self):
        return self._ensure_drag_drop().payload

    @drag_payload.setter
    def drag_payload(self, value):
        self._ensure_drag_drop().payload = value

    @property
    def drag_source_window(self):
        return self._ensure_drag_drop().source_window

    @drag_source_window.setter
    def drag_source_window(self, value):
        self._ensure_drag_drop().source_window = value

    @property
    def drag_target_window(self):
        return self._ensure_drag_drop().target_window

    @drag_target_window.setter
    def drag_target_window(self, value):
        self._ensure_drag_drop().target_window = value

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.running = True
        self.windows = []
        self.menu = Menu()
        self.context_menu = None
        self.dialog = None
        self.selected_icon = -1
        self.use_unicode = check_unicode_support()
        self.config = load_config()
        self.theme_name = self.config.theme
        self.refresh_icons()
        self.theme = get_theme(self.theme_name)
        self.default_show_hidden = bool(self.config.show_hidden)
        self.default_word_wrap = bool(self.config.word_wrap_default)
        self.default_sunday_first = bool(self.config.sunday_first)
        self.show_welcome = bool(self.config.show_welcome)
        self.drag_drop = DragDropManager(self)
        # Movable desktop icon positions: mapping icon_key -> (x, y)
        self._icon_mgr = IconPositionManager(self)
        self._background_operation = None
        self._file_ops = FileOperationManager(self)

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
            win = Window('Welcome to RetroTUI', w // 2 - 22, h // 2 - 10, 44, 20,
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

    def refresh_icons(self):
        """Rebuild desktop icons list based on config and unicode support."""
        base_icons = ICONS if self.use_unicode else ICONS_ASCII
        hidden_labels = {x.strip().lower() for x in self.config.hidden_icons.split(",")} if getattr(self.config, 'hidden_icons', "") else set()
        self.icons = [icon for icon in base_icons if icon["label"].lower() not in hidden_labels]

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
        from .config import default_config_path
        return self._icon_mgr.load(default_config_path())

    def _save_icon_positions(self, cfg_path=None):
        from .config import default_config_path
        path = cfg_path if cfg_path is not None else default_config_path()
        self._icon_mgr.save(path)

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
        return self._icon_mgr.get_screen_pos(index)

    def get_icon_at(self, mx, my):
        """Return icon index at mouse position, or -1."""
        return self._icon_mgr.get_icon_at(mx, my)

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

        # 1. Try delegating to the active window first (for context menu / internal actions)
        active_win = self.get_active_window()
        if active_win and hasattr(active_win, 'execute_action'):
            result = active_win.execute_action(action)
            if result:
                self._dispatch_window_result(result, active_win)
                return

        # 2. Fallback to global/app-level actions
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
                chunk = f.read(BINARY_DETECT_CHUNK_SIZE)
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
        self.file_ops.show_save_as_dialog(win)

    def show_open_dialog(self, win):
        """Show dialog to get filename/path for opening in current window."""
        self.file_ops.show_open_dialog(win)

    def show_rename_dialog(self, win):
        """Show dialog to rename selected File Manager entry."""
        self.file_ops.show_rename_dialog(win)

    def show_delete_confirm_dialog(self, win):
        """Show confirmation dialog before deleting selected File Manager entry."""
        self.file_ops.show_delete_confirm_dialog(win)

    def show_copy_dialog(self, win):
        """Show destination input for copy operation in File Manager."""
        self.file_ops.show_copy_dialog(win)

    def show_move_dialog(self, win):
        """Show destination input for move operation in File Manager."""
        self.file_ops.show_move_dialog(win)

    def show_new_dir_dialog(self, win):
        """Show input dialog to create a new directory in current path."""
        self.file_ops.show_new_dir_dialog(win)

    def show_new_file_dialog(self, win):
        """Show input dialog to create a new file in current path."""
        self.file_ops.show_new_file_dialog(win)

    def show_kill_confirm_dialog(self, win, payload):
        """Show confirmation dialog before sending signal to a process."""
        self.file_ops.show_kill_confirm_dialog(win, payload)

    @staticmethod
    def _window_selected_entry(win):
        """Resolve selected entry accessor from supported window APIs."""
        return FileOperationManager._window_selected_entry(win)

    @staticmethod
    def _resolve_between_panes_destination(win, payload):
        """Resolve destination path for copy/move between panes requests."""
        return FileOperationManager._resolve_between_panes_destination(win, payload)

    def _is_long_file_operation(self, entry):
        """Return True when operation should show a modal progress dialog."""
        return self.file_ops._is_long_file_operation(entry)

    def _start_background_operation(self, *, title, message, worker, source_win):
        """Run blocking filesystem operation in a worker thread and show progress."""
        return self.file_ops._start_background_operation(
            title=title,
            message=message,
            worker=worker,
            source_win=source_win,
        )

    def has_background_operation(self):
        """Return whether a background file operation is currently running."""
        return self.file_ops.has_background_operation()

    def poll_background_operation(self):
        """Advance progress state and dispatch completion when worker finishes."""
        return self.file_ops.poll_background_operation()

    def _run_file_operation_with_progress(self, win, *, operation, destination=None):
        """Run file operation directly or via background worker with progress dialog."""
        return self.file_ops._run_file_operation_with_progress(
            win,
            operation=operation,
            destination=destination,
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

        if result.type == ActionType.REFRESH:
            return

        LOGGER.debug('Dispatching window result: type=%s payload=%r', result.type, result.payload)

        # Simple dialog dispatches (require source_win)
        method_name = self._RESULT_DISPATCH.get(result.type)
        if method_name is not None:
            if source_win:
                getattr(self, method_name)(source_win)
            return

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
            label = win.title[:TASKBAR_TITLE_MAX_LEN]
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

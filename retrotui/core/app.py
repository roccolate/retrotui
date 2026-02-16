"""
Main RetroTUI Application Class.
"""
import os
import logging

from ..constants import (
    ICONS, ICONS_ASCII
)
from ..utils import (
    check_unicode_support, init_colors,
    is_video_file, play_ascii_video
)
from ..ui.menu import Menu
from ..ui.dialog import Dialog, InputDialog
from ..ui.window import Window
from ..apps.notepad import NotepadWindow
from .actions import ActionResult, ActionType, AppAction
from .action_runner import execute_app_action
from .content import build_welcome_content
from .mouse_router import (
    handle_drag_resize_mouse,
    handle_global_menu_mouse,
    handle_window_mouse,
    handle_desktop_mouse,
    handle_mouse_event,
)
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

APP_VERSION = '0.3.6'

class RetroTUI:
    """Main application class."""
    MIN_TERM_WIDTH = 80
    MIN_TERM_HEIGHT = 24

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.running = True
        self.windows = []
        self.menu = Menu()
        self.dialog = None
        self.selected_icon = -1
        self.use_unicode = check_unicode_support()
        self.icons = ICONS if self.use_unicode else ICONS_ASCII

        # Setup terminal
        configure_terminal(stdscr, timeout_ms=500)
        self._validate_terminal_size()

        disable_flow_control()
        self.click_flags, self.stop_drag_flags, self.scroll_down_mask = enable_mouse_support()

        init_colors()

        # Create a welcome window
        h, w = stdscr.getmaxyx()
        welcome_content = build_welcome_content(APP_VERSION)
        win = Window('Welcome to RetroTUI', w // 2 - 25, h // 2 - 10, 50, 20,
                      content=welcome_content)
        win.active = True
        self.windows.append(win)

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

    def get_icon_at(self, mx, my):
        """Return icon index at mouse position, or -1."""
        start_x = 3
        start_y = 3
        spacing_y = 5  # Must match draw_icons

        for i in range(len(self.icons)):
            iy = start_y + i * spacing_y
            icon_w = len(self.icons[i]['art'][0])
            if iy <= my <= iy + 3 and start_x <= mx <= start_x + icon_w - 1:
                return i
        return -1

    def set_active_window(self, win):
        """Set a window as active (bring to front)."""
        for w in self.windows:
            w.active = False
        win.active = True
        # Move to end of list (top of z-order)
        self.windows.remove(win)
        self.windows.append(win)

    def close_window(self, win):
        """Close a window."""
        closer = getattr(win, 'close', None)
        if callable(closer):
            try:
                closer()
            except Exception:  # pragma: no cover - defensive window cleanup path
                LOGGER.debug('Window close hook failed for %r', win, exc_info=True)
        self.windows.remove(win)
        if self.windows:
            self.windows[-1].active = True

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
        filename = os.path.basename(filepath)

        if is_video_file(filepath):
            success, error = play_ascii_video(self.stdscr, filepath)
            if not success:
                self.dialog = Dialog('ASCII Video Error', error, ['OK'], width=50)
            return

        # Check if file seems to be binary
        try:
            with open(filepath, 'rb') as f:
                chunk = f.read(1024)
                if b'\x00' in chunk:
                    self.dialog = Dialog('Binary File',
                        f'{filename}\n\nThis appears to be a binary file\nand cannot be displayed as text.',
                        ['OK'], width=48)
                    return
        except OSError:
            pass

        # Create NotepadWindow with file
        offset_x = 18 + len(self.windows) * 2
        offset_y = 3 + len(self.windows)
        win_w = min(70, w - 4)
        win_h = min(25, h - 4)
        win = NotepadWindow(offset_x, offset_y, win_w, win_h, filepath=filepath)
        self._spawn_window(win)

    def show_save_as_dialog(self, win):
        """Show dialog to get filename for saving."""
        dialog = InputDialog('Save As', 'Enter filename:', width=40)
        dialog.callback = lambda filename, target=win: target.save_as(filename)
        self.dialog = dialog

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

        if result.type == ActionType.SAVE_ERROR:
            message = result.payload or 'Unknown save error.'
            self.dialog = Dialog('Save Error', str(message), ['OK'], width=50)
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
            if callable(callback) and isinstance(dialog, InputDialog):
                callback_result = callback(dialog.value)

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

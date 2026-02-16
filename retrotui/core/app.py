"""
Main RetroTUI Application Class.
"""
import curses
import sys
import os
import termios
import logging

from ..constants import (
    C_DESKTOP, C_ICON, C_ICON_SEL, C_TASKBAR, C_STATUS,
    DESKTOP_PATTERN, ICONS, ICONS_ASCII
)
from ..utils import (
    check_unicode_support, init_colors, safe_addstr,
    is_video_file, play_ascii_video, normalize_key_code
)
from ..ui.menu import Menu
from ..ui.dialog import Dialog, InputDialog
from ..ui.window import Window
from ..apps.notepad import NotepadWindow
from .actions import ActionResult, ActionType, AppAction
from .action_runner import execute_app_action
from .content import build_welcome_content

LOGGER = logging.getLogger(__name__)

APP_VERSION = '0.3.4'

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

        # Setup curses
        curses.curs_set(0)
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        stdscr.nodelay(False)
        stdscr.timeout(500)  # 500ms for clock updates
        self._validate_terminal_size()

        # Disable XON/XOFF flow control so Ctrl+Q/Ctrl+S reach the app
        try:
            fd = sys.stdin.fileno()
            attrs = termios.tcgetattr(fd)
            attrs[0] &= ~termios.IXON   # Disable XON/XOFF output control
            attrs[0] &= ~termios.IXOFF   # Disable XON/XOFF input control
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
        except (termios.error, ValueError, OSError):
            pass  # Not a real terminal or unsupported

        # Enable mouse
        curses.mousemask(
            curses.ALL_MOUSE_EVENTS |
            curses.REPORT_MOUSE_POSITION
        )
        self.click_flags = (
            curses.BUTTON1_CLICKED |
            curses.BUTTON1_PRESSED |
            curses.BUTTON1_DOUBLE_CLICKED
        )
        self.stop_drag_flags = self.click_flags | curses.BUTTON1_RELEASED
        self.scroll_down_mask = getattr(curses, 'BUTTON5_PRESSED', 0x200000)
        # Enable SGR extended mouse mode for better coordinate support
        # Use 1002 (button-event tracking) — reports motion only while button held
        # This gives us implicit release detection: motion events stop when released
        print('\033[?1002h', end='', flush=True)  # Button-event tracking (drag)
        print('\033[?1006h', end='', flush=True)  # SGR extended mode

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
        print('\033[?1002l', end='', flush=True)
        print('\033[?1006l', end='', flush=True)

    def draw_desktop(self):
        """Draw the desktop background pattern."""
        h, w = self.stdscr.getmaxyx()
        attr = curses.color_pair(C_DESKTOP)
        pattern = DESKTOP_PATTERN

        for row in range(1, h - 1):
            line = (pattern * (w // len(pattern) + 1))[:w - 1]
            safe_addstr(self.stdscr, row, 0, line, attr)

    def draw_icons(self):
        """Draw desktop icons (3x4 art + label)."""
        h, w = self.stdscr.getmaxyx()
        start_x = 3
        start_y = 3
        spacing_y = 5  # 3 lines art + 1 label + 1 gap

        for i, icon in enumerate(self.icons):
            y = start_y + i * spacing_y
            if y + 3 >= h - 1:
                break
            is_sel = (i == self.selected_icon)
            attr = curses.color_pair(C_ICON_SEL if is_sel else C_ICON) | curses.A_BOLD
            # Draw 3-line art
            for row, line in enumerate(icon['art']):
                safe_addstr(self.stdscr, y + row, start_x, line, attr)
            # Draw label centered below art
            label = icon['label'].center(len(icon['art'][0]))
            safe_addstr(self.stdscr, y + 3, start_x, label, attr)

    def draw_taskbar(self):
        """Draw taskbar row with minimized window buttons."""
        h, w = self.stdscr.getmaxyx()
        taskbar_y = h - 2
        minimized = [win for win in self.windows if win.minimized]
        if not minimized:
            return
        attr = curses.color_pair(C_TASKBAR)
        safe_addstr(self.stdscr, taskbar_y, 0, ' ' * (w - 1), attr)
        x = 1
        for win in minimized:
            label = win.title[:15]
            btn = f'[{label}]'
            if x + len(btn) >= w - 1:
                break
            safe_addstr(self.stdscr, taskbar_y, x, btn, attr | curses.A_BOLD)
            x += len(btn) + 1

    def draw_statusbar(self):
        """Draw the bottom status bar."""
        h, w = self.stdscr.getmaxyx()
        attr = curses.color_pair(C_STATUS)
        visible = sum(1 for win in self.windows if win.visible)
        total = len(self.windows)
        status = f' RetroTUI v{APP_VERSION} | Windows: {visible}/{total} | Mouse: Enabled | Ctrl+Q: Exit'
        safe_addstr(self.stdscr, h - 1, 0, status.ljust(w - 1), attr)

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
        any_dragging = any(w.dragging for w in self.windows)
        if any_dragging:
            if bstate & self.stop_drag_flags:
                for win in self.windows:
                    win.dragging = False
                return True
            for win in self.windows:
                if win.dragging:
                    h, w = self.stdscr.getmaxyx()
                    new_x = mx - win.drag_offset_x
                    new_y = my - win.drag_offset_y
                    win.x = max(0, min(new_x, w - win.w))
                    win.y = max(1, min(new_y, h - win.h - 1))
                    return True
            return True

        any_resizing = any(w.resizing for w in self.windows)
        if any_resizing:
            if bstate & self.stop_drag_flags:
                for win in self.windows:
                    win.resizing = False
                    win.resize_edge = None
                return True
            for win in self.windows:
                if win.resizing:
                    h, w = self.stdscr.getmaxyx()
                    win.apply_resize(mx, my, w, h)
                    return True
            return True
        return False

    def _handle_global_menu_mouse(self, mx, my, bstate):
        """Handle mouse interaction when the global menu is active."""
        if not self.menu.active:
            return False
        if bstate & curses.REPORT_MOUSE_POSITION:
            self.menu.handle_hover(mx, my)
            return True
        if bstate & self.click_flags:
            action = self.menu.handle_click(mx, my)
            if action:
                self.execute_action(action)
            return True
        if self.menu.hit_test_dropdown(mx, my) or my == 0:
            return True
        return False

    def _handle_window_mouse(self, mx, my, bstate):
        """Route mouse events to windows in z-order."""
        for win in reversed(self.windows):
            if not win.visible:
                continue

            click_flags = self.click_flags

            if win.on_close_button(mx, my) and (bstate & click_flags):
                self.close_window(win)
                return True

            if win.on_minimize_button(mx, my) and (bstate & click_flags):
                self.set_active_window(win)
                win.toggle_minimize()
                visible = [w for w in self.windows if w.visible]
                if visible:
                    self.set_active_window(visible[-1])
                return True

            if win.on_maximize_button(mx, my) and (bstate & click_flags):
                self.set_active_window(win)
                h, w = self.stdscr.getmaxyx()
                win.toggle_maximize(w, h)
                return True

            if bstate & curses.BUTTON1_PRESSED:
                edge = win.on_border(mx, my)
                if edge:
                    win.resizing = True
                    win.resize_edge = edge
                    self.set_active_window(win)
                    return True

            if win.on_title_bar(mx, my):
                if bstate & curses.BUTTON1_DOUBLE_CLICKED:
                    self.set_active_window(win)
                    h, w = self.stdscr.getmaxyx()
                    win.toggle_maximize(w, h)
                    return True
                if bstate & curses.BUTTON1_PRESSED:
                    if not win.maximized:
                        win.dragging = True
                        win.drag_offset_x = mx - win.x
                        win.drag_offset_y = my - win.y
                    self.set_active_window(win)
                    return True
                if bstate & curses.BUTTON1_CLICKED:
                    self.set_active_window(win)
                    return True

            if (bstate & curses.REPORT_MOUSE_POSITION) and win.window_menu and win.window_menu.active:
                if win.window_menu.handle_hover(mx, my, win.x, win.y, win.w):
                    return True

            if win.window_menu and win.window_menu.active and not win.contains(mx, my):
                if bstate & click_flags:
                    win.window_menu.active = False

            if win.contains(mx, my):
                if bstate & click_flags:
                    self.set_active_window(win)
                    for other_win in self.windows:
                        if other_win is not win and other_win.window_menu and other_win.window_menu.active:
                            other_win.window_menu.active = False
                    result = win.handle_click(mx, my)
                    self._dispatch_window_result(result, win)
                    return True

                if bstate & curses.BUTTON4_PRESSED:
                    win.handle_scroll('up', 3)
                    return True

                if bstate & self.scroll_down_mask:
                    win.handle_scroll('down', 3)
                    return True
        return False

    def _handle_desktop_mouse(self, mx, my, bstate):
        """Handle desktop icon interactions and deselection."""
        if bstate & curses.BUTTON1_DOUBLE_CLICKED:
            icon_idx = self.get_icon_at(mx, my)
            if icon_idx >= 0:
                self.execute_action(self.icons[icon_idx]['action'])
                return True

        if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
            icon_idx = self.get_icon_at(mx, my)
            if icon_idx >= 0:
                self.selected_icon = icon_idx
                return True

        self.selected_icon = -1
        self.menu.active = False
        return True

    def handle_mouse(self, event):
        """Handle mouse events."""
        try:
            _, mx, my, _, bstate = event
        except (TypeError, ValueError):
            return

        if self._handle_dialog_mouse(mx, my, bstate):
            return

        if my == 0 and (bstate & self.click_flags):
            action = self.menu.handle_click(mx, my)
            if action:
                self.execute_action(action)
            return

        if self._handle_drag_resize_mouse(mx, my, bstate):
            return

        if self._handle_global_menu_mouse(mx, my, bstate):
            return

        if (bstate & self.click_flags) and self.handle_taskbar_click(mx, my):
            return

        if self._handle_window_mouse(mx, my, bstate):
            return

        self._handle_desktop_mouse(mx, my, bstate)

    @staticmethod
    def _key_code(key):
        """Normalize key values from get_wch()/getch() into common control codes."""
        return normalize_key_code(key)

    def _handle_menu_hotkeys(self, key_code):
        """Handle F10 and Escape interactions for menus."""
        if key_code is None:
            return False

        if key_code == curses.KEY_F10:
            active_win = self.get_active_window()
            if active_win and active_win.window_menu:
                wm = active_win.window_menu
                wm.active = not wm.active
                if wm.active:
                    wm.selected_menu = 0
                    wm.selected_item = 0
                return True
            if self.menu.active:
                self.menu.active = False
            else:
                self.menu.active = True
                self.menu.selected_menu = 0
                self.menu.selected_item = 0
            return True

        if key_code == 27:
            active_win = self.get_active_window()
            if active_win and active_win.window_menu and active_win.window_menu.active:
                active_win.window_menu.active = False
            elif self.menu.active:
                self.menu.active = False
            return True

        return False

    def _handle_global_menu_key(self, key_code):
        """Handle keyboard navigation for the global menu."""
        if not self.menu.active:
            return False

        if key_code is None:
            return True

        action = self.menu.handle_key(key_code)
        if action:
            self.execute_action(action)
        return True

    def _cycle_focus(self):
        """Cycle focus through visible windows."""
        visible_windows = [w for w in self.windows if w.visible]
        if not visible_windows:
            return
        current = next((i for i, w in enumerate(visible_windows) if w.active), -1)
        next_idx = (current + 1) % len(visible_windows)
        for w in self.windows:
            w.active = False
        visible_windows[next_idx].active = True

    def _handle_active_window_key(self, key):
        """Delegate key input to active window."""
        active_win = self.get_active_window()
        if not active_win:
            return

        result = active_win.handle_key(key)
        self._dispatch_window_result(result, active_win)

    def handle_key(self, key):
        """Handle keyboard input."""
        key_code = self._key_code(key)

        if self._handle_dialog_key(key):
            return

        if key_code == 17:  # Ctrl+Q
            self.execute_action(AppAction.EXIT)
            return

        if self._handle_menu_hotkeys(key_code):
            return

        if self._handle_global_menu_key(key_code):
            return

        if key_code == 9:  # Tab
            self._cycle_focus()
            return

        self._handle_active_window_key(key)

    def run(self):
        """Main event loop."""
        try:
            while self.running:
                # Clear and redraw
                self.stdscr.erase()
                self.draw_desktop()
                self.draw_icons()

                # Draw windows
                for win in self.windows:
                    win.draw(self.stdscr)

                # Menu bar (on top)
                h, w = self.stdscr.getmaxyx()
                self.menu.draw_bar(self.stdscr, w)
                self.menu.draw_dropdown(self.stdscr)

                # Taskbar (minimized windows)
                self.draw_taskbar()

                # Status bar
                self.draw_statusbar()

                # Dialog on top of everything
                if self.dialog:
                    self.dialog.draw(self.stdscr)

                self.stdscr.noutrefresh()
                curses.doupdate()

                # Handle input
                try:
                    key = self.stdscr.get_wch()
                except curses.error:
                    continue

                if isinstance(key, int) and key == curses.KEY_MOUSE:
                    try:
                        event = curses.getmouse()
                        self.handle_mouse(event)
                    except curses.error:
                        pass
                elif isinstance(key, int) and key == curses.KEY_RESIZE:
                    curses.update_lines_cols()
                    # Reclamp windows to new terminal size
                    new_h, new_w = self.stdscr.getmaxyx()
                    for win in self.windows:
                        win.x = max(0, min(win.x, new_w - min(win.w, new_w)))
                        win.y = max(1, min(win.y, new_h - min(win.h, new_h) - 1))
                else:
                    self.handle_key(key)
        finally:
            self.cleanup()

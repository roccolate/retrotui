"""
Main RetroTUI Application Class.
"""
import curses
import sys
import time
import os
import termios

from ..constants import (
    C_DESKTOP, C_ICON, C_ICON_SEL, C_TASKBAR, C_STATUS,
    DESKTOP_PATTERN, ICONS, ICONS_ASCII
)
from ..utils import (
    check_unicode_support, init_colors, safe_addstr, get_system_info,
    is_video_file, play_ascii_video
)
from ..ui.menu import Menu
from ..ui.dialog import Dialog, InputDialog
from ..ui.window import Window
from ..apps.filemanager import FileManagerWindow
from ..apps.notepad import NotepadWindow

class RetroTUI:
    """Main application class."""

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
        # Enable SGR extended mouse mode for better coordinate support
        # Use 1002 (button-event tracking) — reports motion only while button held
        # This gives us implicit release detection: motion events stop when released
        print('\033[?1002h', end='', flush=True)  # Button-event tracking (drag)
        print('\033[?1006h', end='', flush=True)  # SGR extended mode

        init_colors()

        # Create a welcome window
        h, w = stdscr.getmaxyx()
        welcome_content = [
            '',
            '   ╔══════════════════════════════════════╗',
            '   ║      Welcome to RetroTUI v0.3.3        ║',
            '   ║                                      ║',
            '   ║  A Windows 3.1 style desktop         ║',
            '   ║  environment for the Linux console.  ║',
            '   ║                                      ║',
            '   ║  New in v0.3.3:                      ║',
            '   ║  • Modular Package Structure         ║',
            '   ║  • ASCII Video Player (mpv/mplayer)   ║',
            '   ║  • Per-window menus (File, View)     ║',
            '   ║  • Text editor (Notepad)             ║',
            '   ║                                      ║',
            '   ║  Use mouse or keyboard to navigate.  ║',
            '   ║  Press Ctrl+Q to exit.               ║',
            '   ╚══════════════════════════════════════╝',
            '',
        ]
        win = Window('Welcome to RetroTUI', w // 2 - 25, h // 2 - 10, 50, 20,
                      content=welcome_content)
        win.active = True
        self.windows.append(win)

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
        status = f' RetroTUI v0.3.3 │ Windows: {visible}/{total} │ Mouse: Enabled │ Ctrl+Q: Exit'
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

    def execute_action(self, action):
        """Execute a menu/icon action."""
        h, w = self.stdscr.getmaxyx()

        if action == 'exit':
            self.dialog = Dialog(
                'Exit RetroTUI',
                'Are you sure you want to exit?\n\nAll windows will be closed.',
                ['Yes', 'No'],
                width=44
            )

        elif action == 'about':
            sys_info = get_system_info()
            msg = ('RetroTUI v0.3.3\n'
                   'A retro desktop environment for Linux console.\n\n'
                   'System Information:\n' +
                   '\n'.join(sys_info) + '\n\n'
                   'Mouse: GPM/xterm protocol\n'
                   'No X11 required!')
            self.dialog = Dialog('About RetroTUI', msg, ['OK'], width=52)

        elif action == 'help':
            msg = ('Keyboard Controls:\n\n'
                   'Tab       - Cycle windows\n'
                   'Escape    - Close menu/dialog\n'
                   'Enter     - Activate selection\n'
                   'Ctrl+Q    - Exit\n'
                   'F10       - Open menu\n'
                   'Arrow keys - Navigate\n'
                   'PgUp/PgDn - Scroll content\n\n'
                   'File Manager:\n\n'
                   'Up/Down   - Move selection\n'
                   'Enter     - Open dir/file\n'
                   'Backspace - Parent directory\n'
                   'H         - Toggle hidden files\n'
                   'Home/End  - First/last entry\n\n'
                   'Notepad Editor:\n\n'
                   'Arrows    - Move cursor\n'
                   'Home/End  - Start/end of line\n'
                   'PgUp/PgDn - Page up/down\n'
                   'Backspace - Delete backward\n'
                   'Delete    - Delete forward\n'
                   'Ctrl+W    - Toggle word wrap\n\n'
                   'Mouse Controls:\n\n'
                   'Click     - Select/activate\n'
                   'Drag title - Move window\n'
                   'Drag border - Resize window\n'
                   'Dbl-click title - Maximize\n'
                   '[─]       - Minimize\n'
                   '[□]       - Maximize/restore\n'
                   'Scroll    - Scroll/select')
            self.dialog = Dialog('Keyboard & Mouse Help', msg, ['OK'], width=46)

        elif action == 'filemanager':
            offset_x = 15 + len(self.windows) * 2
            offset_y = 3 + len(self.windows) * 1
            win = FileManagerWindow(offset_x, offset_y, 58, 22)
            self.windows.append(win)
            self.set_active_window(win)

        elif action == 'notepad':
            offset_x = 20 + len(self.windows) * 2
            offset_y = 4 + len(self.windows) * 1
            win = NotepadWindow(offset_x, offset_y, 60, 20)
            self.windows.append(win)
            self.set_active_window(win)

        elif action == 'asciivideo':
            self.dialog = Dialog(
                'ASCII Video',
                'Reproduce video en la terminal.\n\n'
                'Usa mpv (color) o mplayer (fallback).\n'
                'Abre un video desde File Manager.',
                ['OK'],
                width=50,
            )

        elif action == 'terminal':
            content = [
                f' user@{os.uname().nodename}:~$ _',
                '',
                ' (Terminal emulation placeholder)',
                ' Future: embedded terminal via pty',
            ]
            offset_x = 18 + len(self.windows) * 2
            offset_y = 5 + len(self.windows) * 1
            win = Window('Terminal', offset_x, offset_y, 60, 15, content=content)
            self.windows.append(win)
            self.set_active_window(win)

        elif action == 'settings':
            content = [
                ' ╔═ Display Settings ══════════════════════╗',
                ' ║                                         ║',
                ' ║  Theme: [x] Windows 3.1                 ║',
                ' ║         [ ] DOS / CGA                   ║',
                ' ║         [ ] Windows 95                  ║',
                ' ║                                         ║',
                ' ║  Desktop Pattern: ░ ▒ ▓                 ║',
                ' ║                                         ║',
                ' ║  Colors: 256-color mode                 ║',
                ' ║                                         ║',
                ' ╚═════════════════════════════════════════╝',
            ]
            offset_x = 22 + len(self.windows) * 2
            offset_y = 4 + len(self.windows) * 1
            win = Window('Settings', offset_x, offset_y, 48, 15, content=content)
            self.windows.append(win)
            self.set_active_window(win)

        elif action == 'new_window':
            offset_x = 20 + len(self.windows) * 2
            offset_y = 3 + len(self.windows) * 1
            win = Window(f'Window {Window._next_id}', offset_x, offset_y, 40, 12,
                          content=['', ' New empty window', ''])
            self.windows.append(win)
            self.set_active_window(win)

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
        win = NotepadWindow(offset_x, offset_y, win_w, win_h, filepath=filepath)
        self.windows.append(win)
        self.set_active_window(win)

    def show_save_as_dialog(self, win):
        """Show dialog to get filename for saving."""
        self.dialog = InputDialog('Save As', 'Enter filename:', width=40)
        self.dialog.callback = lambda filename: win.save_as(filename)


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

    def handle_mouse(self, event):
        """Handle mouse events."""
        try:
            _, mx, my, _, bstate = event
        except Exception:
            return

        # Dialog takes priority
        if self.dialog:
            if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_DOUBLE_CLICKED):
                result = self.dialog.handle_click(mx, my)
                if result >= 0:
                    btn_text = self.dialog.buttons[result]
                    if self.dialog.title == 'Exit RetroTUI' and btn_text == 'Yes':
                        self.running = False
                    elif hasattr(self.dialog, 'callback') and result == 0:
                         # For InputDialog, result 0 is OK
                         if hasattr(self.dialog, 'value'):
                             self.dialog.callback(self.dialog.value)
                    
                    self.dialog = None
            return

        # Menu bar click
        if my == 0 and (bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_DOUBLE_CLICKED)):
            action = self.menu.handle_click(mx, my)
            if action:
                self.execute_action(action)
            return

        # Window dragging — check FIRST, before menu/window clicks
        any_dragging = any(w.dragging for w in self.windows)
        if any_dragging:
            stop_flags = (curses.BUTTON1_CLICKED | curses.BUTTON1_RELEASED |
                          curses.BUTTON1_DOUBLE_CLICKED)
            if bstate & stop_flags:
                for win in self.windows:
                    win.dragging = False
                return
            for win in self.windows:
                if win.dragging:
                    h, w = self.stdscr.getmaxyx()
                    new_x = mx - win.drag_offset_x
                    new_y = my - win.drag_offset_y
                    win.x = max(0, min(new_x, w - win.w))
                    win.y = max(1, min(new_y, h - win.h - 1))
                    return
            return

        # Window resizing — parallel to dragging
        any_resizing = any(w.resizing for w in self.windows)
        if any_resizing:
            stop_flags = (curses.BUTTON1_CLICKED | curses.BUTTON1_RELEASED |
                          curses.BUTTON1_DOUBLE_CLICKED)
            if bstate & stop_flags:
                for win in self.windows:
                    win.resizing = False
                    win.resize_edge = None
                return
            for win in self.windows:
                if win.resizing:
                    h, w = self.stdscr.getmaxyx()
                    win.apply_resize(mx, my, w, h)
                    return
            return

        # Menu dropdown handling (when menu is active)
        if self.menu.active:
            # Mouse movement — update hover highlight, don't close
            if bstate & curses.REPORT_MOUSE_POSITION:
                self.menu.handle_hover(mx, my)
                return
            # Actual click — select item or close menu
            if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_DOUBLE_CLICKED):
                action = self.menu.handle_click(mx, my)
                if action:
                    self.execute_action(action)
                return
            # For any other mouse event while menu is active, check if inside menu area
            if self.menu.hit_test_dropdown(mx, my) or my == 0:
                return  # Stay active, absorb event

        # Taskbar click — restore minimized windows
        if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_DOUBLE_CLICKED):
            if self.handle_taskbar_click(mx, my):
                return

        # Check windows (reverse z-order for top window first)
        for win in reversed(self.windows):
            if not win.visible:
                continue

            click_flags = curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_DOUBLE_CLICKED

            # Close button [×]
            if win.on_close_button(mx, my) and (bstate & click_flags):
                self.close_window(win)
                return

            # Minimize button [─]
            if win.on_minimize_button(mx, my) and (bstate & click_flags):
                self.set_active_window(win)
                win.toggle_minimize()
                # Activate next visible window
                visible = [w for w in self.windows if w.visible]
                if visible:
                    self.set_active_window(visible[-1])
                return

            # Maximize button [□]
            if win.on_maximize_button(mx, my) and (bstate & click_flags):
                self.set_active_window(win)
                h, w = self.stdscr.getmaxyx()
                win.toggle_maximize(w, h)
                return

            # Border resize (check before title bar to capture corners)
            if bstate & curses.BUTTON1_PRESSED:
                edge = win.on_border(mx, my)
                if edge:
                    win.resizing = True
                    win.resize_edge = edge
                    self.set_active_window(win)
                    return

            # Title bar — drag or double-click maximize
            if win.on_title_bar(mx, my):
                if bstate & curses.BUTTON1_DOUBLE_CLICKED:
                    self.set_active_window(win)
                    h, w = self.stdscr.getmaxyx()
                    win.toggle_maximize(w, h)
                    return
                elif bstate & curses.BUTTON1_PRESSED:
                    if not win.maximized:
                        win.dragging = True
                        win.drag_offset_x = mx - win.x
                        win.drag_offset_y = my - win.y
                    self.set_active_window(win)
                    return
                elif bstate & curses.BUTTON1_CLICKED:
                    self.set_active_window(win)
                    return

            # Window menu hover tracking
            if (bstate & curses.REPORT_MOUSE_POSITION) and win.window_menu and win.window_menu.active:
                if win.window_menu.handle_hover(mx, my, win.x, win.y, win.w):
                    return

            # Click outside window with active menu — close menu
            if win.window_menu and win.window_menu.active and not win.contains(mx, my):
                if bstate & click_flags:
                    win.window_menu.active = False
                    # Don't return — let click propagate to other windows

            if win.contains(mx, my):
                if bstate & click_flags:
                    self.set_active_window(win)
                    # Close other windows' menus when clicking on a different window
                    for other_win in self.windows:
                        if other_win is not win and other_win.window_menu and other_win.window_menu.active:
                            other_win.window_menu.active = False
                    # Delegate click to window if it has a handler
                    if hasattr(win, 'handle_click'):
                        result = win.handle_click(mx, my)
                        if result and result[0] == 'file':
                            self.open_file_viewer(result[1])
                        elif result and result[0] == 'action':
                            if result[1] == 'close':
                                self.close_window(win)
                            else:
                                self.execute_action(result[1])
                        elif result:
                             # Forward other signals like save_as_request or error strings
                             return result
                    return
                # Scroll wheel
                if bstate & curses.BUTTON4_PRESSED:  # Scroll up
                    if hasattr(win, 'select_up'):
                        for _ in range(3):
                            win.select_up()
                    else:
                        win.scroll_up()
                    return
                if bstate & 0x200000:  # Scroll down (BUTTON5)
                    if hasattr(win, 'select_down'):
                        for _ in range(3):
                            win.select_down()
                    else:
                        win.scroll_down()
                    return

        # Desktop icons — check double-click FIRST (bstate includes CLICKED on double-click)
        if bstate & curses.BUTTON1_DOUBLE_CLICKED:
            icon_idx = self.get_icon_at(mx, my)
            if icon_idx >= 0:
                self.execute_action(self.icons[icon_idx]['action'])
                return

        if bstate & curses.BUTTON1_CLICKED or bstate & curses.BUTTON1_PRESSED:
            icon_idx = self.get_icon_at(mx, my)
            if icon_idx >= 0:
                self.selected_icon = icon_idx
                return

        # Click on desktop - deselect
        self.selected_icon = -1
        self.menu.active = False

    def handle_key(self, key):
        """Handle keyboard input."""
        # Dialog takes priority
        if self.dialog:
            result = self.dialog.handle_key(key)
            if result >= 0:
                # Standard button press
                btn_text = self.dialog.buttons[result]
                if self.dialog.title == 'Exit RetroTUI' and btn_text == 'Yes':
                    self.running = False
                elif hasattr(self.dialog, 'callback') and result == 0:
                     if hasattr(self.dialog, 'value'):
                         self.dialog.callback(self.dialog.value)
                self.dialog = None
            return

        # Global shortcuts
        if key == 17:  # Ctrl+Q
            self.execute_action('exit')
            return

        # F10: window menu (if active window has one) or global menu
        if key == curses.KEY_F10:
            active_win = next((w for w in self.windows if w.active), None)
            if active_win and active_win.window_menu:
                wm = active_win.window_menu
                wm.active = not wm.active
                if wm.active:
                    wm.selected_menu = 0
                    wm.selected_item = 0
                return
            if self.menu.active:
                self.menu.active = False
            else:
                self.menu.active = True
                self.menu.selected_menu = 0
                self.menu.selected_item = 0
            return

        # Escape: close window menu, then global menu
        if key == 27:
            active_win = next((w for w in self.windows if w.active), None)
            if active_win and active_win.window_menu and active_win.window_menu.active:
                active_win.window_menu.active = False
            elif self.menu.active:
                self.menu.active = False
            return

        # Menu navigation
        if self.menu.active:
            if key == curses.KEY_LEFT:
                self.menu.selected_menu = (self.menu.selected_menu - 1) % len(self.menu.menu_names)
                self.menu.selected_item = 0
            elif key == curses.KEY_RIGHT:
                self.menu.selected_menu = (self.menu.selected_menu + 1) % len(self.menu.menu_names)
                self.menu.selected_item = 0
            elif key == curses.KEY_UP:
                items = self.menu.items[self.menu.menu_names[self.menu.selected_menu]]
                self.menu.selected_item = (self.menu.selected_item - 1) % len(items)
                while items[self.menu.selected_item][1] is None:
                    self.menu.selected_item = (self.menu.selected_item - 1) % len(items)
            elif key == curses.KEY_DOWN:
                items = self.menu.items[self.menu.menu_names[self.menu.selected_menu]]
                self.menu.selected_item = (self.menu.selected_item + 1) % len(items)
                while items[self.menu.selected_item][1] is None:
                    self.menu.selected_item = (self.menu.selected_item + 1) % len(items)
            elif key in (curses.KEY_ENTER, 10, 13):
                menu_name = self.menu.menu_names[self.menu.selected_menu]
                items = self.menu.items[menu_name]
                action = items[self.menu.selected_item][1]
                if action:
                    self.menu.active = False
                    self.execute_action(action)
            return

        # Window focus cycling (skip minimized windows)
        if key == 9:  # Tab
            visible_windows = [w for w in self.windows if w.visible]
            if visible_windows:
                current = next((i for i, w in enumerate(visible_windows) if w.active), -1)
                next_idx = (current + 1) % len(visible_windows)
                for w in self.windows:
                    w.active = False
                visible_windows[next_idx].active = True
            return

        # Delegate to active window
        active_win = next((w for w in self.windows if w.active), None)
        if active_win:
            if hasattr(active_win, 'handle_key'):
                result = active_win.handle_key(key)
                if result and result[0] == 'file':
                    self.open_file_viewer(result[1])
                elif result and result[0] == 'action':
                    if result[1] == 'close':
                        self.close_window(active_win)
                    else:
                        self.execute_action(result[1])
                elif result and result[0] == 'save_as_request':
                    self.show_save_as_dialog(active_win)
                elif result and result[0] == 'save_error':
                    self.dialog = Dialog('Save Error', result[1], ['OK'], width=50)
            else:
                # Default scroll behavior for regular windows
                if key == curses.KEY_UP or key == curses.KEY_PPAGE:
                    active_win.scroll_up()
                elif key == curses.KEY_DOWN or key == curses.KEY_NPAGE:
                    active_win.scroll_down()

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
                    key = self.stdscr.getch()
                except curses.error:
                    continue

                if key == -1:
                    continue
                elif key == curses.KEY_MOUSE:
                    try:
                        event = curses.getmouse()
                        self.handle_mouse(event)
                    except curses.error:
                        pass
                elif key == curses.KEY_RESIZE:
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

"""
Base Window Class.
"""
import curses
from ..constants import (
    C_WIN_BORDER, C_WIN_TITLE, C_WIN_TITLE_INV, C_WIN_BODY,
    C_STATUS, C_SCROLLBAR, C_WIN_INACTIVE, BOX_TR, BOX_TL,
    SB_TL
)
from ..utils import safe_addstr, draw_box
from .menu import WindowMenu

class Window:
    """A draggable window with title bar and content area."""

    _next_id = 0

    def __init__(self, title, x, y, w, h, content=None, resizable=True):
        self.id = Window._next_id
        Window._next_id += 1
        self.title = title
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.content = content or []  # List[str]
        self.active = False
        self.minimized = False
        self.maximized = False
        self.restore_rect = None      # (x, y, w, h) before maximize

        # State
        self.scroll_offset = 0
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.resizable = resizable
        self.resizing = False
        self.resize_edge = None       # 'right', 'bottom', 'corner'

        # Components
        self.visible = True
        self.window_menu = None  # Instance of WindowMenu if menu enabled

    def close_button_pos(self):
        """Return (x, y) of the close button."""
        return (self.x + 2, self.y)

    def body_rect(self):
        """Return inner content area (x, y, w, h).
           Accounts for window menu bar if present."""
        bx = self.x + 1
        by = self.y + 1
        bw = self.w - 2
        bh = self.h - 2
        if self.window_menu:
            by += 2  # Skip menu bar row and separator
            bh -= 2
        return (bx, by, bw, max(0, bh))

    def contains(self, mx, my):
        """Check if point is within window bounds."""
        return (self.x <= mx < self.x + self.w and
                self.y <= my < self.y + self.h)

    def on_title_bar(self, mx, my):
        """Check if point is on the title bar (draggable zone, excludes buttons)."""
        if my != self.y:
            return False
        # Exclude [×] at left and [─][□] at right (if implementation adds them)
        # Current implementation: [×] at left, [─][□] at right
        if mx < self.x + 1 or mx > self.x + self.w - 2:
            return False
        # Close button area
        if self.x + 2 <= mx <= self.x + 4:
            return False
        # Min/Max area
        if mx >= self.x + self.w - 7:
            return False
        return True

    def on_close_button(self, mx, my):
        """Check if point is on the close button [×]."""
        return my == self.y and (self.x + 2 <= mx <= self.x + 4)

    def on_minimize_button(self, mx, my):
        """Check if point is on the minimize button [─]."""
        return my == self.y and (self.x + self.w - 7 <= mx <= self.x + self.w - 5)

    def on_maximize_button(self, mx, my):
        """Check if point is on the maximize button [□]."""
        return my == self.y and (self.x + self.w - 4 <= mx <= self.x + self.w - 2)

    def toggle_maximize(self, term_w, term_h):
        """Toggle between maximized and normal state."""
        if not self.maximized:
            # Save current state
            self.restore_rect = (self.x, self.y, self.w, self.h)
            self.maximized = True
            self.x = 0
            self.y = 1  # Below global menu
            self.w = term_w
            self.h = term_h - 2  # Above taskbar
            # Force close menu on resize
            if self.window_menu:
                self.window_menu.active = False
        else:
            # Restore
            if self.restore_rect:
                self.x, self.y, self.w, self.h = self.restore_rect
            self.maximized = False
            # Clamp to screen just in case
            self.x = max(0, min(self.x, term_w - self.w))
            self.y = max(1, min(self.y, term_h - self.h - 1))

    def toggle_minimize(self):
        """Toggle between minimized and visible state."""
        self.minimized = not self.minimized
        self.visible = not self.minimized
        self.active = not self.minimized
        if self.window_menu:
            self.window_menu.active = False

    def on_border(self, mx, my):
        """Detect resize zone on window borders. Returns edge string or None.
           Only bottom, right, and bottom corners are resizable."""
        if not self.resizable or self.maximized:
            return None
        
        # Right border
        on_right = (mx == self.x + self.w - 1 and self.y <= my < self.y + self.h)
        # Bottom border
        on_bottom = (my == self.y + self.h - 1 and self.x <= mx < self.x + self.w)
        
        if on_right and on_bottom:
            return 'corner'
        if on_right:
            return 'right'
        if on_bottom:
            return 'bottom'
        return None

    def apply_resize(self, mx, my, term_w, term_h):
        """Apply resize based on mouse position and active resize_edge."""
        if self.resize_edge == 'right' or self.resize_edge == 'corner':
            new_w = mx - self.x + 1
            self.w = max(20, min(new_w, term_w - self.x))
        
        if self.resize_edge == 'bottom' or self.resize_edge == 'corner':
            new_h = my - self.y + 1
            self.h = max(8, min(new_h, term_h - self.y - 1))
        
        if self.window_menu:
            self.window_menu.active = False

    def draw_frame(self, stdscr):
        """Draw window frame: border, title bar, and buttons. Returns body_attr."""
        if not self.visible:
            return 0

        # Colors
        if self.active:
            border_attr = curses.color_pair(C_WIN_BORDER)
            title_attr = curses.color_pair(C_WIN_TITLE) | curses.A_BOLD
            body_attr = curses.color_pair(C_WIN_BODY)
        else:
            border_attr = curses.color_pair(C_WIN_INACTIVE)
            title_attr = curses.color_pair(C_WIN_INACTIVE)
            body_attr = curses.color_pair(C_WIN_INACTIVE)

        draw_box(stdscr, self.y, self.x, self.h, self.w, border_attr, double=True)

        # Title Bar
        title = f' {self.title} '
        # If active and has menu, show menu indicator
        if self.active and self.window_menu:
            title = ' ≡ ' + title.strip() + ' '
        
        safe_addstr(stdscr, self.y, self.x + 2, title, title_attr)
        
        # Buttons
        if self.active:
            # Close [×]
            safe_addstr(stdscr, self.y, self.x + 2, '[×]', curses.color_pair(C_WIN_TITLE_INV))
            
            # Min [─] Max [□]
            safe_addstr(stdscr, self.y, self.x + self.w - 7, '[─][□]', curses.color_pair(C_WIN_TITLE_INV))

        # Window Menu Bar
        if self.window_menu:
            self.window_menu.draw_bar(stdscr, self.x, self.y, self.w, self.active)
            # Separator line below menu
            sep_y = self.y + 2
            safe_addstr(stdscr, sep_y, self.x + 1, '╟' + '─' * (self.w - 2) + '╢', border_attr)

        return body_attr

    def draw_body(self, stdscr, body_attr):
        """Draw window body: background, content lines, scrollbar."""
        bx, by, bw, bh = self.body_rect()
        
        # Fill background
        for i in range(bh):
            safe_addstr(stdscr, by + i, bx, ' ' * bw, body_attr)

        # Draw content
        for i in range(bh):
            idx = self.scroll_offset + i
            if idx < len(self.content):
                line = self.content[idx][:bw]
                safe_addstr(stdscr, by + i, bx, line, body_attr)

        # Scrollbar
        if len(self.content) > bh:
            sb_x = bx + bw - 1
            # Thumb position
            thumb_pos = int(self.scroll_offset / max(1, len(self.content) - bh) * (bh - 1))
            for i in range(bh):
                ch = '█' if i == thumb_pos else '░'
                safe_addstr(stdscr, by + i, sb_x, ch, curses.color_pair(C_SCROLLBAR))

    def draw(self, stdscr):
        """Draw the window."""
        body_attr = self.draw_frame(stdscr)
        self.draw_body(stdscr, body_attr)
        
        # Draw window menu dropdown on top
        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def scroll_up(self):
        if self.scroll_offset > 0:
            self.scroll_offset -= 1

    def scroll_down(self):
        _, _, _, bh = self.body_rect()
        if self.scroll_offset < len(self.content) - bh:
            self.scroll_offset += 1

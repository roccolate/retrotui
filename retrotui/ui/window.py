"""
Base Window Class.
"""
import curses
from ..constants import (
    C_SCROLLBAR,
    C_WIN_BODY,
    C_WIN_BORDER,
    C_WIN_INACTIVE,
    C_WIN_TITLE,
    C_WIN_TITLE_INV,
    WIN_MIN_WIDTH,
    WIN_MIN_HEIGHT,
    MENU_BAR_HEIGHT,
    BOTTOM_BARS_HEIGHT,
)
from ..utils import safe_addstr, draw_box, theme_attr
from .menu import WindowMenu

class Window:
    """A draggable window with title bar and content area."""

    _next_id = 0
    TITLE_CONTROLS = '[─][□][×]'
    MIN_BTN_OFFSET = 10
    MAX_BTN_OFFSET = 7
    CLOSE_BTN_OFFSET = 4

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
        self.always_on_top = False
        self.drop_target_highlight = False

        # Components
        self.visible = True
        self.window_menu = None  # Instance of WindowMenu if menu enabled

    def close_button_pos(self):
        """Return (x, y) of the close button."""
        return (self.x + self.w - self.CLOSE_BTN_OFFSET, self.y)

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
        if mx < self.x + 1 or mx > self.x + self.w - 2:
            return False
        # Reserve right-side title controls: [─][□][×]
        if mx >= self.x + self.w - self.MIN_BTN_OFFSET:
            return False
        return True

    def on_close_button(self, mx, my):
        """Check if point is on the close button [×]."""
        start_x = self.x + self.w - self.CLOSE_BTN_OFFSET
        return my == self.y and (start_x <= mx <= start_x + 2)

    def on_minimize_button(self, mx, my):
        """Check if point is on the minimize button [─]."""
        start_x = self.x + self.w - self.MIN_BTN_OFFSET
        return my == self.y and (start_x <= mx <= start_x + 2)

    def on_maximize_button(self, mx, my):
        """Check if point is on the maximize button [□]."""
        start_x = self.x + self.w - self.MAX_BTN_OFFSET
        return my == self.y and (start_x <= mx <= start_x + 2)

    def toggle_maximize(self, term_w, term_h):
        """Toggle between maximized and normal state."""
        if not self.maximized:
            # Save current state
            self.restore_rect = (self.x, self.y, self.w, self.h)
            self.maximized = True
            self.x = 0
            self.y = MENU_BAR_HEIGHT  # Below global menu
            self.w = term_w
            self.h = term_h - BOTTOM_BARS_HEIGHT  # Above taskbar
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
            self.y = max(MENU_BAR_HEIGHT, min(self.y, term_h - self.h - 1))

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
            self.w = max(WIN_MIN_WIDTH, min(new_w, term_w - self.x))
        
        if self.resize_edge == 'bottom' or self.resize_edge == 'corner':
            new_h = my - self.y + 1
            self.h = max(WIN_MIN_HEIGHT, min(new_h, term_h - self.y - 1))
        
        if self.window_menu:
            self.window_menu.active = False

    def draw_frame(self, stdscr):
        """Draw window frame: border, title bar, and buttons. Returns body_attr."""
        if not self.visible:
            return 0

        # Colors
        if self.active:
            border_attr = theme_attr('window_border')
            title_attr = theme_attr('window_title') | curses.A_BOLD
            body_attr = theme_attr('window_body')
        else:
            border_attr = theme_attr('window_inactive')
            title_attr = theme_attr('window_inactive')
            body_attr = theme_attr('window_inactive')

        if self.drop_target_highlight:
            border_attr |= curses.A_BOLD | curses.A_REVERSE
            title_attr |= curses.A_BOLD | curses.A_REVERSE

        draw_box(stdscr, self.y, self.x, self.h, self.w, border_attr, double=True)

        # Title Bar
        title = f' {self.title} '
        # If active and has menu, show menu indicator
        if self.active and self.window_menu:
            title = ' ≡ ' + title.strip() + ' '
        
        safe_addstr(stdscr, self.y, self.x + 2, title, title_attr)
        
        # Buttons
        if self.active:
            # Right-aligned title controls: [─][□][×]
            safe_addstr(
                stdscr,
                self.y,
                self.x + self.w - self.MIN_BTN_OFFSET,
                self.TITLE_CONTROLS,
                theme_attr('window_title_invert'),
            )

        # Window Menu Bar
        if self.window_menu:
            self.window_menu.draw_bar(stdscr, self.x, self.y, self.w, self.active)
            # Separator line below menu
            sep_y = self.y + 2
            safe_addstr(stdscr, sep_y, self.x, '╟' + '─' * (self.w - 2) + '╢', border_attr)

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
                safe_addstr(stdscr, by + i, sb_x, ch, theme_attr('scrollbar'))

    def draw(self, stdscr):
        """Draw the window."""
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        self.draw_body(stdscr, body_attr)
        
        # Draw window menu dropdown on top
        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def handle_click(self, mx, my):
        """Default click handler for basic windows."""
        return None

    def handle_key(self, key):
        """Default key handler: vertical scrolling for simple windows."""
        if key in (curses.KEY_UP, curses.KEY_PPAGE):
            self.scroll_up()
        elif key in (curses.KEY_DOWN, curses.KEY_NPAGE):
            self.scroll_down()
        return None

    def handle_scroll(self, direction, steps=1):
        """Default scroll handler used by mouse wheel routing."""
        count = max(1, steps)
        if direction == 'up':
            for _ in range(count):
                self.scroll_up()
        elif direction == 'down':
            for _ in range(count):
                self.scroll_down()

    def scroll_up(self):
        if self.scroll_offset > 0:
            self.scroll_offset -= 1

    def scroll_down(self):
        _, _, _, bh = self.body_rect()
        if self.scroll_offset < len(self.content) - bh:
            self.scroll_offset += 1

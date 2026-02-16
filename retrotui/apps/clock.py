"""Clock and calendar widget window."""

import calendar
import curses
from datetime import datetime

from ..core.actions import ActionResult, ActionType, AppAction
from ..ui.menu import WindowMenu
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr


class ClockCalendarWindow(Window):
    """Small widget with digital clock and ASCII month calendar."""

    def __init__(self, x, y, w, h):
        super().__init__("Clock / Calendar", x, y, max(32, w), max(13, h), content=[], resizable=False)
        self.always_on_top = True
        self.chime_enabled = False
        self.week_starts_sunday = False
        self._last_chime_hour = None
        self.window_menu = WindowMenu(
            {
                "Options": [
                    ("Always on Top   T", "clk_top"),
                    ("Hourly Chime    B", "clk_chime"),
                    ("Week Starts Sun S", "clk_week"),
                    ("-------------", None),
                    ("Close           Q", "clk_close"),
                ]
            }
        )

    def _maybe_chime(self, now):
        if not self.chime_enabled:
            return
        if now.minute != 0:
            return
        current_hour = (now.year, now.month, now.day, now.hour)
        if current_hour == self._last_chime_hour:
            return
        self._last_chime_hour = current_hour
        beeper = getattr(curses, "beep", None)
        if callable(beeper):
            try:
                beeper()
            except Exception:
                pass

    def _execute_menu_action(self, action):
        if action == "clk_top":
            self.always_on_top = not self.always_on_top
            return None
        if action == "clk_chime":
            self.chime_enabled = not self.chime_enabled
            return None
        if action == "clk_week":
            self.week_starts_sunday = not self.week_starts_sunday
            return None
        if action == "clk_close":
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

    def _month_lines(self, now):
        """Return ASCII calendar lines honoring first weekday preference."""
        first_weekday = calendar.SUNDAY if self.week_starts_sunday else calendar.MONDAY
        text_calendar = calendar.TextCalendar(firstweekday=first_weekday)
        return text_calendar.formatmonth(now.year, now.month).splitlines()

    def draw(self, stdscr):
        """Draw digital clock and month calendar."""
        if not self.visible:
            return

        now = datetime.now()
        self._maybe_chime(now)

        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        if bh <= 0 or bw <= 0:
            return

        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, " " * bw, body_attr)

        time_label = now.strftime("%H:%M:%S")
        date_label = now.strftime("%A, %Y-%m-%d")
        safe_addstr(stdscr, by, bx, time_label.center(bw)[:bw], theme_attr("menubar"))
        safe_addstr(stdscr, by + 1, bx, date_label.center(bw)[:bw], body_attr | curses.A_BOLD)

        month_lines = self._month_lines(now)
        max_cal_rows = max(0, bh - 4)
        for i, line in enumerate(month_lines[:max_cal_rows]):
            safe_addstr(stdscr, by + 2 + i, bx, line.center(bw)[:bw], body_attr)

        top_state = "ON" if self.always_on_top else "OFF"
        chime_state = "ON" if self.chime_enabled else "OFF"
        week_state = "SUN" if self.week_starts_sunday else "MON"
        status = f"T top:{top_state} | B chime:{chime_state} | S week:{week_state} | Q close"
        safe_addstr(stdscr, by + bh - 1, bx, status[:bw].ljust(bw), theme_attr("status"))

        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def handle_click(self, mx, my, bstate=None):
        """Handle window-menu clicks."""
        _ = bstate
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if action:
                    return self._execute_menu_action(action)
        return None

    def handle_key(self, key):
        """Handle keyboard shortcuts."""
        key_code = normalize_key_code(key)

        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self._execute_menu_action(action)
            return None

        if key_code in (ord("t"), ord("T")):
            self.always_on_top = not self.always_on_top
        elif key_code in (ord("b"), ord("B")):
            self.chime_enabled = not self.chime_enabled
        elif key_code in (ord("s"), ord("S")):
            self.week_starts_sunday = not self.week_starts_sunday
        elif key_code in (ord("q"), ord("Q")):
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

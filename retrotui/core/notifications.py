"""Toast notification system for RetroTUI."""

import logging
import time
from dataclasses import dataclass, field

LOGGER = logging.getLogger(__name__)

TOAST_WIDTH = 40
TOAST_DISPLAY_SECONDS = 4.0
TOAST_MAX_VISIBLE = 3
TOAST_RIGHT_MARGIN = 2
TOAST_TOP_MARGIN = 2  # below menu bar
TOAST_MAX_QUEUE = 20


@dataclass
class Toast:
    """One notification toast."""

    title: str
    message: str
    created_at: float = field(default_factory=time.monotonic)
    duration: float = TOAST_DISPLAY_SECONDS
    level: str = "info"  # "info", "success", "warning", "error"

    @property
    def expired(self):
        return time.monotonic() - self.created_at >= self.duration


class NotificationManager:
    """Manages toast notifications displayed in the top-right desktop area.

    Integrates with EventBus by subscribing to the ``notification`` topic.
    Can also be called directly via :meth:`notify`.
    """

    def __init__(self, event_bus=None):
        self._toasts = []
        self._bus = event_bus
        self._unsub = None
        if event_bus is not None:
            self._unsub = event_bus.subscribe(
                "notification",
                self._on_notification_event,
                subscriber_id="notification_manager",
            )

    def _on_notification_event(self, event):
        data = event.data
        if data is None:
            return
        if isinstance(data, str):
            self.notify(data)
        elif isinstance(data, dict):
            self.notify(
                message=data.get("message", ""),
                title=data.get("title", ""),
                level=data.get("level", "info"),
                duration=data.get("duration", TOAST_DISPLAY_SECONDS),
            )

    def notify(self, message, title="", level="info", duration=TOAST_DISPLAY_SECONDS):
        """Add a toast notification."""
        toast = Toast(
            title=title or level.capitalize(),
            message=message,
            level=level,
            duration=duration,
        )
        self._toasts.append(toast)
        if len(self._toasts) > TOAST_MAX_QUEUE:
            self._toasts = self._toasts[-TOAST_MAX_QUEUE:]

    def tick(self):
        """Remove expired toasts.  Returns True if any were removed."""
        before = len(self._toasts)
        self._toasts = [t for t in self._toasts if not t.expired]
        return before != len(self._toasts)

    @property
    def visible_toasts(self):
        """Return up to TOAST_MAX_VISIBLE most recent non-expired toasts."""
        active = [t for t in self._toasts if not t.expired]
        return active[-TOAST_MAX_VISIBLE:]

    @property
    def has_visible(self):
        return any(not t.expired for t in self._toasts)

    def draw(self, stdscr, frame_w, frame_h):
        """Render visible toasts in the top-right corner."""
        from ..utils import safe_addstr
        from ..constants import C_WIN_BORDER, C_WIN_TITLE

        toasts = self.visible_toasts
        if not toasts:
            return

        try:
            import curses
            border_attr = curses.color_pair(C_WIN_BORDER)
            title_attr = curses.color_pair(C_WIN_TITLE) | curses.A_BOLD
        except Exception:
            border_attr = 0
            title_attr = 0

        x = frame_w - TOAST_WIDTH - TOAST_RIGHT_MARGIN
        if x < 0:
            return

        y = TOAST_TOP_MARGIN
        w = TOAST_WIDTH
        inner = w - 2

        for toast in toasts:
            if y + 4 > frame_h:
                break
            top = "+" + "-" * inner + "+"
            safe_addstr(stdscr, y, x, top, border_attr)
            y += 1
            title_line = (" " + toast.title)[:inner].ljust(inner)
            safe_addstr(stdscr, y, x, "|" + title_line + "|", title_attr)
            y += 1
            msg_line = (" " + toast.message)[:inner].ljust(inner)
            safe_addstr(stdscr, y, x, "|" + msg_line + "|", border_attr)
            y += 1
            bot = "+" + "-" * inner + "+"
            safe_addstr(stdscr, y, x, bot, border_attr)
            y += 1

    def cleanup(self):
        """Unsubscribe from bus and clear toasts."""
        if self._unsub:
            self._unsub()
            self._unsub = None
        self._toasts.clear()

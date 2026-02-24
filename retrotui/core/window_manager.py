"""Window lifecycle management for RetroTUI."""
import logging

from ..constants import TASKBAR_TITLE_MAX_LEN, BOTTOM_BARS_HEIGHT

LOGGER = logging.getLogger(__name__)
_WINDOW_CLOSE_HOOK_ERRORS = (
    ArithmeticError,
    AssertionError,
    AttributeError,
    LookupError,
    NameError,
    OSError,
    RuntimeError,
    SyntaxError,
    TypeError,
    ValueError,
)


class WindowManager:
    """Manages the window list, z-order, activation, and spawning."""

    def __init__(self, app):
        self._app = app
        self.windows = []
        self._layers_dirty = True

    # ------------------------------------------------------------------
    # Window list / activation
    # ------------------------------------------------------------------

    def set_active_window(self, win):
        """Set a window as active (bring to front)."""
        for w in self.windows:
            w.active = False
        win.active = True
        # Move to top of its layer.
        self.windows.remove(win)
        self._layers_dirty = True
        self.normalize_window_layers()
        if win.always_on_top:
            self.windows.append(win)
            return

        insert_at = len(self.windows)
        for i, candidate in enumerate(self.windows):
            if candidate.always_on_top:
                insert_at = i
                break
        self.windows.insert(insert_at, win)

    def normalize_window_layers(self):
        """Keep always-on-top windows above regular windows preserving order."""
        if not self._layers_dirty:
            return
        normal = [w for w in self.windows if not w.always_on_top]
        pinned = [w for w in self.windows if w.always_on_top]
        self.windows = normal + pinned
        self._layers_dirty = False

    def close_window(self, win):
        """Close a window."""
        if getattr(self._app, "_active_window_menu_owner", None) is win:
            menu = getattr(win, "window_menu", None)
            if menu is not None:
                menu.active = False
            self._app._active_window_menu_owner = None
        closer = getattr(win, 'close', None)
        if callable(closer):
            try:
                closer()
            except _WINDOW_CLOSE_HOOK_ERRORS:  # pragma: no cover - defensive window cleanup path
                LOGGER.debug('Window close hook failed for %r', win, exc_info=True)
        self.windows.remove(win)
        self._layers_dirty = True
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

    def get_active_window(self):
        """Return the active window, if any."""
        return next((w for w in self.windows if w.active), None)

    # ------------------------------------------------------------------
    # Window spawning
    # ------------------------------------------------------------------

    def _spawn_window(self, win):
        """Append a window and make it active."""
        self.windows.append(win)
        self._layers_dirty = True
        self.set_active_window(win)

    def _next_window_offset(self, base_x, base_y, step_x=2, step_y=1):
        """Return staggered window coordinates based on open window count."""
        count = len(self.windows)
        return base_x + count * step_x, base_y + count * step_y

    # ------------------------------------------------------------------
    # Taskbar
    # ------------------------------------------------------------------

    def handle_taskbar_click(self, mx, my):
        """Handle click on taskbar row. Returns True if handled."""
        h, w = self._app.stdscr.getmaxyx()
        taskbar_y = h - BOTTOM_BARS_HEIGHT
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
                self._app.set_active_window(win)
                return True
            x += btn_w + 1
        return False

"""Window lifecycle management for RetroTUI."""
import logging

LOGGER = logging.getLogger(__name__)


class WindowManager:
    """Manages the window list, z-order, activation, and spawning."""

    def __init__(self, app):
        self._app = app
        self.windows = []

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

    def get_active_window(self):
        """Return the active window, if any."""
        return next((w for w in self.windows if w.active), None)

    # ------------------------------------------------------------------
    # Window spawning
    # ------------------------------------------------------------------

    def _spawn_window(self, win):
        """Append a window and make it active."""
        self.windows.append(win)
        self.set_active_window(win)

    def _next_window_offset(self, base_x, base_y, step_x=2, step_y=1):
        """Return staggered window coordinates based on open window count."""
        count = len(self.windows)
        return base_x + count * step_x, base_y + count * step_y

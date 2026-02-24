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
        self._taskbar_cache = {"key": None, "buttons": ()}
        self._window_stats_cache = {"cycle": None, "stats": None}

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

    def _current_render_cycle(self):
        return getattr(self._app, "_render_cycle_id", None)

    def window_stats(self):
        """Return cached window stats for current render cycle when available."""
        cycle = self._current_render_cycle()
        cached_cycle = self._window_stats_cache.get("cycle")
        cached_stats = self._window_stats_cache.get("stats")
        if cycle is not None and cached_cycle == cycle and isinstance(cached_stats, dict):
            return cached_stats

        windows = list(self.windows)
        minimized = []
        visible_count = 0
        for win in windows:
            if getattr(win, "visible", False):
                visible_count += 1
            if getattr(win, "minimized", False):
                label = str(getattr(win, "title", ""))[:TASKBAR_TITLE_MAX_LEN]
                minimized.append((label, win))

        stats = {
            "total": len(windows),
            "visible": visible_count,
            "minimized": tuple(minimized),
            "minimized_labels": tuple(label for label, _ in minimized),
        }
        if cycle is not None:
            self._window_stats_cache["cycle"] = cycle
            self._window_stats_cache["stats"] = stats
        return stats

    def taskbar_buttons(self, width):
        """Return cached taskbar button layout for minimized windows.

        Each entry is `(start_x, end_x, label, win)` where `end_x` is exclusive.
        """
        stats = self.window_stats()
        cycle = self._current_render_cycle()
        key = (int(width), cycle, stats.get("minimized"))
        if cycle is None:
            key = (int(width), stats.get("minimized"))
        cached_key = self._taskbar_cache.get("key")
        if cached_key == key:
            return self._taskbar_cache.get("buttons", ())

        x = 1
        buttons = []
        for label, win in stats.get("minimized", ()):
            btn_w = len(label) + 2  # [label]
            if x + btn_w > width:
                break
            buttons.append((x, x + btn_w, label, win))
            x += btn_w + 1

        result = tuple(buttons)
        self._taskbar_cache["key"] = key
        self._taskbar_cache["buttons"] = result
        return result

    def handle_taskbar_click(self, mx, my):
        """Handle click on taskbar row. Returns True if handled."""
        h, w = self._app.stdscr.getmaxyx()
        taskbar_y = h - BOTTOM_BARS_HEIGHT
        if my != taskbar_y:
            return False
        buttons = self.taskbar_buttons(w)
        if not buttons:
            return False
        for start_x, end_x, _label, win in buttons:
            if start_x <= mx < end_x:
                win.toggle_minimize()
                self._app.set_active_window(win)
                return True
        return False

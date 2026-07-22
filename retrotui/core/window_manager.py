"""Window lifecycle management for RetroTUI."""
import logging

from ..constants import TASKBAR_TITLE_MAX_LEN, BOTTOM_BARS_HEIGHT
from ..utils import clip_text_columns, text_display_width

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
        # Single active-window pointer. ``get_active_window`` is on
        # the per-event hot path (mouse + key dispatch), and a linear
        # ``next((w for w in self.windows if w.active), None)`` scan
        # costs O(n) per call.
        self._active_window = None

    def _event_bus(self):
        """Return the app's public lifecycle bus, if an app is attached."""
        if self._app is None:
            return None
        return getattr(self._app, "event_bus", None)

    def _emit_event(self, topic, win):
        """Publish a window lifecycle event on the app's public bus."""
        bus = self._event_bus()
        if bus is not None:
            bus.publish(topic, data={
                "window_id": getattr(win, "id", None),
                "title": getattr(win, "title", ""),
            })

    # ------------------------------------------------------------------
    # Window list / activation
    # ------------------------------------------------------------------

    def set_active_window(self, win):
        """Set a registered window as active (bring to front).

        Activation is not a spawn path. Stale references are rejected without
        mutating focus or registering a window that skipped lifecycle hooks.
        """
        if win not in self.windows:
            LOGGER.warning("Ignoring activation request for unregistered window %r", win)
            return False

        # Deactivate only the previous active window (O(1) via the
        # cached pointer) instead of walking every window in the list.
        # Also pick up a stale active flag in case the pointer is
        # out-of-sync (e.g. tests poke ``active`` directly).
        previous = self._active_window
        if previous is None:
            for w in self.windows:
                if getattr(w, "active", False):
                    w.active = False
        elif previous is not win:
            previous.active = False
        win.active = True
        self._active_window = win
        # Move to top of its layer. Guard the membership check so a
        # stale reference (closed window, dangling test stub) cannot
        # raise ``ValueError`` from ``list.remove``.
        if win in self.windows:
            self.windows.remove(win)
        self._layers_dirty = True
        self.normalize_window_layers()
        if getattr(win, "always_on_top", False):
            self.windows.append(win)
            self._emit_event("window.focused", win)
            return True

        insert_at = len(self.windows)
        for i, candidate in enumerate(self.windows):
            if getattr(candidate, "always_on_top", False):
                insert_at = i
                break
        self.windows.insert(insert_at, win)
        self._emit_event("window.focused", win)
        return True

    def normalize_window_layers(self):
        """Keep always-on-top windows above regular windows preserving order."""
        if not self._layers_dirty:
            return
        normal = [w for w in self.windows if not getattr(w, "always_on_top", False)]
        pinned = [w for w in self.windows if getattr(w, "always_on_top", False)]
        self.windows = normal + pinned
        self._layers_dirty = False

    def close_window(self, win, *, force=False):
        """Request and, when authorized, close *win*.

        Returns True only when the window was removed. ``force=True`` is
        reserved for shutdown and bypasses the interactive close request.
        """
        if win not in self.windows:
            return False

        if not force:
            requester = getattr(win, "request_close", None)
            if callable(requester):
                try:
                    request_result = requester()
                except Exception:  # Window/plugin boundary: isolate extension code.
                    LOGGER.debug('Window close request failed for %r', win, exc_info=True)
                    return False
                if request_result is False:
                    return False
                if request_result is not None and request_result is not True:
                    dispatcher = getattr(self._app, "_dispatch_window_result", None)
                    if callable(dispatcher):
                        dispatcher(request_result, win)
                    return False

        if getattr(self._app, "_active_window_menu_owner", None) is win:
            menu = getattr(win, "window_menu", None)
            if menu is not None:
                menu.active = False
            self._app._active_window_menu_owner = None

        closer = getattr(win, 'close', None)
        if callable(closer):
            try:
                close_result = closer()
            except Exception:  # Window/plugin boundary: isolate extension code.
                LOGGER.debug('Window close hook failed for %r', win, exc_info=True)
                return False
            if close_result is False:
                LOGGER.warning('Window close was not verified for %r; keeping it registered', win)
                return False
        if win in self.windows:
            self.windows.remove(win)
        if self._active_window is win:
            self._active_window = None
        self._layers_dirty = True
        self._emit_event("window.closed", win)
        self._activate_last_visible_window()
        return True

    def _activate_last_visible_window(self):
        """Activate topmost visible window after z-order/window-list changes."""
        previous = self._active_window
        if previous is not None:
            previous.active = False
            self._active_window = None
        for candidate in reversed(self.windows):
            if getattr(candidate, 'visible', True):
                candidate.active = True
                self._active_window = candidate
                return candidate
        return None

    def get_active_window(self):
        """Return a visible active window, repairing hidden focus if needed.

        A component isolated after repeated draw failures may remain in the
        window list. It must not keep keyboard focus after becoming invisible.
        A list replacement with no active window remains a legitimate no-focus
        state and must not activate a window as a side effect.
        """
        cached = self._active_window
        if (
            cached is not None
            and getattr(cached, "active", False)
            and getattr(cached, "visible", True)
            and cached in self.windows
        ):
            return cached

        repair_hidden_focus = False
        if (
            cached is not None
            and cached in self.windows
            and getattr(cached, "active", False)
            and not getattr(cached, "visible", True)
        ):
            cached.active = False
            repair_hidden_focus = True
        self._active_window = None

        for window in self.windows:
            if not getattr(window, "active", False):
                continue
            if getattr(window, "visible", True):
                self._active_window = window
                return window
            window.active = False
            repair_hidden_focus = True

        if repair_hidden_focus:
            return self._activate_last_visible_window()
        return None

    # ------------------------------------------------------------------
    # Window spawning
    # ------------------------------------------------------------------

    def _spawn_window(self, win):
        """Register a window exactly once and make it active."""
        if win in self.windows:
            LOGGER.warning("Ignoring duplicate spawn for window %r", win)
            return False
        self.windows.append(win)
        self._layers_dirty = True
        self._emit_event("window.opened", win)
        # Let windows subscribe to the event bus (if they opt in).
        bus_sub = getattr(win, "subscribe_to_bus", None)
        if callable(bus_sub):
            bus = self._event_bus()
            if bus is not None:
                bus_sub(bus)
        self.set_active_window(win)
        return True

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
                label = clip_text_columns(
                    getattr(win, "title", ""),
                    TASKBAR_TITLE_MAX_LEN,
                    suffix="…",
                )
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

    def _taskbar_row(self, height):
        return height - BOTTOM_BARS_HEIGHT if BOTTOM_BARS_HEIGHT else 0

    def _taskbar_bounds(self, width):
        if BOTTOM_BARS_HEIGHT:
            return 1, width

        menu = getattr(self._app, "menu", None)
        start_x = 1
        menu_right = getattr(menu, "menu_items_right_x", None)
        if callable(menu_right):
            try:
                start_x = max(start_x, int(menu_right()) + 2)
            except (TypeError, ValueError):
                start_x = 1

        end_x = width
        reserved = getattr(menu, "right_reserved_start_x", None)
        if callable(reserved):
            try:
                end_x = min(end_x, max(start_x, int(reserved(width)) - 1))
            except (TypeError, ValueError):
                end_x = width
        return start_x, end_x

    def taskbar_buttons(self, width, *, start_x=None, end_x=None):
        """Return cached taskbar button layout for minimized windows.

        Each entry is `(start_x, end_x, label, win)` where `end_x` is exclusive.
        """
        if start_x is None or end_x is None:
            start_x, end_x = self._taskbar_bounds(width)
        stats = self.window_stats()
        cycle = self._current_render_cycle()
        key = (int(width), int(start_x), int(end_x), cycle, stats.get("minimized"))
        if cycle is None:
            key = (int(width), int(start_x), int(end_x), stats.get("minimized"))
        cached_key = self._taskbar_cache.get("key")
        if cached_key == key:
            return self._taskbar_cache.get("buttons", ())

        x = int(start_x)
        buttons = []
        for label, win in stats.get("minimized", ()):
            btn_w = text_display_width(label) + 2  # [label]
            if x + btn_w > end_x:
                break
            buttons.append((x, x + btn_w, label, win))
            x += btn_w + 1

        result = tuple(buttons)
        self._taskbar_cache["key"] = key
        self._taskbar_cache["buttons"] = result
        return result

    def handle_taskbar_click(self, mx, my):
        """Handle click on taskbar buttons. Returns True if handled."""
        h, w = self._app.stdscr.getmaxyx()
        taskbar_y = self._taskbar_row(h)
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

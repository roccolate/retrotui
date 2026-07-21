"""Drag-and-drop manager for file operations between windows."""
import curses
import logging


LOGGER = logging.getLogger(__name__)


class DragDropManager:
    """Manages file drag-and-drop state between windows."""

    def __init__(self, app):
        self._app = app
        self.payload = None
        self.source_window = None
        self.target_window = None

    def clear_pending_file_drags(self):
        """Clear pending drag candidates exposed by file-manager-like windows."""
        for win in getattr(self._app, 'windows', []):
            clearer = getattr(win, 'clear_pending_drag', None)
            if callable(clearer):
                clearer()

    def set_drag_target(self, target):
        """Track active drop target and update per-window highlight flags."""
        if target is self.target_window:
            return

        previous = self.target_window
        if previous is not None:
            setattr(previous, 'drop_target_highlight', False)

        if target is not None:
            setattr(target, 'drop_target_highlight', True)

        self.target_window = target

    def clear_state(self):
        """Reset drag payload/source/target state."""
        self.payload = None
        self.source_window = None
        self.set_drag_target(None)

    @staticmethod
    def supports_file_drop_target(win):
        """Return True when window can accept dropped file paths."""
        return callable(getattr(win, 'open_path', None)) or callable(
            getattr(win, 'accept_dropped_path', None)
        )

    def find_drop_target_window(self, mx, my):
        """Return topmost visible drop target under pointer, excluding source window."""
        for win in reversed(getattr(self._app, 'windows', [])):
            if not getattr(win, 'visible', False):
                continue
            contains = getattr(win, 'contains', None)
            if not callable(contains) or not contains(mx, my):
                continue
            if win is self.source_window:
                return None
            if self.supports_file_drop_target(win):
                return win
            return None
        return None

    def dispatch_drop(self, target, payload):
        """Apply one dropped payload to target window and dispatch returned action."""
        if target is None or not isinstance(payload, dict):
            return
        if payload.get('type') != 'file_path':
            return
        path = payload.get('path')
        if not path:
            return

        result = None
        accept_path = getattr(target, 'accept_dropped_path', None)
        open_path = getattr(target, 'open_path', None)
        # ``accept_dropped_path`` is the explicit drop capability.  A target
        # such as File Manager may also expose ``open_path`` for navigation;
        # using the generic opener first would turn a copy operation into an
        # unrelated directory change.
        #
        # Isolate drop-target handlers so a buggy target can't kill the
        # mouse-event loop. ``FileNotFoundError`` and ``PermissionError``
        # are common when the user drops a path the target cannot accept;
        # we log them as info rather than tracebacks.
        try:
            if callable(accept_path):
                result = accept_path(path)
            elif callable(open_path):
                result = open_path(path)
        except (FileNotFoundError, PermissionError, IsADirectoryError) as exc:
            LOGGER.info(
                "Drop target %r could not accept %r: %s",
                target, path, exc,
            )
            return
        except Exception:
            LOGGER.debug(
                "Unhandled exception in drop target %r for %r",
                target, path, exc_info=True,
            )
            return

        if result is not None:
            dispatcher = getattr(self._app, '_dispatch_window_result', None)
            if callable(dispatcher):
                try:
                    dispatcher(result, target)
                except Exception:
                    LOGGER.debug(
                        "Drop target %r produced an unhandled ActionResult",
                        target, exc_info=True,
                    )

    def _notify_outside_drop(self, payload):
        """Surface a short toast when a file drop lands on no target."""
        if not isinstance(payload, dict):
            return
        path = payload.get('path')
        if not path:
            return
        notify = getattr(self._app, 'notify', None)
        if callable(notify):
            try:
                notify(
                    f'Dropped "{path}" outside any window.',
                    title="Drag & Drop",
                    level="info",
                )
                return
            except Exception:
                LOGGER.debug("notify() failed for outside drop", exc_info=True)
        # Fall back to the bus if direct notify is not available.
        bus = getattr(self._app, '_event_bus', None)
        publish = getattr(bus, 'publish', None) if bus is not None else None
        if callable(publish):
            try:
                publish('notification', data={
                    'title': 'Drag & Drop',
                    'message': f'Dropped "{path}" outside any window.',
                    'level': 'info',
                })
            except Exception:
                LOGGER.debug(
                    "bus.publish('notification') failed for outside drop",
                    exc_info=True,
                )

    def handle_mouse(self, mx, my, bstate, norm=None):
        """Handle file drag-and-drop between windows. Returns True if event was consumed."""
        report_flag = getattr(curses, 'REPORT_MOUSE_POSITION', 0)
        pressed_flag = getattr(curses, 'BUTTON1_PRESSED', 0)

        if norm is not None:
            is_motion = bool(norm.get('is_motion'))
            button_down = bool(norm.get('button1_down'))
            is_release_like = bool(norm.get('button1_released'))
            if not is_release_like and not is_motion:
                is_release_like = bool(norm.get('button1_clicked') or norm.get('button1_double'))
            stop_drag = is_release_like
        else:
            is_motion = bool(bstate & report_flag)
            button_down = bool((bstate & pressed_flag) or getattr(self._app, 'button1_pressed', False))
            stop_drag = bool(bstate & getattr(curses, 'BUTTON1_RELEASED', 0))
            if not stop_drag:
                inferred_stop = getattr(self._app, 'stop_drag_flags', 0) & ~pressed_flag & ~report_flag
                stop_drag = bool(bstate & inferred_stop)

        move_drag = is_motion and button_down

        if self.payload is not None:
            if stop_drag:
                target = self.find_drop_target_window(mx, my)
                self.dispatch_drop(target, self.payload)
                if target is None:
                    self._notify_outside_drop(self.payload)
                self.clear_state()
                self.clear_pending_file_drags()
                return True
            if move_drag:
                self.set_drag_target(self.find_drop_target_window(mx, my))
                return True
            return True

        if stop_drag:
            self.clear_pending_file_drags()
            self.set_drag_target(None)
            return False

        if not move_drag:
            return False

        for win in reversed(getattr(self._app, 'windows', [])):
            consumer = getattr(win, 'consume_pending_drag', None)
            if not callable(consumer):
                continue
            payload = consumer(mx, my, bstate)
            if payload is None:
                continue
            self.payload = payload
            self.source_window = win
            self.set_drag_target(self.find_drop_target_window(mx, my))
            return True
        return False

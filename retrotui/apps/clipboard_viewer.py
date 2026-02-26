"""Clipboard Viewer window (minimal for tests)."""
from __future__ import annotations

import curses
from typing import List

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr
from ..core.clipboard import paste_text, copy_text, clear_clipboard
from ..constants import _CURSES_ERROR
_OPTIONAL_PYPERCLIP_IMPORT_ERRORS = (
    ImportError,
    ModuleNotFoundError,
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_CLIPBOARD_THEME_ERRORS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)
_CLIPBOARD_SYNC_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_KEYMAP_RESOLVE_ERRORS = (
    ImportError,
    ModuleNotFoundError,
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
try:
    import pyperclip
except _OPTIONAL_PYPERCLIP_IMPORT_ERRORS:
    pyperclip = None


class ClipboardViewerWindow(Window):
    def __init__(self, x, y, w, h, history_size=10):
        super().__init__("Clipboard", x, y, max(30, w), max(10, h), content=[], resizable=False)
        self.history_size = history_size
        self.history: List[str] = []
        self.selected_index = 0
        self._unsub_clipboard = None
        self._refresh_from_clipboard()

    def subscribe_to_bus(self, event_bus):
        """Subscribe to clipboard changes via the event bus."""
        self._unsub_clipboard = event_bus.subscribe(
            "clipboard.changed",
            self._on_clipboard_changed,
            subscriber_id=f"clipboard_viewer_{self.id}",
        )

    def _on_clipboard_changed(self, event):
        """React to clipboard.changed events from the bus."""
        data = event.data
        if not isinstance(data, dict):
            return
        text = data.get("text", "")
        if text and (not self.history or self.history[0] != text):
            self.history.insert(0, text)
            self.history = self.history[: self.history_size]

    def _refresh_from_clipboard(self):
        text = paste_text(sync_system=False)
        if text and (not self.history or self.history[0] != text):
            self.history.insert(0, text)
            self.history = self.history[: self.history_size]

    def close(self):
        """Unsubscribe from the event bus on close."""
        if self._unsub_clipboard:
            self._unsub_clipboard()
            self._unsub_clipboard = None

    def draw(self, stdscr):
        if not self.visible:
            return
        # Poll system clipboard as fallback — the bus only fires for internal
        # copies; external clipboard changes (other apps) need polling.
        self._refresh_from_clipboard()
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        for i, item in enumerate(self.history[: bh]):
            attr = body_attr
            if i == self.selected_index:
                try:
                    sel_attr = theme_attr("selected")
                    # combine, but fall back to body_attr if theme_attr is not available
                    attr = body_attr | (sel_attr or 0)
                except _CLIPBOARD_THEME_ERRORS:
                    attr = body_attr
            safe_addstr(stdscr, by + i, bx, item[:bw].ljust(bw), attr)
        if not self.history:
            safe_addstr(stdscr, by, bx, "<clipboard empty>"[:bw], body_attr)

    def handle_click(self, mx, my, bstate=None):
        bx, by, bw, bh = self.body_rect()
        if not (by <= my < by + bh):
            return None
        idx = my - by
        if 0 <= idx < len(self.history):
            copy_text(self.history[idx])
            if pyperclip:
                try:
                    pyperclip.copy(self.history[idx])
                except _CLIPBOARD_SYNC_ERRORS:
                    pass
            # update selection to clicked item
            self.selected_index = idx
        return None

    def handle_key(self, key):
        # 'c' clears clipboard
        if getattr(key, '__int__', None) and int(key) == ord('c'):
            clear_clipboard()
            self.history = []
            self.selected_index = 0
        # 'y' yank top history to system clipboard if available
        if getattr(key, '__int__', None) and int(key) == ord('y') and self.history:
            if pyperclip:
                try:
                    pyperclip.copy(self.history[0])
                except _CLIPBOARD_SYNC_ERRORS:
                    pass
        # navigation: up/down and enter to copy
        if getattr(key, '__int__', None):
            k = int(key)
            try:
                import curses as _c

                KEY_UP = _c.KEY_UP
                KEY_DOWN = _c.KEY_DOWN
            except _KEYMAP_RESOLVE_ERRORS:
                KEY_UP = -1
                KEY_DOWN = -2

            if k in (KEY_UP, ord('k')):
                if self.history:
                    self.selected_index = max(0, self.selected_index - 1)
            if k in (KEY_DOWN, ord('j')):
                if self.history:
                    self.selected_index = min(len(self.history) - 1, self.selected_index + 1)
            # Enter/Return to copy selected
            if k in (10, 13):
                if self.history and 0 <= self.selected_index < len(self.history):
                    copy_text(self.history[self.selected_index])
                    if pyperclip:
                        try:
                            pyperclip.copy(self.history[self.selected_index])
                        except _CLIPBOARD_SYNC_ERRORS:
                            pass
        return None

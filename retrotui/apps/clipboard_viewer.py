"""Clipboard Viewer window (minimal for tests)."""
from __future__ import annotations

import curses
from typing import List

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr, normalize_key_code
from ..core.clipboard import paste_text, copy_text, clear_clipboard
from ..constants import _CURSES_ERROR

try:
    _KEY_UP = curses.KEY_UP
    _KEY_DOWN = curses.KEY_DOWN
except (AttributeError, _CURSES_ERROR):
    _KEY_UP = -1
    _KEY_DOWN = -2
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
    _CURSES_ERROR,
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

    def tick(self):
        """Poll system clipboard as a fallback outside the render path.

        The event bus only fires for internal copies; external clipboard
        changes (other apps) need polling.
        """
        before = self.history[:1] if self.history else None
        self._refresh_from_clipboard()
        after = self.history[:1] if self.history else None
        return before != after

    def draw(self, stdscr):
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        for i, item in enumerate(self.history[: bh]):
            attr = body_attr
            if i == self.selected_index:
                try:
                    sel_attr = theme_attr("file_selected")
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
        kc = normalize_key_code(key)
        if kc is None:
            return None
        # 'c' clears clipboard (both internal and system clipboard)
        if kc == ord('c'):
            clear_clipboard()
            if pyperclip:
                try:
                    pyperclip.copy("")
                except _CLIPBOARD_SYNC_ERRORS:
                    pass
            self.history = []
            self.selected_index = 0
        # 'y' yank top history to system clipboard if available
        if kc == ord('y') and self.history:
            if pyperclip:
                try:
                    pyperclip.copy(self.history[0])
                except _CLIPBOARD_SYNC_ERRORS:
                    pass

        if kc in (_KEY_UP, ord('k')):
            if self.history:
                self.selected_index = max(0, self.selected_index - 1)
        elif kc in (_KEY_DOWN, ord('j')):
            if self.history:
                self.selected_index = min(len(self.history) - 1, self.selected_index + 1)
        elif kc in (10, 13):
            if self.history and 0 <= self.selected_index < len(self.history):
                copy_text(self.history[self.selected_index])
                if pyperclip:
                    try:
                        pyperclip.copy(self.history[self.selected_index])
                    except _CLIPBOARD_SYNC_ERRORS:
                        pass
        return None

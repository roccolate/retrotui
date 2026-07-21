#!/usr/bin/env python3
"""Refine hardening semantics against the existing core contracts."""
from pathlib import Path


path = Path(__file__).resolve().parents[1] / "retrotui/core/window_manager.py"
text = path.read_text(encoding="utf-8")

text = text.replace(
    "LOGGER.warning('Window close hook failed for %r', win, exc_info=True)",
    "LOGGER.debug('Window close hook failed for %r', win, exc_info=True)",
    1,
)

old = '''    def get_active_window(self):
        """Return a visible active window, repairing stale focus if needed.

        A component isolated after repeated draw failures may remain in the
        window list. It must not keep keyboard focus after becoming invisible.
        """
        cached = self._active_window
        if (
            cached is not None
            and getattr(cached, "active", False)
            and getattr(cached, "visible", True)
            and cached in self.windows
        ):
            return cached

        if cached is not None and not getattr(cached, "visible", True):
            cached.active = False
        self._active_window = None

        for window in self.windows:
            if not getattr(window, "active", False):
                continue
            if getattr(window, "visible", True):
                self._active_window = window
                return window
            window.active = False

        return self._activate_last_visible_window()
'''
new = '''    def get_active_window(self):
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
'''
if new not in text:
    if old not in text:
        raise RuntimeError("patched get_active_window block changed")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

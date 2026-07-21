"""Terminal capability declarations and runtime DEC mode state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TerminalCapabilities:
    """Capabilities currently implemented by the embedded terminal.

    Keep this conservative. It documents what RetroTUI can actually honor and
    is intended to become the source for a future terminfo profile.
    """

    colors: int = 8
    alternate_screen: bool = True
    application_cursor_keys: bool = True
    bracketed_paste: bool = True
    cursor_visibility: bool = True
    sgr_mouse: bool = True


DEFAULT_TERMINAL_CAPABILITIES = TerminalCapabilities()


@dataclass(slots=True)
class TerminalModes:
    """Mutable per-session DEC private mode state."""

    cursor_visible: bool = True
    application_cursor_keys: bool = False
    bracketed_paste: bool = False
    autowrap: bool = True

    def reset(self) -> None:
        """Restore terminal modes to their power-on defaults."""
        self.cursor_visible = True
        self.application_cursor_keys = False
        self.bracketed_paste = False
        self.autowrap = True

    def set_private_mode(self, mode: int, enabled: bool) -> bool:
        """Apply one supported DEC private mode.

        Returns ``True`` when the mode is recognized. Screen and mouse modes
        remain owned by ``TerminalWindow`` because they require additional
        side effects beyond toggling a boolean.
        """
        if mode == 25:
            self.cursor_visible = enabled
            return True
        if mode == 1:
            self.application_cursor_keys = enabled
            return True
        if mode == 2004:
            self.bracketed_paste = enabled
            return True
        if mode == 7:
            self.autowrap = enabled
            return True
        return False

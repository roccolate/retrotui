"""Mixin providing shared text selection state and helpers."""


class SelectableTextMixin:
    """Mixin providing text selection state and helpers.

    Provides the three selection-state attributes and four helper methods
    that are identical across Notepad, Terminal and LogViewer windows.

    Classes that use this mixin must call ``_init_selection()`` inside
    their own ``__init__`` in order to set up the state attributes.
    """

    def _init_selection(self):
        """Initialise selection state.  Call from ``__init__``."""
        self.selection_anchor = None   # (line, col)
        self.selection_cursor = None   # (line, col)
        self._mouse_selecting = False

    def clear_selection(self):
        """Clear current text selection."""
        self.selection_anchor = None
        self.selection_cursor = None
        self._mouse_selecting = False

    def has_selection(self):
        """Return True when there is a non-empty text selection."""
        return (
            self.selection_anchor is not None
            and self.selection_cursor is not None
            and self.selection_anchor != self.selection_cursor
        )

    def _selection_bounds(self):
        """Return ordered ((line, col), (line, col)) selection bounds, or None."""
        if not self.has_selection():
            return None
        a = self.selection_anchor
        b = self.selection_cursor
        return (a, b) if a <= b else (b, a)

    def _line_selection_span(self, line_idx, line_len):
        """Return [start, end) selected columns for a buffer line, or None.

        Parameters
        ----------
        line_idx:
            Zero-based index of the buffer line being queried.
        line_len:
            Length of that line in characters (used to clamp the span).

        Returns ``None`` when the line has no selected region.
        """
        bounds = self._selection_bounds()
        if not bounds:
            return None
        (s_line, s_col), (e_line, e_col) = bounds
        if line_idx < s_line or line_idx > e_line:
            return None

        if s_line == e_line:
            start = max(0, min(line_len, s_col))
            end = max(0, min(line_len, e_col))
            if end <= start:
                return None
            return (start, end)

        if line_idx == s_line:
            start = max(0, min(line_len, s_col))
            end = line_len
            if end <= start:
                return None
            return (start, end)

        if line_idx == e_line:
            start = 0
            end = max(0, min(line_len, e_col))
            if end <= start:
                return None
            return (start, end)

        return (0, line_len)

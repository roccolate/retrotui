"""Icon position management for RetroTUI desktop icons."""
import logging
from pathlib import Path

from ..constants import (
    ICON_DEFAULT_START_X,
    ICON_DEFAULT_START_Y,
    ICON_DEFAULT_SPACING_X,
    ICON_DEFAULT_SPACING_Y,
    ICON_GRID_BOTTOM_MARGIN,
    ICON_FALLBACK_TERMINAL_HEIGHT,
    ICON_ART_HEIGHT,
)
from ..utils import text_display_width

LOGGER = logging.getLogger(__name__)

_ICON_PERSIST_ERRORS = (AttributeError, OSError, TypeError, ValueError)
_ICON_PARSE_ERRORS = (TypeError, ValueError)
_ICON_TERMINAL_SIZE_ERRORS = (AttributeError, OSError, TypeError, ValueError)


def icon_render_metrics(icon):
    """Return art lines, art height and shared Unicode-aware icon width."""
    symbol = icon.get("symbol")
    if isinstance(symbol, str) and symbol:
        art_lines = [symbol]
    else:
        art = icon.get("art", ())
        art_lines = [str(line) for line in art] if isinstance(art, (list, tuple)) else []
        if not art_lines:
            art_lines = ["[]"]

    art_width = max((text_display_width(line) for line in art_lines), default=2)
    label_width = text_display_width(icon.get("label", ""))
    slot_width = max(2, int(ICON_DEFAULT_SPACING_X) - 1)
    render_width = min(slot_width, max(2, art_width, label_width))
    render_height = max(ICON_ART_HEIGHT, len(art_lines))
    return art_lines, render_height, render_width


class IconPositionManager:
    """Manages desktop icon positions including persistence to TOML config."""

    def __init__(self, app):
        """Initialize with reference to main app for icon list access."""
        self._app = app
        self.positions = {}  # icon_key -> (x, y)

        # Desktop icon drag state
        self.dragging_icon = -1
        self.drag_offset_x = 0
        self.drag_offset_y = 0

    @staticmethod
    def _quote_toml_key(key):
        # Route through the shared helper so icon names with newlines or
        # tabs are encoded the same way as the rest of the config. The
        # inline implementation here previously skipped ``\n``/``\r``/``\t``
        # which corrupted configs whenever an icon label happened to
        # contain them.
        from ..utils import toml_basic_string
        return '"' + toml_basic_string(key) + '"'

    @staticmethod
    def _unquote_toml_key(key):
        from ..utils import decode_toml_basic_string
        if len(key) < 2 or key[0] != '"' or key[-1] != '"':
            return key
        return decode_toml_basic_string(key[1:-1])

    # ------------------------------------------------------------------
    # Icon drag helpers
    # ------------------------------------------------------------------

    @property
    def is_dragging(self):
        """Return True when a desktop icon drag is in progress."""
        return self.dragging_icon >= 0

    @staticmethod
    def _position_key_for(icon):
        """Return stable persistence key for one icon entry."""
        key = icon.get("position_key")
        if isinstance(key, str) and key.strip():
            return key.strip()
        label = icon.get("label")
        return str(label).strip()

    def start_drag(self, icon_idx, mx, my, *, frame_size=None):
        """Begin dragging icon at *icon_idx* from mouse position (mx, my).

        If a previous drag was never released (terminals that emit PRESS +
        CLICK without RELEASE), finalize it first so positions persist and
        ``is_dragging`` reflects the new drag only.
        """
        if self.is_dragging and self.dragging_icon != icon_idx:
            self.end_drag()
        self.dragging_icon = icon_idx
        self._drag_dirty = False
        ix, iy = self.get_screen_pos(icon_idx, frame_size=frame_size)
        self.drag_offset_x = mx - ix
        self.drag_offset_y = my - iy

    def update_drag(self, mx, my):
        """Update the dragged icon's position based on current mouse (mx, my)."""
        if not self.is_dragging:
            return
        icons = self._app.icons
        icon_idx = self.dragging_icon
        if not (0 <= icon_idx < len(icons)):
            return
        icon_key = self._position_key_for(icons[icon_idx])
        if not icon_key:
            return
        new_x = max(0, mx - self.drag_offset_x)
        new_y = max(0, my - self.drag_offset_y)
        previous = self.positions.get(icon_key)
        if previous != (new_x, new_y):
            self.positions[icon_key] = (new_x, new_y)
            self._drag_dirty = True

    def end_drag(self):
        """Finish the drag and persist when the icon actually moved."""
        self.dragging_icon = -1
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        # Avoid persisting config on every release (clicks that don't
        # actually move the icon should not rewrite ``config.toml``).
        if getattr(self, "_drag_dirty", False):
            self._drag_dirty = False
            try:
                self._app.persist_config()
            except _ICON_PERSIST_ERRORS:
                pass

    def load(self, cfg_path):
        """Load icon positions from config TOML under [icons] section."""
        path = Path(cfg_path)
        # Use ``read_text`` directly: ``path.exists()`` followed by
        # ``read_text`` is a TOCTOU race and the file may be deleted
        # between the two calls. ``FileNotFoundError`` is the legitimate
        # "no saved positions yet" case.
        try:
            text = path.read_text(encoding='utf-8')
        except FileNotFoundError:
            return {}
        section = None
        icons = {}
        for raw in text.splitlines():
            # Use the shared TOML-aware comment stripper so keys that
            # legitimately contain ``#`` (e.g. plugin ids like ``RPG#1``)
            # survive a round-trip. The previous naive ``split('#', 1)``
            # silently dropped any key whose value contained ``#`` even
            # when it was inside quotes.
            from .config import _strip_inline_comment
            line = _strip_inline_comment(raw).strip()
            if not line:
                continue
            if line.startswith('[') and line.endswith(']'):
                section = line[1:-1].strip()
                continue
            if section != 'icons':
                continue
            if '=' not in line:
                continue
            key, val = line.split('=', 1)
            key = self._unquote_toml_key(key.strip())
            val = val.strip().strip('"').strip("'")
            try:
                x_str, y_str = val.split(',')
                icons[key] = (int(x_str.strip()), int(y_str.strip()))
            except _ICON_PARSE_ERRORS:
                continue
        self.positions = icons
        return icons

    def save(self, cfg_path):
        """Save icon positions into the config TOML under [icons], preserving other sections."""
        from ..utils import atomic_write_text

        cfg_path = Path(cfg_path)
        existing = ''
        if cfg_path.exists():
            existing = cfg_path.read_text(encoding='utf-8')

        # Remove any existing [icons] section
        lines = existing.splitlines()
        out_lines = []
        skip = False
        for raw in lines:
            line = raw.strip()
            if line.startswith('[') and line.endswith(']'):
                sect = line[1:-1].strip()
                if sect == 'icons':
                    skip = True
                    continue
                else:
                    skip = False
            if skip:
                continue
            out_lines.append(raw)

        # Append icons section
        out_lines.append('')
        out_lines.append('[icons]')
        for name, (x, y) in sorted(self.positions.items()):
            out_lines.append(f'{self._quote_toml_key(name)} = "{x},{y}"')

        atomic_write_text(cfg_path, '\n'.join(out_lines) + '\n')

    def _read_terminal_height(self, frame_size=None):
        """Return current terminal height with a safe fallback."""
        if isinstance(frame_size, tuple) and len(frame_size) == 2:
            return frame_size[0]
        try:
            h, _ = self._app.stdscr.getmaxyx()
        except _ICON_TERMINAL_SIZE_ERRORS:
            h = ICON_FALLBACK_TERMINAL_HEIGHT
        return h

    @staticmethod
    def _grid_slot_position(index, *, terminal_height):
        """Return default desktop grid position for zero-based slot *index*."""
        start_x = ICON_DEFAULT_START_X
        start_y = ICON_DEFAULT_START_Y
        spacing_x = ICON_DEFAULT_SPACING_X
        spacing_y = ICON_DEFAULT_SPACING_Y
        max_y = terminal_height - ICON_GRID_BOTTOM_MARGIN
        icons_per_col = max(1, (max_y - start_y) // spacing_y)
        col = index // icons_per_col
        row = index % icons_per_col
        return (start_x + col * spacing_x, start_y + row * spacing_y)

    def sort_positions(self, *, frame_size=None):
        """Sort icons by label and rewrite persisted positions using default grid slots."""
        icons = list(getattr(self._app, "icons", ()) or ())
        ordered = sorted(
            enumerate(icons),
            key=lambda pair: (str(pair[1].get("label", "")).strip().lower(), pair[0]),
        )
        terminal_height = self._read_terminal_height(frame_size=frame_size)

        positions = {}
        for slot, (_index, icon) in enumerate(ordered):
            key = self._position_key_for(icon)
            if not key:
                continue
            positions[key] = self._grid_slot_position(slot, terminal_height=terminal_height)

        self.positions = positions
        try:
            self._app.persist_config()
        except _ICON_PERSIST_ERRORS:
            pass
        return positions

    def get_screen_pos(self, index, *, frame_size=None):
        """Return (x, y) for icon at index, checking persisted positions then default grid."""
        icons = self._app.icons
        if not (0 <= index < len(icons)):
            return (0, 0)

        key_label = self._position_key_for(icons[index])
        if key_label in self.positions:
            return self.positions[key_label]
        return self._grid_slot_position(
            index,
            terminal_height=self._read_terminal_height(frame_size=frame_size),
        )

    def get_icon_at(self, mx, my, *, frame_size=None):
        """Return icon index at mouse position, or -1."""
        icons = self._app.icons
        for i, icon in enumerate(icons):
            x, y = self.get_screen_pos(i, frame_size=frame_size)
            _art_lines, render_height, render_width = icon_render_metrics(icon)
            if (
                y <= my < y + render_height + 1
                and x <= mx < x + render_width
            ):
                return i
        return -1

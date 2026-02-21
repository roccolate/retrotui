"""Icon position management for RetroTUI desktop icons."""
import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


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

    # ------------------------------------------------------------------
    # Icon drag helpers
    # ------------------------------------------------------------------

    @property
    def is_dragging(self):
        """Return True when a desktop icon drag is in progress."""
        return self.dragging_icon >= 0

    def start_drag(self, icon_idx, mx, my):
        """Begin dragging icon at *icon_idx* from mouse position (mx, my)."""
        self.dragging_icon = icon_idx
        ix, iy = self.get_screen_pos(icon_idx)
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
        icon_key = icons[icon_idx].get('label')
        new_x = max(0, mx - self.drag_offset_x)
        new_y = max(0, my - self.drag_offset_y)
        self.positions[icon_key] = (new_x, new_y)

    def end_drag(self):
        """Finish the drag and persist the new icon position."""
        self.dragging_icon = -1
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        try:
            self._app.persist_config()
        except Exception:
            pass

    def load(self, cfg_path):
        """Load icon positions from config TOML under [icons] section."""
        path = Path(cfg_path)
        if not path.exists():
            return {}
        text = path.read_text(encoding='utf-8')
        section = None
        icons = {}
        for raw in text.splitlines():
            line = raw.split('#', 1)[0].strip()
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
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            try:
                x_str, y_str = val.split(',')
                icons[key] = (int(x_str.strip()), int(y_str.strip()))
            except Exception:
                continue
        self.positions = icons
        return icons

    def save(self, cfg_path):
        """Save icon positions into the config TOML under [icons], preserving other sections."""
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
            out_lines.append(f'{name} = "{x},{y}"')

        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text('\n'.join(out_lines) + '\n', encoding='utf-8', newline='\n')

    def get_screen_pos(self, index):
        """Return (x, y) for icon at index, checking persisted positions then default grid."""
        icons = self._app.icons
        if not (0 <= index < len(icons)):
            return (0, 0)

        key_label = icons[index].get('label')
        if key_label in self.positions:
            return self.positions[key_label]

        # Default vertical layout with wrapping
        start_x = 3
        start_y = 3
        spacing_x = 12
        spacing_y = 5
        
        try:
            h, _ = self._app.stdscr.getmaxyx()
        except Exception:
            h = 24
            
        max_y = h - 3
        icons_per_col = max(1, (max_y - start_y) // spacing_y)
        col = index // icons_per_col
        row = index % icons_per_col
        
        return (start_x + col * spacing_x, start_y + row * spacing_y)

    def get_icon_at(self, mx, my):
        """Return icon index at mouse position, or -1."""
        icons = self._app.icons
        for i, icon in enumerate(icons):
            x, y = self.get_screen_pos(i)
            art = icon.get('art', [])
            w = max(len(line) for line in art) if art else 8
            h = len(art) + 1  # +1 for label

            if y <= my < y + h and x <= mx < x + w:
                return i
        return -1

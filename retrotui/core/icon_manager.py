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

        # Default vertical layout
        start_x = 3
        start_y = 3
        spacing_y = 5
        return (start_x, start_y + index * spacing_y)

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

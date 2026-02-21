"""JSON Viewer plugin (example).

Loads a JSON file (path can be provided via plugin config) and pretty-prints
it. Falls back to a sample JSON if file not found.
"""
import os
import json
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


SAMPLE = {
    "name": "example",
    "items": [
        {"id": 1, "value": "foo"},
        {"id": 2, "value": "bar"}
    ],
    "meta": {"created": "2026-02-21"}
}


def _render(obj, prefix=''):
    lines = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{prefix}{k}:")
                lines.extend(_render(v, prefix + '  '))
            else:
                lines.append(f"{prefix}{k}: {v}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            lines.append(f"{prefix}- [{i}]")
            lines.extend(_render(v, prefix + '  '))
    else:
        lines.append(f"{prefix}{obj}")
    return lines


class Plugin(RetroApp):
    def __init__(self, *args, path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.path = path
        self.lines = []
        self._load()

    def _load(self):
        data = None
        if self.path and os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                data = None
        if data is None:
            data = SAMPLE
        self.lines = _render(data)

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        for i, line in enumerate(self.lines[:h]):
            safe_addstr(stdscr, y + i, x, line[:w], attr)

    def handle_key(self, key):
        if key == ord('r'):
            self._load()

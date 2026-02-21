"""Sticky Notes plugin (example)."""
import os
import json
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lines = ['']
        self._load()

    def _data_path(self):
        return os.path.expanduser('~/.config/retrotui/sticky-notes.json')

    def _load(self):
        path = self._data_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'lines' in data and isinstance(data['lines'], list):
                        self.lines = data['lines']
                    else:
                        # backward compatibility with 'note' string
                        note = data.get('note', '')
                        self.lines = note.split('\n') if note else ['']
            except Exception:
                self.lines = ['']

    def _save(self):
        path = self._data_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'lines': self.lines}, f)
        except Exception:
            pass

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        for i, line in enumerate(self.lines[:h]):
            safe_addstr(stdscr, y + i, x, line[:w], attr)

    def handle_key(self, key):
        # Controls: 'a' add line, 'd' delete last line, 'e' edit-last (append marker)
        if key == ord('a'):
            self.lines.append('')
            self._save()
        elif key == ord('d'):
            if len(self.lines) > 1:
                self.lines.pop()
                self._save()
        elif key == ord('e'):
            # Lightweight edit: append marker to last line
            self.lines[-1] = (self.lines[-1] + ' [edited]').strip()
            self._save()

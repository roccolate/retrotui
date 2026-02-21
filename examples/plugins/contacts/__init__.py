"""Contacts plugin (example)."""
import os
import json
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.contacts = []
        self.selected = 0
        self._load()

    def _data_path(self):
        return os.path.expanduser('~/.config/retrotui/contacts.json')

    def _load(self):
        path = self._data_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.contacts = json.load(f)
            except Exception:
                self.contacts = []

    def _save(self):
        path = self._data_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.contacts, f)

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        for i, c in enumerate(self.contacts[:h]):
            line = f"{c.get('name','')} {c.get('phone','')} {c.get('email','')}"
            a = attr
            if i == self.selected:
                a = theme_attr('menu_selected')
            safe_addstr(stdscr, y + i, x, line[:w], a)

    def handle_key(self, key):
        if key == ord('a'):
            # add a dummy contact for demo
            self.contacts.append({'name': 'New', 'phone': '', 'email': ''})
            self._save()
        elif key == ord('d'):
            if 0 <= self.selected < len(self.contacts):
                self.contacts.pop(self.selected)
                self.selected = max(0, self.selected - 1)
                self._save()
        elif key == ord('e'):
            # lightweight edit: append marker to name
            if 0 <= self.selected < len(self.contacts):
                c = self.contacts[self.selected]
                c['name'] = (c.get('name','') + ' [edited]').strip()
                self._save()
        elif key == ord('j'):
            self.selected = min(self.selected + 1, len(self.contacts) - 1)
        elif key == ord('k'):
            self.selected = max(self.selected - 1, 0)

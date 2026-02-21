"""Todo List plugin for RetroTUI."""
import json
import os
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.todos = []
        self.selected = 0
        self._load()

    def _data_path(self):
        return os.path.expanduser('~/.config/retrotui/todo-list.json')

    def _load(self):
        path = self._data_path()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.todos = json.load(f)
            except Exception:
                self.todos = []

    def _save(self):
        path = self._data_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.todos, f)

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        for i, todo in enumerate(self.todos[:h]):
            check = '[x]' if todo.get('done') else '[ ]'
            line = f" {check} {todo.get('text','') }"
            a = attr
            if i == self.selected:
                a = theme_attr('menu_selected')
            safe_addstr(stdscr, y + i, x, line[:w], a)

    def handle_key(self, key):
        try:
            if key == ord('j') or key == 258:  # down
                self.selected = min(self.selected + 1, len(self.todos) - 1)
            elif key == ord('k') or key == 259:  # up
                self.selected = max(self.selected - 1, 0)
            elif key == ord(' '):  # toggle
                if self.todos:
                    self.todos[self.selected]['done'] = not self.todos[self.selected].get('done')
                    self._save()
            elif key == ord('a'):  # add (simplified)
                self.todos.append({'text': f'New task {len(self.todos)+1}', 'done': False})
                self._save()
            elif key == ord('d'):  # delete
                if self.todos:
                    self.todos.pop(self.selected)
                    self.selected = min(self.selected, max(len(self.todos)-1, 0))
                    self._save()
        except Exception:
            pass

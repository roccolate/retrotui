"""DB Browser plugin (example).

Opens a SQLite file (default: ./example.db) and lists tables; shows first
few rows of selected table. Uses stdlib `sqlite3`.
"""
import os
import sqlite3
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, path='./example.db', **kwargs):
        super().__init__(*args, **kwargs)
        self.path = path
        self.tables = []
        self.selected = 0
        self.rows = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            self.tables = []
            return
        try:
            con = sqlite3.connect(self.path)
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            self.tables = [r[0] for r in cur.fetchall()]
            con.close()
        except Exception:
            self.tables = []

    def _load_rows(self, table):
        try:
            con = sqlite3.connect(self.path)
            cur = con.cursor()
            cur.execute(f'SELECT * FROM "{table}" LIMIT 10')
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            con.close()
            self.rows = [', '.join(map(str, cols))] + [', '.join(map(str, r)) for r in rows]
        except Exception:
            self.rows = ['(error reading table)']

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        mid = max(10, w // 3)
        # Left: tables
        safe_addstr(stdscr, y, x, f'DB: {self.path}'[:mid], attr)
        for i, t in enumerate(self.tables[:h-1]):
            a = attr
            if i == self.selected:
                a = theme_attr('menu_selected')
            safe_addstr(stdscr, y + 1 + i, x, t[:mid], a)

        # Right: rows
        for i, line in enumerate(self.rows[:h]):
            safe_addstr(stdscr, y + i, x + mid + 2, line[:max(0, w - mid - 3)], attr)

    def handle_key(self, key):
        if key == ord('j'):
            self.selected = min(self.selected + 1, len(self.tables) - 1)
        elif key == ord('k'):
            self.selected = max(0, self.selected - 1)
        elif key == ord('r'):
            self._load()
        elif key == ord('o'):
            if 0 <= self.selected < len(self.tables):
                self._load_rows(self.tables[self.selected])

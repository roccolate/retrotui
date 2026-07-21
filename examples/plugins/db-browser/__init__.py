"""DB Browser plugin (example).

Opens a SQLite file (default: ./example.db) and lists tables; shows first
few rows of selected table. Uses stdlib `sqlite3`.
"""
import os
import sqlite3
from contextlib import closing

from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


def _quote_identifier(name):
    return '"' + str(name).replace('"', '""') + '"'


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
            # sqlite3.Connection's context manager commits or rolls back but
            # does not close the handle. Explicit closing is required so
            # Windows can delete temporary database files immediately.
            with closing(sqlite3.connect(self.path)) as con:
                cur = con.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                self.tables = [r[0] for r in cur.fetchall()]
        except sqlite3.Error:
            self.tables = []

    def _load_rows(self, table):
        try:
            with closing(sqlite3.connect(self.path)) as con:
                cur = con.cursor()
                cur.execute(f'SELECT * FROM {_quote_identifier(table)} LIMIT 10')
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchall()
                self.rows = [', '.join(map(str, cols))] + [', '.join(map(str, r)) for r in rows]
        except sqlite3.Error:
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

"""Disk Usage plugin (example, ncdu-style)."""
import os
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


def _human(n):
    for u in ('B','K','M','G','T'):
        if abs(n) < 1024.0:
            return f"{n:3.1f}{u}"
        n /= 1024.0
    return f"{n:.1f}P"


class Plugin(RetroApp):
    def __init__(self, *args, path='.', **kwargs):
        super().__init__(*args, **kwargs)
        self.path = path
        self.entries = []  # list of (name, size)
        self._scan()

    def _scan(self):
        try:
            items = []
            with os.scandir(self.path) as it:
                for e in it:
                    try:
                        if e.is_file(follow_symlinks=False):
                            size = e.stat(follow_symlinks=False).st_size
                        elif e.is_dir(follow_symlinks=False):
                            # approximate: sum file sizes in directory (non-recursive depth-limited)
                            size = 0
                            for root, dirs, files in os.walk(e.path):
                                for f in files:
                                    try:
                                        p = os.path.join(root, f)
                                        size += os.path.getsize(p)
                                    except Exception:
                                        pass
                                # limit deep recursion to avoid long runs
                                break
                        else:
                            size = 0
                    except Exception:
                        size = 0
                    items.append((e.name, size))
            items.sort(key=lambda x: x[1], reverse=True)
            self.entries = items
        except Exception:
            self.entries = []

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        header = f"Path: {self.path}"
        safe_addstr(stdscr, y, x, header[:w], attr)
        for i, (name, size) in enumerate(self.entries[: max(0, h-1) ]):
            line = f"{_human(size):>8}  {name}"
            safe_addstr(stdscr, y + 1 + i, x, line[:w], attr)

    def handle_key(self, key):
        # 'r' refresh scan, 'o' open into directory (naive)
        if key == ord('r'):
            self._scan()
        elif key == ord('o'):
            # open first directory entry as a simple demo
            if self.entries:
                name, _ = self.entries[0]
                p = os.path.join(self.path, name)
                if os.path.isdir(p):
                    self.path = p
                    self._scan()

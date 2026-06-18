"""
Core data structures and helpers for File Manager.
"""
import os
import unicodedata

def _cell_width(ch):
    """Return terminal cell width for a single character."""
    if not ch:
        return 0
    if unicodedata.combining(ch):
        return 0
    if unicodedata.east_asian_width(ch) in ('W', 'F'):
        return 2
    return 1


def _fit_text_to_cells(text, max_cells):
    """Clip/pad text so rendered width does not exceed max_cells."""
    if max_cells <= 0:
        return ''
    out = []
    used = 0
    for ch in text:
        w = _cell_width(ch)
        if used + w > max_cells:
            break
        out.append(ch)
        used += w
    if used < max_cells:
        out.append(' ' * (max_cells - used))
    return ''.join(out)


class FileEntry:
    """Represents a file or directory entry in the file manager."""
    __slots__ = ('name', 'is_dir', 'full_path', 'size', 'display_text', 'use_unicode')

    def __init__(self, name, is_dir, full_path, size=0, use_unicode=True):
        self.name = name
        self.is_dir = is_dir
        self.full_path = full_path
        self.size = size
        self.use_unicode = use_unicode

        dir_icon = '📁' if use_unicode else '[D]'
        file_icon = '📄' if use_unicode else '[F]'
        if name == '..':
            self.display_text = f'  {dir_icon} ..'
        elif is_dir:
            self.display_text = f'  {dir_icon} {name}/'
        else:
            self.display_text = f'  {file_icon} {name:<30} {self._format_size():>8}'

    def _format_size(self):
        units = ('B', 'K', 'M', 'G', 'T')
        value = float(self.size)
        unit_index = 0
        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1
        if unit_index == 0:
            return f'{int(value)}B'
        return f'{value:.1f}{units[unit_index]}'


class PaneState:
    """Mutable state for one file-manager pane (primary or secondary).

    Holds the directory listing, selection cursor, and scroll position.
    Two ``PaneState`` instances eliminate the duplicated ``secondary_*``
    attributes that used to live directly on ``FileManagerWindow``.
    """

    __slots__ = (
        'path', 'entries', 'content', 'selected_index',
        'scroll_offset', 'error_message',
    )

    def __init__(self, path):
        self.path = path
        self.entries = []
        self.content = []
        self.selected_index = 0
        self.scroll_offset = 0
        self.error_message = None

    def navigate_to(self, path):
        real = os.path.realpath(path)
        if os.path.isdir(real):
            self.path = real

    def navigate_parent(self):
        parent = os.path.dirname(self.path)
        if parent != self.path:
            self.navigate_to(parent)

    def clamp(self):
        """Clamp selected_index and scroll_offset to valid ranges."""
        if self.entries:
            self.selected_index = min(
                self.selected_index, len(self.entries) - 1,
            )
        else:
            self.selected_index = 0
        max_scroll = max(0, len(self.entries) - 1)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

    def select_by_name(self, name, display_h):
        """Move selection to entry with *name*.  Returns True if found."""
        for i, entry in enumerate(self.entries):
            if entry.name == name:
                self.selected_index = i
                if self.selected_index >= display_h:
                    self.scroll_offset = max(
                        0, self.selected_index - display_h + 1,
                    )
                else:
                    self.scroll_offset = 0
                return True
        return False

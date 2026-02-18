"""
Core data structures and helpers for File Manager.
"""
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

        dir_icon = '[D]'
        file_icon = '[F]'
        if name == '..':
            self.display_text = f'  {dir_icon} ..'
        elif is_dir:
            self.display_text = f'  {dir_icon} {name}/'
        else:
            self.display_text = f'  {file_icon} {name:<30} {self._format_size():>8}'

    def _format_size(self):
        if self.size > 1048576:
            return f'{self.size / 1048576:.1f}M'
        elif self.size > 1024:
            return f'{self.size / 1024:.1f}K'
        else:
            return f'{self.size}B'

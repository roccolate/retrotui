"""
File preview generation logic.
"""
import os
import subprocess
import shutil
import stat
try:
    import pwd
except ImportError:
    pwd = None
from datetime import datetime
from .core import FileEntry

IMAGE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'
}

def _owner_name(uid):
    """Resolve uid to a displayable owner name."""
    if pwd is None:
        return str(uid)
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)

def get_entry_info_lines(entry):
    """Return short metadata lines for selected entry."""
    if entry is None:
        return ['Type: -', 'Name: -']
    try:
        st = os.stat(entry.full_path)
    except OSError:
        return [f'Name: {entry.name}', 'Type: unreadable']

    type_label = 'Directory' if entry.is_dir else 'File'
    if entry.name == '..':
        type_label = 'Parent'
    mode = stat.filemode(st.st_mode)
    owner = _owner_name(getattr(st, 'st_uid', 0))
    mtime = datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M')
    size = '-' if entry.is_dir else FileEntry(entry.name, False, entry.full_path, st.st_size)._format_size()
    return [
        f'Name: {entry.name}',
        f'Type: {type_label}',
        f'Size: {size}',
        f'Perm: {mode}',
        f'Owner: {owner}',
        f'Mod: {mtime}',
    ]

def _read_text_preview(path, max_lines):
    """Read preview lines from text file, safely handling binary data."""
    if max_lines <= 0:
        return []
    try:
        with open(path, 'rb') as stream:
            raw = stream.read(16 * 1024)
    except OSError:
        return ['[preview unavailable]']

    if b'\x00' in raw:
        return ['[binary file]']

    text = raw.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    if not lines:
        return ['[empty file]']
    result = [line.replace('\t', '    ') for line in lines[:max_lines]]
    if not any(result):
        return ['[empty file]']
    return result

def _detect_image_preview_backend():
    """Select available command backend for image preview."""
    if shutil.which('chafa'):
        return 'chafa'
    if shutil.which('timg'):
        return 'timg'
    return None

def _read_image_preview(path, max_lines, max_cols):
    """Read image preview using chafa/timg when available."""
    if max_lines <= 0 or max_cols <= 0:
        return []
    backend = _detect_image_preview_backend()
    if not backend:
        return ['[image preview unavailable: install chafa/timg]']

    if backend == 'chafa':
        cmd = [
            'chafa',
            '--format=symbols',
            '--size', f'{max_cols}x{max_lines}',
            '--colors=none',
            path,
        ]
    else:
        cmd = [
            'timg',
            '-g', f'{max_cols}x{max_lines}',
            path,
        ]

    try:
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return [f'[image preview failed via {backend}]']

    if completed.returncode != 0:
        return [f'[image preview failed via {backend}]']

    lines = completed.stdout.splitlines()
    if not lines:
        return ['[empty image output]']
    return lines[:max_lines]

def get_preview_lines(entry, max_lines, max_cols=0):
    """Return preview lines for selected entry."""
    if max_lines <= 0:
        return []
    if entry is None:
        return ['No selection.']
    if entry.name == '..':
        return ['Parent directory entry.']
    if entry.is_dir:
        try:
            names = sorted(os.listdir(entry.full_path), key=str.lower)
        except OSError:
            return ['[directory not readable]']
        if not names:
            return ['[empty directory]']
        result = []
        for name in names[:max_lines]:
            marker = '/' if os.path.isdir(os.path.join(entry.full_path, name)) else ''
            result.append(f'{name}{marker}')
        return result

    ext = os.path.splitext(entry.full_path)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return _read_image_preview(entry.full_path, max_lines=max_lines, max_cols=max_cols)

    return _read_text_preview(entry.full_path, max_lines=max_lines)

"""
File system operations for File Manager.
"""
import os
import shutil
import time
import threading
from ...core.actions import ActionResult, ActionType
from .core import FileEntry

def _trash_base_dir():
    """Return platform-local trash directory used for undoable delete."""
    return os.path.join(os.path.expanduser('~'), '.local', 'share', 'Trash', 'files')

def _is_long_file_operation(entry, threshold_bytes):
    """Return True when operation should show a modal progress dialog."""
    if entry is None or getattr(entry, 'name', None) == '..':
        return False
    if getattr(entry, 'is_dir', False):
        return True

    size = getattr(entry, 'size', None)
    if size is None:
        full_path = getattr(entry, 'full_path', None)
        if not full_path:
            return False
        try:
            size = os.path.getsize(full_path)
        except OSError:
            return False
    return int(size) >= threshold_bytes


def next_trash_path(original_path, trash_dir=None):
    """Build a non-colliding destination path inside trash directory."""
    if trash_dir is None:
        trash_dir = _trash_base_dir()
    os.makedirs(trash_dir, exist_ok=True)
    base_name = os.path.basename(original_path.rstrip(os.sep)) or 'item'
    candidate = os.path.join(trash_dir, base_name)
    if not os.path.exists(candidate):
        return candidate
    index = 1
    while True:
        alt = os.path.join(trash_dir, f'{base_name}.{index}')
        if not os.path.exists(alt):
            return alt
        index += 1

def perform_copy(source_path, dest_path):
    """Copy file or directory."""
    try:
        if os.path.isdir(source_path):
            shutil.copytree(source_path, os.path.join(dest_path, os.path.basename(source_path)))
        else:
            shutil.copy2(source_path, dest_path)
        return ActionResult(ActionType.REFRESH)
    except (OSError, shutil.Error) as exc:
        return ActionResult(ActionType.ERROR, str(exc))

def perform_move(source_path, dest_path):
    """Move file or directory."""
    try:
        shutil.move(source_path, dest_path)
        return ActionResult(ActionType.REFRESH)
    except (OSError, shutil.Error) as exc:
        return ActionResult(ActionType.ERROR, str(exc))

def perform_delete(source_path):
    """Move file or directory to trash."""
    try:
        trash_path = next_trash_path(source_path)
        shutil.move(source_path, trash_path)
        return trash_path
    except (OSError, shutil.Error):
        return None

def perform_undo(last_trash_move):
    """Restore last trashed path back to its original location."""
    if not last_trash_move:
        return ActionResult(ActionType.ERROR, 'Nothing to undo.')
    source = last_trash_move.get('source')
    trash_path = last_trash_move.get('trash')
    
    if not source or not trash_path or not os.path.exists(trash_path):
        return ActionResult(ActionType.ERROR, 'Undo state is no longer available.')
    if os.path.exists(source):
        return ActionResult(ActionType.ERROR, 'Cannot undo: destination already exists.')
    parent = os.path.dirname(source) or os.path.sep
    if not os.path.isdir(parent):
        return ActionResult(ActionType.ERROR, 'Cannot undo: parent directory does not exist.')
    
    try:
        shutil.move(trash_path, source)
    except OSError as exc:
        return ActionResult(ActionType.ERROR, str(exc))
    return None

def create_directory(base_path, name):
    """Create a new directory."""
    name = name.strip()
    if not name:
        return ActionResult(ActionType.ERROR, 'Folder name cannot be empty.')
    path = os.path.join(base_path, name)
    if os.path.exists(path):
        return ActionResult(ActionType.ERROR, 'A file or folder with that name already exists.')
    try:
        os.makedirs(path)
        return ActionResult(ActionType.REFRESH)
    except OSError as exc:
        return ActionResult(ActionType.ERROR, str(exc))

def create_file(base_path, name):
    """Create a new empty file."""
    name = name.strip()
    if not name:
        return ActionResult(ActionType.ERROR, 'File name cannot be empty.')
    path = os.path.join(base_path, name)
    if os.path.exists(path):
        return ActionResult(ActionType.ERROR, 'A file or folder with that name already exists.')
    try:
        open(path, 'a').close()
        return ActionResult(ActionType.REFRESH)
    except OSError as exc:
        return ActionResult(ActionType.ERROR, str(exc))

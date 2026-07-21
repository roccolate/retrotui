"""
File system operations for File Manager.
"""
import json
import os
import shutil
import time
import threading
from pathlib import Path
from ...core.actions import ActionResult, ActionType
from ...core.file_transfer import cooperative_copy, cooperative_move
from ...core.trash_transaction import (
    clear_trash_metadata as _clear_trash_metadata_strict,
    read_trash_metadata as _read_trash_metadata_strict,
    transactional_empty_trash,
    transactional_move_to_trash,
    transactional_permanent_delete,
    transactional_restore,
    trash_metadata_path,
    write_trash_metadata as _write_trash_metadata_strict,
)
from .core import FileEntry

_TRASH_METADATA_ERRORS = (
    AttributeError,
    OSError,
    TypeError,
    ValueError,
)


def _trash_metadata_path(trash_path):
    """Return sidecar path that records the original location of a trash item."""
    return trash_metadata_path(trash_path)


def write_trash_metadata(trash_path, original_path):
    """Best-effort compatibility wrapper for callers that stage metadata."""
    try:
        _write_trash_metadata_strict(trash_path, original_path)
    except _TRASH_METADATA_ERRORS:
        _clear_trash_metadata_strict(trash_path)


def read_trash_metadata(trash_path):
    """Return the original path stored alongside ``trash_path`` or None."""
    return _read_trash_metadata_strict(trash_path)


def clear_trash_metadata(trash_path):
    """Remove a trash sidecar (best-effort)."""
    _clear_trash_metadata_strict(trash_path)


def _trash_base_dir():
    """Return platform-local trash directory used for undoable delete."""
    if os.name == 'nt':
        return os.path.join(os.environ.get('TEMP', os.path.expanduser('~')), 'RetroTUI_Trash')
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

def perform_copy(
    source_path,
    dest_path,
    *,
    cancel_event=None,
    progress_callback=None,
):
    """Copy file or directory through a rollback-safe temporary destination."""
    try:
        cooperative_copy(
            source_path,
            dest_path,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
        return ActionResult(ActionType.REFRESH)
    except (OSError, shutil.Error, ValueError) as exc:
        return ActionResult(ActionType.ERROR, str(exc))


def perform_move(
    source_path,
    dest_path,
    *,
    cancel_event=None,
    progress_callback=None,
):
    """Move atomically when possible, otherwise use cooperative copy + cleanup."""
    try:
        cooperative_move(
            source_path,
            dest_path,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
        return ActionResult(ActionType.REFRESH)
    except (OSError, shutil.Error, ValueError) as exc:
        return ActionResult(ActionType.ERROR, str(exc))


def perform_delete(
    source_path,
    trash_dir=None,
    *,
    cancel_event=None,
    progress_callback=None,
):
    """Move a path to trash through a durable, recoverable transaction."""
    try:
        trash_path = next_trash_path(source_path, trash_dir=trash_dir)
        transactional_move_to_trash(
            source_path,
            trash_path,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
        return trash_path
    except (OSError, shutil.Error, ValueError):
        return None


def perform_undo(
    last_trash_move,
    *,
    cancel_event=None,
    progress_callback=None,
):
    """Restore the last trashed path back to its original location."""
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
        transactional_restore(
            trash_path,
            source,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
    except (OSError, shutil.Error, ValueError) as exc:
        return ActionResult(ActionType.ERROR, str(exc))
    return ActionResult(ActionType.REFRESH)


def perform_restore(
    trash_path,
    fallback_dir=None,
    *,
    cancel_event=None,
    progress_callback=None,
):
    """Restore one trash item and return ``(result, restored_path)``."""
    if not trash_path or not os.path.exists(trash_path):
        return ActionResult(ActionType.ERROR, 'Item is no longer in the trash.'), None
    original = read_trash_metadata(trash_path)
    target = original
    if not target:
        if not fallback_dir:
            return ActionResult(ActionType.ERROR, 'Original location is unknown.'), None
        target = os.path.join(fallback_dir, os.path.basename(trash_path))
    if os.path.exists(target):
        return ActionResult(ActionType.ERROR, f'Cannot restore: {target} already exists.'), None
    parent = os.path.dirname(target) or os.path.sep
    if not os.path.isdir(parent):
        return ActionResult(ActionType.ERROR, f'Cannot restore: parent {parent} no longer exists.'), None
    try:
        transactional_restore(
            trash_path,
            target,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
    except (OSError, shutil.Error, ValueError) as exc:
        return ActionResult(ActionType.ERROR, str(exc)), None
    return ActionResult(ActionType.REFRESH), target


def perform_permanent_delete(
    path,
    trash_root,
    *,
    cancel_event=None,
    progress_callback=None,
):
    """Stage and cooperatively clean one permanent-delete transaction."""
    try:
        progress = transactional_permanent_delete(
            path,
            trash_root,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
    except (OSError, shutil.Error, ValueError) as exc:
        return ActionResult(ActionType.ERROR, str(exc))
    message = (
        'Deletion committed; physical cleanup deferred.'
        if progress.phase == 'deferred'
        else None
    )
    return ActionResult(ActionType.REFRESH, message)


def perform_empty_trash(
    trash_root,
    *,
    cancel_event=None,
    progress_callback=None,
):
    """Permanently remove all user-visible trash entries."""
    try:
        progress = transactional_empty_trash(
            trash_root,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
    except FileNotFoundError:
        return ActionResult(ActionType.ERROR, 'Trash is already empty.')
    except (OSError, shutil.Error, ValueError) as exc:
        return ActionResult(ActionType.ERROR, str(exc))
    message = (
        'Trash cleanup deferred; it will resume when Trash opens again.'
        if progress.phase == 'deferred'
        else None
    )
    return ActionResult(ActionType.REFRESH, message)


def create_directory(base_path, name):
    """Create a new directory."""
    name = name.strip()
    if not name:
        return ActionResult(ActionType.ERROR, 'Folder name cannot be empty.')
    path = os.path.join(base_path, name)
    # Use ``exist_ok=False`` semantics — let the OS do the check via the
    # raise, no pre-flight ``os.path.exists`` (TOCTOU race).
    try:
        os.makedirs(path, exist_ok=False)
        return ActionResult(ActionType.REFRESH)
    except FileExistsError:
        return ActionResult(ActionType.ERROR, 'A file or folder with that name already exists.')
    except OSError as exc:
        return ActionResult(ActionType.ERROR, str(exc))

def create_file(base_path, name):
    """Create a new empty file."""
    name = name.strip()
    if not name:
        return ActionResult(ActionType.ERROR, 'File name cannot be empty.')
    path = os.path.join(base_path, name)
    # ``Path.touch(exist_ok=False)`` already raises FileExistsError on
    # conflict; no pre-flight ``os.path.exists`` (TOCTOU race).
    try:
        Path(path).touch(exist_ok=False)
        return ActionResult(ActionType.REFRESH)
    except FileExistsError:
        return ActionResult(ActionType.ERROR, 'A file or folder with that name already exists.')
    except OSError as exc:
        return ActionResult(ActionType.ERROR, str(exc))

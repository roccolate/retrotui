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
from .core import FileEntry

_TRASH_METADATA_ERRORS = (
    AttributeError,
    OSError,
    TypeError,
    ValueError,
)


def _trash_metadata_path(trash_path):
    """Return sidecar path that records the original location of a trash item."""
    return f"{trash_path}.trashinfo"


def write_trash_metadata(trash_path, original_path):
    """Persist ``original_path`` next to ``trash_path`` so we can restore later."""
    from ...utils import atomic_write_text
    try:
        atomic_write_text(
            _trash_metadata_path(trash_path),
            json.dumps({"original_path": str(original_path)}),
            encoding="utf-8",
        )
    except _TRASH_METADATA_ERRORS:
        # Metadata is best-effort; restore will fall back to the trash root
        # when sidecars are missing.
        try:
            path = Path(_trash_metadata_path(trash_path))
            if path.exists():
                path.unlink()
        except _TRASH_METADATA_ERRORS:
            pass


def read_trash_metadata(trash_path):
    """Return the original path stored alongside ``trash_path`` or None."""
    sidecar = _trash_metadata_path(trash_path)
    if not os.path.exists(sidecar):
        return None
    try:
        with open(sidecar, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except _TRASH_METADATA_ERRORS:
        return None
    if not isinstance(data, dict):
        return None
    original = data.get("original_path")
    if not isinstance(original, str) or not original:
        return None
    return original


def clear_trash_metadata(trash_path):
    """Remove a trash sidecar (best-effort)."""
    try:
        os.unlink(_trash_metadata_path(trash_path))
    except OSError:
        pass

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

def perform_copy(source_path, dest_path):
    """Copy file or directory."""
    try:
        if os.path.isdir(source_path):
            shutil.copytree(source_path, dest_path)
        else:
            shutil.copy2(source_path, dest_path)
        return ActionResult(ActionType.REFRESH)
    except (OSError, shutil.Error) as exc:
        return ActionResult(ActionType.ERROR, str(exc))

def perform_move(source_path, dest_path):
    """Move file or directory."""
    try:
        # ``shutil.move`` is only atomic on the same filesystem; across
        # filesystems it falls back to copy+delete, which can leave the
        # source partially deleted on a crash. Acceptable for a desktop
        # file manager; documented here so future improvements are aware.
        shutil.move(source_path, dest_path)
        return ActionResult(ActionType.REFRESH)
    except (OSError, shutil.Error) as exc:
        return ActionResult(ActionType.ERROR, str(exc))
def perform_delete(source_path, trash_dir=None):
    """Move file or directory to trash."""
    try:
        trash_path = next_trash_path(source_path, trash_dir=trash_dir)
        # Write the metadata sidecar *before* moving so a SIGKILL between
        # the move and the metadata write can't leave the file in trash
        # with no way to restore. The trash path is already determined
        # by ``next_trash_path`` so this is safe to do up front.
        write_trash_metadata(trash_path, source_path)
        try:
            shutil.move(source_path, trash_path)
        except (OSError, shutil.Error):
            # Clean up the sidecar so an undo doesn't try to restore
            # something that was never moved.
            try:
                Path(_trash_metadata_path(trash_path)).unlink()
            except OSError:
                pass
            raise
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
    clear_trash_metadata(trash_path)
    return ActionResult(ActionType.REFRESH)


def perform_restore(trash_path, fallback_dir=None):
    """Restore a single item currently in the trash back to its origin.

    Returns a tuple ``(result, restored_path)`` so the caller can update any
    local undo state. ``restored_path`` is ``None`` when the move failed.
    """
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
        shutil.move(trash_path, target)
    except (OSError, shutil.Error) as exc:
        return ActionResult(ActionType.ERROR, str(exc)), None
    clear_trash_metadata(trash_path)
    return ActionResult(ActionType.REFRESH), target

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

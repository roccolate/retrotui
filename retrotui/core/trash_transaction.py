"""Crash-recoverable trash and permanent-delete transactions."""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from ..utils import atomic_write_text
from .file_transfer import (
    TransferCancelled,
    TransferProgress,
    _rename_noreplace,
    cooperative_move,
)

_TXN_DIR = ".retrotui-transactions"
_PENDING_DIR = ".retrotui-pending-delete"
_VERSION = 1


def trash_metadata_path(path: str) -> str:
    return f"{path}.trashinfo"


def write_trash_metadata(path: str, original: str) -> None:
    atomic_write_text(
        trash_metadata_path(path),
        json.dumps(
            {"version": _VERSION, "original_path": os.fspath(original)},
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def read_trash_metadata(path: str) -> str | None:
    try:
        with open(trash_metadata_path(path), "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, UnicodeError, ValueError, TypeError):
        return None
    original = data.get("original_path") if isinstance(data, dict) else None
    return original if isinstance(original, str) and original else None


def clear_trash_metadata(path: str) -> None:
    try:
        os.unlink(trash_metadata_path(path))
    except OSError:
        pass


def _remove(path: str | None) -> None:
    if not path or not os.path.lexists(path):
        return
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)


def _txn_dir(root: str) -> str:
    return os.path.join(root, _TXN_DIR)


def _pending_dir(root: str) -> str:
    return os.path.join(root, _PENDING_DIR)


def _journal_path(root: str, txn_id: str) -> str:
    return os.path.join(_txn_dir(root), f"{txn_id}.json")


def _new_journal(operation: str, **paths: str) -> dict[str, Any]:
    return {
        "version": _VERSION,
        "id": uuid.uuid4().hex,
        "operation": operation,
        "phase": "prepared",
        "created_at": time.time(),
        **paths,
    }


def _write_journal(root: str, data: dict[str, Any], phase: str | None = None) -> str:
    payload = dict(data)
    if phase is not None:
        payload["phase"] = phase
        payload["updated_at"] = time.time()
    os.makedirs(_txn_dir(root), exist_ok=True)
    path = _journal_path(root, str(payload["id"]))
    atomic_write_text(
        path,
        json.dumps(payload, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return path


def _read_journal(path: str) -> dict[str, Any] | None:
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, UnicodeError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _unlink_journal(path: str | None) -> None:
    try:
        if path:
            os.unlink(path)
    except OSError:
        pass


def _cleanup_dirs(root: str) -> None:
    for path in (_txn_dir(root), _pending_dir(root)):
        try:
            os.rmdir(path)
        except OSError:
            pass


def _cleanup_transfer_temps(destination: str) -> None:
    parent = os.path.dirname(destination) or os.curdir
    name = os.path.basename(destination) or "transfer"
    try:
        candidates = Path(parent).glob(f".{name}.retrotui-*.part")
        for candidate in candidates:
            try:
                _remove(os.fspath(candidate))
            except OSError:
                pass
    except OSError:
        pass


def _publish(callback: Callable[[TransferProgress], Any] | None, progress: TransferProgress) -> None:
    if not callable(callback):
        return
    try:
        callback(progress)
    except Exception:
        pass


def transactional_move_to_trash(
    source_path: str,
    trash_path: str,
    *,
    cancel_event: Any | None = None,
    progress_callback: Callable[[TransferProgress], Any] | None = None,
) -> TransferProgress:
    source = os.path.abspath(os.fspath(source_path))
    destination = os.path.abspath(os.fspath(trash_path))
    root = os.path.dirname(destination) or os.curdir
    if not os.path.lexists(source):
        raise FileNotFoundError(source)
    if os.path.lexists(destination):
        raise FileExistsError(destination)
    os.makedirs(root, exist_ok=True)

    journal = _new_journal(
        "trash",
        source=source,
        destination=destination,
        metadata=trash_metadata_path(destination),
    )
    journal_path = _write_journal(root, journal)
    try:
        write_trash_metadata(destination, source)
    except Exception:
        _unlink_journal(journal_path)
        _cleanup_dirs(root)
        raise

    try:
        result = cooperative_move(
            source,
            destination,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
    except Exception:
        source_exists = os.path.lexists(source)
        destination_exists = os.path.lexists(destination)
        if source_exists and destination_exists:
            try:
                _remove(destination)
                destination_exists = False
            except OSError:
                pass
        if source_exists and not destination_exists:
            clear_trash_metadata(destination)
            _cleanup_transfer_temps(destination)
            _unlink_journal(journal_path)
            _cleanup_dirs(root)
        raise

    _write_journal(root, journal, "committed")
    _unlink_journal(journal_path)
    _cleanup_dirs(root)
    return result


def transactional_restore(
    trash_path: str,
    target_path: str,
    *,
    cancel_event: Any | None = None,
    progress_callback: Callable[[TransferProgress], Any] | None = None,
) -> TransferProgress:
    source = os.path.abspath(os.fspath(trash_path))
    destination = os.path.abspath(os.fspath(target_path))
    root = os.path.dirname(source) or os.curdir
    if not os.path.lexists(source):
        raise FileNotFoundError(source)
    if os.path.lexists(destination):
        raise FileExistsError(destination)

    journal = _new_journal(
        "restore",
        source=source,
        destination=destination,
        metadata=trash_metadata_path(source),
    )
    journal_path = _write_journal(root, journal)
    try:
        result = cooperative_move(
            source,
            destination,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
    except Exception:
        source_exists = os.path.lexists(source)
        destination_exists = os.path.lexists(destination)
        if source_exists and destination_exists:
            try:
                _remove(destination)
                destination_exists = False
            except OSError:
                pass
        if source_exists and not destination_exists:
            _cleanup_transfer_temps(destination)
            _unlink_journal(journal_path)
            _cleanup_dirs(root)
        raise

    _write_journal(root, journal, "committed")
    clear_trash_metadata(source)
    _unlink_journal(journal_path)
    _cleanup_dirs(root)
    return result


class _RemovalReporter:
    def __init__(self, callback):
        self.callback = callback
        self.phase = "scanning"
        self.bytes_done = 0
        self.total_bytes = 0
        self.files_done = 0
        self.total_files = 0
        self.current_path = ""

    def snapshot(self) -> TransferProgress:
        return TransferProgress(
            phase=self.phase,
            bytes_done=self.bytes_done,
            total_bytes=self.total_bytes,
            files_done=self.files_done,
            total_files=self.total_files,
            current_path=self.current_path,
        )

    def emit(self, phase: str | None = None, path: str | None = None) -> None:
        if phase is not None:
            self.phase = phase
        if path is not None:
            self.current_path = path
        _publish(self.callback, self.snapshot())

    def removed(self, path: str, size: int = 0) -> None:
        self.bytes_done += max(0, int(size))
        self.files_done += 1
        self.emit(path=path)


def _cancelled(event: Any | None) -> bool:
    checker = getattr(event, "is_set", None)
    return bool(checker()) if callable(checker) else False


def _check_cancel(event: Any | None) -> None:
    if _cancelled(event):
        raise TransferCancelled("Operation cancelled.")


def _scan_removal(path: str, event: Any | None, reporter: _RemovalReporter) -> None:
    reporter.emit("scanning", path)
    if os.path.islink(path):
        reporter.total_files = 1
        reporter.emit()
        return
    if os.path.isfile(path):
        reporter.total_files = 1
        try:
            reporter.total_bytes = int(os.stat(path, follow_symlinks=False).st_size)
        except OSError:
            pass
        reporter.emit()
        return
    if not os.path.isdir(path):
        raise OSError(f"Unsupported file type: {path}")

    files = 1
    total_bytes = 0
    for root, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
        _check_cancel(event)
        reporter.emit(path=root)
        for dirname in list(dirnames):
            full = os.path.join(root, dirname)
            files += 1
            if os.path.islink(full):
                dirnames.remove(dirname)
        for filename in filenames:
            full = os.path.join(root, filename)
            files += 1
            if not os.path.islink(full):
                try:
                    total_bytes += int(os.stat(full, follow_symlinks=False).st_size)
                except OSError:
                    pass
    reporter.total_files = files
    reporter.total_bytes = total_bytes
    reporter.emit()


def _remove_tree(path: str, event: Any | None, reporter: _RemovalReporter) -> None:
    if os.path.islink(path) or not os.path.isdir(path):
        _check_cancel(event)
        try:
            size = int(os.stat(path, follow_symlinks=False).st_size)
        except OSError:
            size = 0
        os.unlink(path)
        reporter.removed(path, size)
        return

    for root, dirnames, filenames in os.walk(path, topdown=False, followlinks=False):
        for filename in filenames:
            _check_cancel(event)
            full = os.path.join(root, filename)
            try:
                size = 0 if os.path.islink(full) else int(
                    os.stat(full, follow_symlinks=False).st_size
                )
            except OSError:
                size = 0
            os.unlink(full)
            reporter.removed(full, size)
        for dirname in dirnames:
            _check_cancel(event)
            full = os.path.join(root, dirname)
            os.unlink(full) if os.path.islink(full) else os.rmdir(full)
            reporter.removed(full)
    _check_cancel(event)
    os.rmdir(path)
    reporter.removed(path)


def transactional_permanent_delete(
    path: str,
    trash_root: str,
    *,
    cancel_event: Any | None = None,
    progress_callback: Callable[[TransferProgress], Any] | None = None,
) -> TransferProgress:
    source = os.path.abspath(os.fspath(path))
    root = os.path.abspath(os.fspath(trash_root))
    root_real = os.path.realpath(root)
    parent_real = os.path.realpath(os.path.dirname(source) or os.curdir)
    if source == root or not (
        parent_real == root_real or parent_real.startswith(root_real + os.sep)
    ):
        raise ValueError("Permanent delete target must be inside the trash root.")
    if not os.path.lexists(source):
        raise FileNotFoundError(source)

    reporter = _RemovalReporter(progress_callback)
    _scan_removal(source, cancel_event, reporter)
    _check_cancel(cancel_event)

    os.makedirs(_pending_dir(root), exist_ok=True)
    tombstone = os.path.join(
        _pending_dir(root),
        f"{uuid.uuid4().hex}-{os.path.basename(source) or 'item'}",
    )
    journal = _new_journal(
        "purge",
        source=source,
        destination=tombstone,
        metadata=trash_metadata_path(source),
    )
    journal_path = _write_journal(root, journal)
    try:
        _rename_noreplace(source, tombstone)
    except Exception:
        _unlink_journal(journal_path)
        _cleanup_dirs(root)
        raise

    clear_trash_metadata(source)
    _write_journal(root, journal, "staged")
    reporter.emit("deleting", tombstone)
    try:
        _remove_tree(tombstone, cancel_event, reporter)
    except TransferCancelled:
        _write_journal(root, journal, "deferred")
        reporter.emit("deferred", source)
        return reporter.snapshot()
    except Exception:
        _write_journal(root, journal, "failed")
        raise

    reporter.bytes_done = reporter.total_bytes
    reporter.files_done = reporter.total_files
    reporter.emit("completed", source)
    _unlink_journal(journal_path)
    _cleanup_dirs(root)
    return reporter.snapshot()


def is_internal_trash_name(name: str) -> bool:
    return (
        name in {_TXN_DIR, _PENDING_DIR}
        or name.endswith(".trashinfo")
        or (name.startswith(".") and ".retrotui-" in name and name.endswith(".part"))
    )


def list_trash_items(root: str) -> list[str]:
    try:
        names = os.listdir(root)
    except FileNotFoundError:
        return []
    return [
        os.path.join(root, name)
        for name in sorted(names)
        if not is_internal_trash_name(name)
    ]


def recover_trash_transactions(root: str) -> list[str]:
    root = os.path.abspath(os.fspath(root))
    directory = _txn_dir(root)
    if not os.path.isdir(directory):
        return []

    errors: list[str] = []
    for path_obj in sorted(Path(directory).glob("*.json")):
        path = os.fspath(path_obj)
        data = _read_journal(path)
        if not data:
            errors.append(f"Invalid trash journal: {path_obj.name}")
            continue
        operation = data.get("operation")
        source = data.get("source")
        destination = data.get("destination")
        if not isinstance(source, str) or not isinstance(destination, str):
            errors.append(f"Incomplete trash journal: {path_obj.name}")
            continue

        try:
            source_exists = os.path.lexists(source)
            destination_exists = os.path.lexists(destination)
            if operation in {"trash", "restore"}:
                if source_exists and destination_exists:
                    _remove(destination)
                    destination_exists = False
                if source_exists and not destination_exists:
                    _cleanup_transfer_temps(destination)
                    if operation == "trash":
                        clear_trash_metadata(destination)
                    _unlink_journal(path)
                elif not source_exists and destination_exists:
                    _cleanup_transfer_temps(destination)
                    if operation == "trash":
                        write_trash_metadata(destination, source)
                    else:
                        clear_trash_metadata(source)
                    _unlink_journal(path)
                else:
                    errors.append(f"Unresolved {operation} transaction: {path_obj.name}")
            elif operation == "purge":
                if destination_exists:
                    reporter = _RemovalReporter(None)
                    _scan_removal(destination, None, reporter)
                    _remove_tree(destination, None, reporter)
                    clear_trash_metadata(source)
                    _unlink_journal(path)
                elif source_exists:
                    _unlink_journal(path)
                else:
                    clear_trash_metadata(source)
                    _unlink_journal(path)
            else:
                errors.append(f"Unknown trash transaction: {path_obj.name}")
        except (OSError, ValueError) as exc:
            errors.append(f"{path_obj.name}: {exc}")

    _cleanup_dirs(root)
    return errors

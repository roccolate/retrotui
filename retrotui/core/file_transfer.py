
"""Cooperative filesystem transfer primitives.

Transfers copy into a sibling temporary path and only publish the destination
after the complete payload has been written. Cancellation therefore removes
temporary state instead of leaving a partial destination behind.
"""
from __future__ import annotations

import ctypes
import errno
import logging
import os
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass, replace
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)
DEFAULT_CHUNK_SIZE = 1024 * 1024


class TransferCancelled(RuntimeError):
    """Raised when a cooperative transfer receives a cancellation request."""


@dataclass(frozen=True)
class TransferProgress:
    """Immutable progress snapshot emitted by cooperative transfers."""

    phase: str
    bytes_done: int = 0
    total_bytes: int = 0
    files_done: int = 0
    total_files: int = 0
    current_path: str = ""

    @property
    def fraction(self) -> float | None:
        if self.total_bytes > 0:
            return min(1.0, self.bytes_done / self.total_bytes)
        if self.total_files > 0:
            return min(1.0, self.files_done / self.total_files)
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "bytes_done": self.bytes_done,
            "total_bytes": self.total_bytes,
            "files_done": self.files_done,
            "total_files": self.total_files,
            "current_path": self.current_path,
            "fraction": self.fraction,
        }


def _emit_callback(
    callback: Callable[[TransferProgress], Any] | None,
    progress: TransferProgress,
) -> None:
    if not callable(callback):
        return
    try:
        callback(progress)
    except Exception:
        LOGGER.debug("transfer progress callback failed", exc_info=True)


class _Reporter:
    def __init__(self, callback: Callable[[TransferProgress], Any] | None):
        self.callback = callback
        self.phase = "preparing"
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

    def emit(self, *, phase: str | None = None, current_path: str | None = None) -> None:
        if phase is not None:
            self.phase = phase
        if current_path is not None:
            self.current_path = current_path
        _emit_callback(self.callback, self.snapshot())

    def advance_bytes(self, count: int, current_path: str) -> None:
        self.bytes_done += max(0, int(count))
        self.emit(current_path=current_path)

    def advance_file(self, current_path: str) -> None:
        self.files_done += 1
        self.emit(current_path=current_path)


def _cancel_requested(cancel_event: Any | None) -> bool:
    checker = getattr(cancel_event, "is_set", None)
    return bool(checker()) if callable(checker) else False


def _raise_if_cancelled(cancel_event: Any | None) -> None:
    if _cancel_requested(cancel_event):
        raise TransferCancelled("Operation cancelled.")


def _validate_paths(source_path: str, dest_path: str) -> tuple[str, str]:
    source = os.path.abspath(os.fspath(source_path))
    dest = os.path.abspath(os.fspath(dest_path))
    if not os.path.lexists(source):
        raise FileNotFoundError(source)
    if os.path.lexists(dest):
        raise FileExistsError(dest)
    parent = os.path.dirname(dest) or os.curdir
    if not os.path.isdir(parent):
        raise FileNotFoundError(f"Destination directory does not exist: {parent}")
    if os.path.isdir(source) and not os.path.islink(source):
        source_real = os.path.realpath(source)
        dest_real = os.path.realpath(dest)
        if dest_real == source_real or dest_real.startswith(source_real + os.sep):
            raise ValueError("Cannot copy or move a directory into itself.")
    return source, dest


def _scan_source(source: str, cancel_event: Any | None, reporter: _Reporter) -> None:
    reporter.emit(phase="scanning", current_path=source)
    if os.path.islink(source):
        reporter.total_files = 1
        reporter.emit()
        return
    if os.path.isfile(source):
        st = os.stat(source, follow_symlinks=False)
        if not stat.S_ISREG(st.st_mode):
            raise OSError(f"Unsupported file type: {source}")
        reporter.total_bytes = int(st.st_size)
        reporter.total_files = 1
        reporter.emit()
        return
    if not os.path.isdir(source):
        raise OSError(f"Unsupported file type: {source}")

    total_bytes = 0
    total_files = 0
    for root, dirnames, filenames in os.walk(source, topdown=True, followlinks=False):
        _raise_if_cancelled(cancel_event)
        reporter.emit(current_path=root)
        for dirname in list(dirnames):
            full_path = os.path.join(root, dirname)
            if os.path.islink(full_path):
                total_files += 1
                dirnames.remove(dirname)
        for filename in filenames:
            full_path = os.path.join(root, filename)
            total_files += 1
            if os.path.islink(full_path):
                continue
            st = os.stat(full_path, follow_symlinks=False)
            if not stat.S_ISREG(st.st_mode):
                raise OSError(f"Unsupported file type: {full_path}")
            total_bytes += int(st.st_size)
    reporter.total_bytes = total_bytes
    reporter.total_files = total_files
    reporter.emit()


def _temporary_destination(dest: str, *, is_dir: bool) -> str:
    parent = os.path.dirname(dest) or os.curdir
    basename = os.path.basename(dest) or "transfer"
    prefix = f".{basename}.retrotui-"
    if is_dir:
        return tempfile.mkdtemp(prefix=prefix, suffix=".part", dir=parent)
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=".part", dir=parent)
    os.close(fd)
    return path


def _cleanup_path(path: str | None) -> None:
    if not path or not os.path.lexists(path):
        return
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.unlink(path)
    except OSError:
        LOGGER.warning("Could not clean transfer path %s", path, exc_info=True)


def _copy_symlink(source: str, dest: str, reporter: _Reporter) -> None:
    if os.path.lexists(dest):
        os.unlink(dest)
    target = os.readlink(source)
    try:
        os.symlink(target, dest, target_is_directory=os.path.isdir(source))
    except TypeError:  # pragma: no cover - Python/platform compatibility
        os.symlink(target, dest)
    reporter.advance_file(source)


def _copy_regular_file(
    source: str,
    dest: str,
    *,
    cancel_event: Any | None,
    reporter: _Reporter,
    chunk_size: int,
) -> None:
    with open(source, "rb") as src, open(dest, "wb") as dst:
        while True:
            _raise_if_cancelled(cancel_event)
            chunk = src.read(chunk_size)
            if not chunk:
                break
            dst.write(chunk)
            reporter.advance_bytes(len(chunk), source)
    shutil.copystat(source, dest, follow_symlinks=False)
    reporter.advance_file(source)


def _copy_directory(
    source: str,
    temp_root: str,
    *,
    cancel_event: Any | None,
    reporter: _Reporter,
    chunk_size: int,
) -> None:
    directory_metadata: list[tuple[str, str]] = [(source, temp_root)]
    for root, dirnames, filenames in os.walk(source, topdown=True, followlinks=False):
        _raise_if_cancelled(cancel_event)
        rel = os.path.relpath(root, source)
        dest_root = temp_root if rel == os.curdir else os.path.join(temp_root, rel)
        reporter.emit(phase="copying", current_path=root)

        for dirname in list(dirnames):
            _raise_if_cancelled(cancel_event)
            src_dir = os.path.join(root, dirname)
            dst_dir = os.path.join(dest_root, dirname)
            if os.path.islink(src_dir):
                _copy_symlink(src_dir, dst_dir, reporter)
                dirnames.remove(dirname)
                continue
            os.mkdir(dst_dir)
            directory_metadata.append((src_dir, dst_dir))

        for filename in filenames:
            _raise_if_cancelled(cancel_event)
            src_file = os.path.join(root, filename)
            dst_file = os.path.join(dest_root, filename)
            if os.path.islink(src_file):
                _copy_symlink(src_file, dst_file, reporter)
            else:
                _copy_regular_file(
                    src_file,
                    dst_file,
                    cancel_event=cancel_event,
                    reporter=reporter,
                    chunk_size=chunk_size,
                )

    for src_dir, dst_dir in reversed(directory_metadata):
        shutil.copystat(src_dir, dst_dir, follow_symlinks=False)


def _rename_noreplace(source: str, dest: str) -> None:
    """Atomically rename *source* without replacing an existing destination.

    Windows already gives ``os.rename`` no-replace semantics. Linux uses
    ``renameat2(RENAME_NOREPLACE)`` when libc exposes it. Other POSIX hosts
    retain a checked fallback; that fallback is safe for normal operation but
    cannot close the final cross-process race without a platform-specific API.
    """

    if os.name == "nt":
        os.rename(source, dest)
        return

    if sys.platform.startswith("linux"):
        try:
            renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
        except AttributeError:
            renameat2 = None
        if renameat2 is not None:
            renameat2.argtypes = (
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            )
            renameat2.restype = ctypes.c_int
            result = renameat2(
                -100,
                os.fsencode(source),
                -100,
                os.fsencode(dest),
                1,
            )
            if result == 0:
                return
            error_number = ctypes.get_errno()
            unsupported = {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP}
            if error_number not in unsupported:
                raise OSError(error_number, os.strerror(error_number), dest)

    if os.path.lexists(dest):
        raise FileExistsError(dest)
    os.rename(source, dest)


def _commit_filelike(temp_path: str, dest: str) -> None:
    _rename_noreplace(temp_path, dest)


def _commit_directory(temp_path: str, dest: str) -> None:
    _rename_noreplace(temp_path, dest)


def cooperative_copy(
    source_path: str,
    dest_path: str,
    *,
    cancel_event: Any | None = None,
    progress_callback: Callable[[TransferProgress], Any] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> TransferProgress:
    """Copy one file or directory with cooperative cancellation and rollback."""

    if int(chunk_size) <= 0:
        raise ValueError("chunk_size must be positive")
    source, dest = _validate_paths(source_path, dest_path)
    reporter = _Reporter(progress_callback)
    _raise_if_cancelled(cancel_event)
    _scan_source(source, cancel_event, reporter)

    source_is_dir = os.path.isdir(source) and not os.path.islink(source)
    source_is_link = os.path.islink(source)
    temp_path = _temporary_destination(dest, is_dir=source_is_dir)
    try:
        reporter.emit(phase="copying", current_path=source)
        if source_is_dir:
            _copy_directory(
                source,
                temp_path,
                cancel_event=cancel_event,
                reporter=reporter,
                chunk_size=int(chunk_size),
            )
        elif source_is_link:
            _copy_symlink(source, temp_path, reporter)
        else:
            _copy_regular_file(
                source,
                temp_path,
                cancel_event=cancel_event,
                reporter=reporter,
                chunk_size=int(chunk_size),
            )

        _raise_if_cancelled(cancel_event)
        reporter.emit(phase="committing", current_path=dest)
        if source_is_dir:
            _commit_directory(temp_path, dest)
        else:
            _commit_filelike(temp_path, dest)
        temp_path = None
    except Exception:
        _cleanup_path(temp_path)
        raise

    reporter.bytes_done = reporter.total_bytes
    reporter.files_done = reporter.total_files
    reporter.emit(phase="completed", current_path=dest)
    return reporter.snapshot()


def _try_atomic_move(source: str, dest: str) -> bool:
    try:
        _rename_noreplace(source, dest)
        return True
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            return False
        raise


def _remove_source_after_copy(source: str) -> None:
    if os.path.isdir(source) and not os.path.islink(source):
        shutil.rmtree(source)
    else:
        os.unlink(source)


def cooperative_move(
    source_path: str,
    dest_path: str,
    *,
    cancel_event: Any | None = None,
    progress_callback: Callable[[TransferProgress], Any] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> TransferProgress:
    """Move a path atomically when possible, otherwise copy then safely remove."""

    source, dest = _validate_paths(source_path, dest_path)
    _raise_if_cancelled(cancel_event)
    direct = TransferProgress(
        phase="moving",
        total_bytes=0,
        total_files=1,
        current_path=source,
    )
    _emit_callback(progress_callback, direct)

    if _try_atomic_move(source, dest):
        finished = replace(
            direct,
            phase="completed",
            files_done=1,
            current_path=dest,
        )
        _emit_callback(progress_callback, finished)
        return finished

    copied = cooperative_copy(
        source,
        dest,
        cancel_event=cancel_event,
        progress_callback=progress_callback,
        chunk_size=chunk_size,
    )
    finalizing = replace(copied, phase="finalizing", current_path=source)
    _emit_callback(progress_callback, finalizing)

    # Cancellation is intentionally no longer observed after destination commit:
    # source removal is the point-of-no-return for a cross-filesystem move.
    try:
        _remove_source_after_copy(source)
    except Exception as exc:
        _cleanup_path(dest)
        if os.path.lexists(dest):
            raise OSError(
                f"Move finalization failed; source and destination may both exist: {exc}"
            ) from exc
        raise OSError(f"Move finalization failed; destination was rolled back: {exc}") from exc

    finished = replace(copied, phase="completed", current_path=dest)
    _emit_callback(progress_callback, finished)
    return finished

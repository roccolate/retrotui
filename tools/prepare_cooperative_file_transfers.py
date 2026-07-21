#!/usr/bin/env python3
"""Apply cooperative file-transfer hardening to the stacked branch."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, content):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path, old, new):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    write(path, text.replace(old, new, 1))


def replace_between(path, start_marker, end_marker, replacement):
    text = read(path)
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"{path}: start marker not found: {start_marker!r}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"{path}: end marker not found: {end_marker!r}")
    write(path, text[:start] + replacement + text[end:])


write("retrotui/core/file_transfer.py", """\
"""Cooperative filesystem transfer primitives.

Transfers copy into a sibling temporary path and only publish the destination
after the complete payload has been written. Cancellation therefore removes
temporary state instead of leaving a partial destination behind.
"""
from __future__ import annotations

import errno
import logging
import os
import shutil
import stat
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


def _commit_filelike(temp_path: str, dest: str) -> None:
    # Reserve the final name without overwriting a path that appeared after the
    # initial validation, then atomically replace our own placeholder.
    fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        os.replace(temp_path, dest)
    except Exception:
        try:
            os.unlink(dest)
        except OSError:
            pass
        raise


def _commit_directory(temp_path: str, dest: str) -> None:
    if os.path.lexists(dest):
        raise FileExistsError(dest)
    os.rename(temp_path, dest)


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
        os.rename(source, dest)
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
""")

write("tests/test_file_transfer.py", """\
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from retrotui.core.file_transfer import (
    TransferCancelled,
    cooperative_copy,
    cooperative_move,
)


class CooperativeFileTransferTests(unittest.TestCase):
    def test_copy_file_reports_progress_and_commits_complete_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            dest = root / "dest.bin"
            payload = (b"retro-tui-" * 300_000) + b"done"
            source.write_bytes(payload)
            updates = []

            result = cooperative_copy(
                source,
                dest,
                progress_callback=updates.append,
                chunk_size=64 * 1024,
            )

            self.assertEqual(dest.read_bytes(), payload)
            self.assertEqual(result.phase, "completed")
            self.assertEqual(result.bytes_done, len(payload))
            self.assertEqual(result.total_bytes, len(payload))
            self.assertTrue(any(item.phase == "copying" for item in updates))
            self.assertEqual(updates[-1].phase, "completed")

    def test_cancelled_copy_removes_partial_destination_and_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "large.bin"
            dest = root / "dest.bin"
            source.write_bytes(b"x" * (3 * 1024 * 1024))
            cancel_event = threading.Event()

            def on_progress(progress):
                if progress.bytes_done >= 64 * 1024:
                    cancel_event.set()

            with self.assertRaises(TransferCancelled):
                cooperative_copy(
                    source,
                    dest,
                    cancel_event=cancel_event,
                    progress_callback=on_progress,
                    chunk_size=64 * 1024,
                )

            self.assertFalse(dest.exists())
            self.assertEqual(
                [path for path in root.iterdir() if ".retrotui-" in path.name],
                [],
            )

    def test_directory_copy_preserves_nested_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tree"
            dest = root / "tree-copy"
            (source / "nested").mkdir(parents=True)
            (source / "a.txt").write_text("alpha", encoding="utf-8")
            (source / "nested" / "b.txt").write_text("beta", encoding="utf-8")

            result = cooperative_copy(source, dest, chunk_size=2)

            self.assertEqual((dest / "a.txt").read_text(encoding="utf-8"), "alpha")
            self.assertEqual(
                (dest / "nested" / "b.txt").read_text(encoding="utf-8"),
                "beta",
            )
            self.assertEqual(result.files_done, 2)
            self.assertEqual(result.total_files, 2)

    def test_cross_filesystem_move_rolls_back_destination_when_source_cleanup_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            dest = root / "dest.txt"
            source.write_text("payload", encoding="utf-8")

            with (
                mock.patch(
                    "retrotui.core.file_transfer._try_atomic_move",
                    return_value=False,
                ),
                mock.patch(
                    "retrotui.core.file_transfer._remove_source_after_copy",
                    side_effect=OSError("cannot remove source"),
                ),
            ):
                with self.assertRaisesRegex(OSError, "rolled back"):
                    cooperative_move(source, dest)

            self.assertTrue(source.exists())
            self.assertFalse(dest.exists())

    def test_atomic_move_does_not_copy_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            dest = root / "dest.txt"
            source.write_text("payload", encoding="utf-8")

            with mock.patch(
                "retrotui.core.file_transfer.cooperative_copy",
                side_effect=AssertionError("copy fallback should not run"),
            ):
                result = cooperative_move(source, dest)

            self.assertFalse(source.exists())
            self.assertEqual(dest.read_text(encoding="utf-8"), "payload")
            self.assertEqual(result.phase, "completed")


if __name__ == "__main__":
    unittest.main()
""")

write("tests/test_file_operation_progress.py", """\
import threading
import time
import types
import unittest
from unittest import mock

from retrotui.core.actions import ActionResult, ActionType
from retrotui.core.file_operations import FileOperationManager
from retrotui.core.file_transfer import TransferCancelled
from retrotui.ui.dialog import ProgressDialog


class _Bus:
    def __init__(self):
        self.events = []

    def publish(self, topic, data=None, **_kwargs):
        self.events.append((topic, data))


class CooperativeProgressTests(unittest.TestCase):
    def test_progress_dialog_requests_cancel_without_closing_itself(self):
        callback = mock.Mock()
        dialog = ProgressDialog(
            "Copying",
            "payload.bin",
            width=40,
            cancel_callback=callback,
        )

        self.assertEqual(dialog.handle_key(27), -1)
        callback.assert_called_once_with()
        self.assertTrue(dialog.cancel_requested)
        self.assertEqual(dialog.handle_key(ord("c")), -1)
        callback.assert_called_once_with()

    def test_manager_cancel_event_stops_worker_and_suppresses_error_dialog(self):
        bus = _Bus()
        app = types.SimpleNamespace(
            _background_operation=None,
            dialog=None,
            _event_bus=bus,
            _dirty=False,
            _dispatch_window_result=mock.Mock(),
        )
        manager = FileOperationManager(app)

        def worker(cancel_event=None, progress_callback=None):
            progress_callback({
                "phase": "copying",
                "bytes_done": 128,
                "total_bytes": 1024,
                "files_done": 0,
                "total_files": 1,
                "current_path": "payload.bin",
            })
            while not cancel_event.is_set():
                time.sleep(0.001)
            raise TransferCancelled("cancelled")

        worker._retrotui_cancellable = True
        self.assertIsNone(manager._start_background_operation(
            title="Copying",
            message="payload.bin",
            worker=worker,
            source_win=object(),
        ))
        self.assertIsInstance(app.dialog, ProgressDialog)
        self.assertTrue(manager.cancel_background_operation())

        deadline = time.monotonic() + 1.0
        while app._background_operation and time.monotonic() < deadline:
            manager.poll_background_operation()
            time.sleep(0.005)

        self.assertIsNone(app._background_operation)
        app._dispatch_window_result.assert_not_called()
        self.assertTrue(any(topic == "file_op.cancelled" for topic, _ in bus.events))

    def test_non_cancellable_worker_keeps_legacy_progress_dialog_contract(self):
        app = types.SimpleNamespace(
            _background_operation=None,
            dialog=None,
            _event_bus=None,
            _dirty=False,
            _dispatch_window_result=mock.Mock(),
        )
        manager = FileOperationManager(app)
        release = threading.Event()

        def worker():
            release.wait(0.5)
            return ActionResult(ActionType.REFRESH)

        self.assertIsNone(manager._start_background_operation(
            title="Deleting",
            message="payload.bin",
            worker=worker,
            source_win=None,
        ))
        try:
            self.assertIsNone(app.dialog.cancel_callback)
            self.assertFalse(manager.cancel_background_operation())
        finally:
            release.set()
            manager._worker_scope.join(timeout=1.0)


if __name__ == "__main__":
    unittest.main()
""")

replace_once(
    "retrotui/apps/filemanager/operations.py",
    "from ...core.actions import ActionResult, ActionType\n",
    "from ...core.actions import ActionResult, ActionType\n"
    "from ...core.file_transfer import cooperative_copy, cooperative_move\n",
)
replace_between(
    "retrotui/apps/filemanager/operations.py",
    "def perform_copy(",
    "def perform_delete(",
    """def perform_copy(
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


""",
)

replace_between(
    "retrotui/apps/filemanager/window.py",
    "    def copy_selected(",
    "    def _dual_copy_move_between_panes(",
    """    def copy_selected(self, dest_path, *, cancel_event=None, progress_callback=None):
        entry = self._selected_entry()
        if not entry:
            return ActionResult(ActionType.ERROR, 'No item selected.')

        target, error = self._resolve_destination_path(entry, dest_path)
        if error:
            return error

        res = perform_copy(
            entry.full_path,
            target,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
        if res.type == ActionType.REFRESH:
            self._rebuild_content()
        return res

    def copy_path_to(
        self,
        source_path,
        dest_path,
        *,
        cancel_event=None,
        progress_callback=None,
    ):
        """Copy an explicit source path into a destination path or directory."""
        if not source_path or not isinstance(source_path, str):
            return ActionResult(ActionType.ERROR, 'No source path provided.')
        name = os.path.basename(os.path.normpath(source_path))
        if not name:
            return ActionResult(ActionType.ERROR, 'Invalid source path.')
        entry = FileEntry(name, os.path.isdir(source_path), source_path, 0)
        target, error = self._resolve_destination_path(entry, dest_path)
        if error:
            return error

        res = perform_copy(
            source_path,
            target,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
        if res.type == ActionType.REFRESH:
            self._rebuild_content()
        return res

    def move_selected(self, dest_path, *, cancel_event=None, progress_callback=None):
        entry = self._selected_entry()
        if not entry:
            return ActionResult(ActionType.ERROR, 'No item selected.')

        target, error = self._resolve_destination_path(entry, dest_path)
        if error:
            return error

        res = perform_move(
            entry.full_path,
            target,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
        if res.type == ActionType.REFRESH:
            self._rebuild_content()
        return res

    def move_path_to(
        self,
        source_path,
        dest_path,
        *,
        cancel_event=None,
        progress_callback=None,
    ):
        """Move an explicit source path into a destination path or directory."""
        if not source_path or not isinstance(source_path, str):
            return ActionResult(ActionType.ERROR, 'No source path provided.')
        name = os.path.basename(os.path.normpath(source_path))
        if not name:
            return ActionResult(ActionType.ERROR, 'Invalid source path.')
        entry = FileEntry(name, os.path.isdir(source_path), source_path, 0)
        target, error = self._resolve_destination_path(entry, dest_path)
        if error:
            return error

        res = perform_move(
            source_path,
            target,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
        if res.type == ActionType.REFRESH:
            self._rebuild_content()
        return res

""",
)
replace_between(
    "retrotui/apps/filemanager/window.py",
    "    def _dual_copy_move_between_panes(",
    "    def _dual_copy_move(",
    """    def _dual_copy_move_between_panes(self, move=False):
        if not self.dual_pane_enabled:
            return ActionResult(ActionType.ERROR, 'Dual pane not enabled.')

        source = self._selected_entry()
        if not source or source.name == '..':
            return ActionResult(ActionType.ERROR, 'No item selected.')

        dest_dir = self.current_path if self.active_pane == 1 else self._secondary.path
        dest_path = os.path.join(dest_dir, source.name)
        if os.path.exists(dest_path):
            return ActionResult(ActionType.ERROR, f'Destination exists: {source.name}')

        if _is_long_file_operation(source, 10 * 1024 * 1024):
            request_type = (
                ActionType.REQUEST_MOVE_BETWEEN_PANES
                if move
                else ActionType.REQUEST_COPY_BETWEEN_PANES
            )
            return ActionResult(request_type, {
                'source': source.full_path,
                'destination': dest_dir,
            })

        if move:
            res = perform_move(source.full_path, dest_path)
            success_message = f'Moved {source.name}'
        else:
            res = perform_copy(source.full_path, dest_path)
            success_message = f'Copied {source.name}'
        if res.type == ActionType.ERROR:
            return res
        self._rebuild_content()
        return ActionResult(ActionType.REFRESH, success_message)

""",
)

replace_once(
    "retrotui/core/file_operations.py",
    "import os\nimport logging\nimport threading\n",
    "import inspect\nimport os\nimport logging\nimport threading\n",
)
replace_once(
    "retrotui/core/file_operations.py",
    "from .actions import ActionResult, ActionType\n",
    "from .actions import ActionResult, ActionType\nfrom .file_transfer import TransferCancelled\n",
)
replace_once(
    "retrotui/core/file_operations.py",
    "\n\nclass FileOperationManager:\n",
    """

class _CombinedCancelEvent:
    """Cancellation probe that becomes set when any owned event is set."""

    def __init__(self, *events):
        self._events = tuple(event for event in events if event is not None)

    def is_set(self):
        return any(event.is_set() for event in self._events)


class FileOperationManager:
""",
)
replace_between(
    "retrotui/core/file_operations.py",
    "    def _start_background_operation",
    "    def has_background_operation",
    """    @staticmethod
    def _invoke_worker(worker, cancel_event, progress_callback):
        """Call legacy or cooperative workers without masking worker TypeErrors."""
        try:
            params = inspect.signature(worker).parameters
        except (TypeError, ValueError):
            return worker()

        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in params.values()
        )
        kwargs = {}
        cancel_param = params.get("cancel_event")
        if accepts_kwargs or (
            cancel_param is not None
            and cancel_param.kind != inspect.Parameter.POSITIONAL_ONLY
        ):
            kwargs["cancel_event"] = cancel_event
        progress_param = params.get("progress_callback")
        if accepts_kwargs or (
            progress_param is not None
            and progress_param.kind != inspect.Parameter.POSITIONAL_ONLY
        ):
            kwargs["progress_callback"] = progress_callback
        return worker(**kwargs)

    @staticmethod
    def _normalize_progress(progress):
        if hasattr(progress, "as_dict"):
            progress = progress.as_dict()
        if not isinstance(progress, dict):
            return {}
        return dict(progress)

    def cancel_background_operation(self):
        """Request cancellation for the active cooperative file operation."""
        state = getattr(self._app, '_background_operation', None)
        if not state or not state.get('cancellable') or state.get('done'):
            return False
        event = state.get('operation_cancel_event')
        if event is None:
            return False
        event.set()
        lock = state.get('lock')
        if lock is not None:
            with lock:
                state['cancel_requested'] = True
        else:
            state['cancel_requested'] = True
        dialog = state.get('dialog')
        if dialog and hasattr(dialog, 'set_cancel_requested'):
            dialog.set_cancel_requested()
        bus = getattr(self._app, '_event_bus', None)
        if bus is not None:
            bus.publish("file_op.cancel_requested", data={"title": state.get('dialog_title', '')})
        self._app._dirty = True
        return True

    def _start_background_operation(self, *, title, message, worker, source_win):
        """Run blocking filesystem operation in an owned worker scope."""
        if self._shutting_down or self._worker_scope.closed:
            return ActionResult(ActionType.ERROR, 'Application is shutting down.')
        state = getattr(self._app, '_background_operation', None)
        if state:
            return ActionResult(ActionType.ERROR, 'Another operation is already running.')

        cancellable = bool(getattr(worker, '_retrotui_cancellable', False))
        if cancellable:
            progress_dialog = ProgressDialog(
                title, message, width=62,
                cancel_callback=self.cancel_background_operation,
            )
        else:
            progress_dialog = ProgressDialog(title, message, width=62)
        op_lock = threading.Lock()
        operation_cancel_event = threading.Event()
        op_state = {
            'dialog': progress_dialog,
            'source_win': source_win,
            'worker_result': None,
            'done': False,
            'cancelled': False,
            'cancel_requested': False,
            'cancellable': cancellable,
            'progress': {},
            'operation_cancel_event': operation_cancel_event,
            'started_at': time.monotonic(),
            'thread': None,
        }

        def _publish_progress(progress):
            data = self._normalize_progress(progress)
            with op_lock:
                op_state['progress'] = data

        def _runner(scope_cancel_event):
            cancel_event = _CombinedCancelEvent(scope_cancel_event, operation_cancel_event)
            cancelled = False
            try:
                result = self._invoke_worker(worker, cancel_event, _publish_progress)
            except TransferCancelled:
                cancelled = True
                result = ActionResult(ActionType.REFRESH, 'Operation cancelled.')
            except _BACKGROUND_WORKER_ERRORS as exc:
                result = ActionResult(ActionType.ERROR, str(exc))
            with op_lock:
                op_state['worker_result'] = result
                op_state['cancelled'] = cancelled
                op_state['done'] = True

        op_state['lock'] = op_lock
        op_state['dialog_title'] = title
        op_state['cancel_event'] = operation_cancel_event
        self._app._background_operation = op_state
        self._app.dialog = progress_dialog
        thread = self._worker_scope.start(_runner, name='retrotui-file-op')
        if thread is None:
            self._app._background_operation = None
            if self._app.dialog is progress_dialog:
                self._app.dialog = None
            return ActionResult(ActionType.ERROR, 'Application is shutting down.')
        op_state['thread'] = thread
        bus = getattr(self._app, '_event_bus', None)
        if bus is not None:
            bus.publish("file_op.started", data={"title": title, "cancellable": cancellable})
        return None

""",
)
replace_between(
    "retrotui/core/file_operations.py",
    "    def poll_background_operation",
    "    def _run_file_operation_with_progress",
    """    def poll_background_operation(self):
        """Advance progress state and dispatch completion when worker finishes."""
        state = getattr(self._app, '_background_operation', None)
        if not state or self._shutting_down:
            return

        self._app._dirty = True
        elapsed = max(0.0, time.monotonic() - state['started_at'])
        dialog = state.get('dialog')
        if dialog and hasattr(dialog, 'set_elapsed'):
            dialog.set_elapsed(elapsed)

        lock = state.get('lock')
        if lock is not None:
            with lock:
                done = state.get('done')
                result = state.get('worker_result')
                cancelled = bool(state.get('cancelled'))
                progress = dict(state.get('progress') or {})
                cancel_requested = bool(state.get('cancel_requested'))
        else:
            done = state.get('done')
            result = state.get('worker_result')
            cancelled = bool(state.get('cancelled'))
            progress = dict(state.get('progress') or {})
            cancel_requested = bool(state.get('cancel_requested'))

        if dialog and progress and hasattr(dialog, 'set_progress'):
            dialog.set_progress(progress)
        if dialog and cancel_requested and hasattr(dialog, 'set_cancel_requested'):
            dialog.set_cancel_requested()
        if not done:
            return

        if self._app.dialog is dialog:
            self._app.dialog = None
        self._app._background_operation = None

        bus = getattr(self._app, '_event_bus', None)
        if cancelled:
            if bus is not None:
                bus.publish("file_op.cancelled", data={"title": state.get('dialog_title', '')})
            return

        if bus is not None:
            is_error = result is not None and getattr(result, 'type', None) == ActionType.ERROR
            topic = "file_op.failed" if is_error else "file_op.completed"
            bus.publish(topic, data={"title": state.get('dialog_title', '')})

        if result is not None:
            self._app._dispatch_window_result(result, state.get('source_win'))

""",
)
text = read("retrotui/core/file_operations.py")
start = text.find("    def _run_file_operation_with_progress")
if start < 0:
    raise RuntimeError("file_operations.py: run method marker not found")
write("retrotui/core/file_operations.py", text[:start] + """    def _run_file_operation_with_progress(self, win, *, operation, destination=None, source_path=None):
        """Run file operation directly or via background worker with progress dialog."""
        entry = self._window_selected_entry(win)
        operation = str(operation).lower()

        if operation in ('copy', 'move') and source_path:
            method_name = 'copy_path_to' if operation == 'copy' else 'move_path_to'
            transfer_path_to = getattr(win, method_name, None)
            if not callable(transfer_path_to):
                return ActionResult(ActionType.ERROR, f'Window does not support source-path {operation}.')
            name = os.path.basename(os.path.normpath(str(source_path))) or 'item'
            entry = SimpleNamespace(
                name=name,
                full_path=source_path,
                is_dir=os.path.isdir(source_path),
                size=None,
            )

            def worker(cancel_event=None, progress_callback=None, transfer=transfer_path_to):
                return transfer(
                    source_path,
                    destination,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )

            title = 'Copying' if operation == 'copy' else 'Moving'
            details = f"{title}:\n{name}"
        elif operation == 'copy':
            def worker(cancel_event=None, progress_callback=None):
                return win.copy_selected(
                    destination,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )

            title = 'Copying'
            details = f"Copying:\n{getattr(entry, 'name', 'item')}"
        elif operation == 'move':
            def worker(cancel_event=None, progress_callback=None):
                return win.move_selected(
                    destination,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )

            title = 'Moving'
            details = f"Moving:\n{getattr(entry, 'name', 'item')}"
        elif operation == 'delete':
            def worker():
                return win.delete_selected()

            title = 'Deleting'
            details = f"Deleting:\n{getattr(entry, 'name', 'item')}"
        else:
            return ActionResult(ActionType.ERROR, f'Unsupported file operation: {operation}')

        if operation in ('copy', 'move'):
            setattr(worker, '_retrotui_cancellable', True)

        if not self._is_long_file_operation(entry):
            return worker()

        message = f'{details}\n\nPlease wait...'
        return self._app._start_background_operation(
            title=title,
            message=message,
            worker=worker,
            source_win=win,
        )
""" + "\n")

dialog_text = read("retrotui/ui/dialog.py")
dialog_start = dialog_text.find("class ProgressDialog:")
if dialog_start < 0:
    raise RuntimeError("dialog.py: ProgressDialog marker not found")
write("retrotui/ui/dialog.py", dialog_text[:dialog_start] + """class ProgressDialog:
    """Modal progress dialog for background operations."""

    SPINNER_FRAMES = ('|', '/', '-', '\\')

    def __init__(self, title, message, width=58, cancel_callback=None):
        self.title = title
        self.message = message
        self.buttons = []
        self.width = max(width, len(title) + 8)
        self.lines = _wrap_dialog_message(message, self.width - 6)
        self.elapsed_seconds = 0.0
        self.progress = {}
        self.cancel_callback = cancel_callback
        self.cancel_requested = False
        self.height = len(self.lines) + 10
        self._cancel_y = 0
        self._cancel_x_start = 0
        self._cancel_x_end = 0

    def set_elapsed(self, seconds):
        self.elapsed_seconds = max(0.0, float(seconds))

    def set_progress(self, progress):
        if hasattr(progress, "as_dict"):
            progress = progress.as_dict()
        self.progress = dict(progress or {})

    def set_cancel_requested(self):
        self.cancel_requested = True

    def _request_cancel(self):
        if self.cancel_requested or not callable(self.cancel_callback):
            return
        self.cancel_requested = True
        self.cancel_callback()

    def _progress_fraction(self):
        fraction = self.progress.get("fraction")
        if fraction is not None:
            try:
                return max(0.0, min(1.0, float(fraction)))
            except (TypeError, ValueError):
                return None
        total_bytes = int(self.progress.get("total_bytes", 0) or 0)
        if total_bytes > 0:
            return max(0.0, min(1.0, int(self.progress.get("bytes_done", 0) or 0) / total_bytes))
        total_files = int(self.progress.get("total_files", 0) or 0)
        if total_files > 0:
            return max(0.0, min(1.0, int(self.progress.get("files_done", 0) or 0) / total_files))
        return None

    def draw(self, stdscr, frame_size=None):
        if frame_size is not None:
            max_h, max_w = frame_size
        else:
            max_h, max_w = stdscr.getmaxyx()
        x = (max_w - self.width) // 2
        y = (max_h - self.height) // 2
        attr = theme_attr('dialog')
        title_attr = theme_attr('window_title') | curses.A_BOLD
        info_attr = theme_attr('status') | curses.A_BOLD

        for row in range(self.height):
            safe_addstr(stdscr, y + row + 1, x + 2, ' ' * self.width, curses.A_DIM, _bounds=frame_size)
        for row in range(self.height):
            safe_addstr(stdscr, y + row, x, ' ' * self.width, attr, _bounds=frame_size)
        draw_box(stdscr, y, x, self.height, self.width, attr, double=True, _bounds=frame_size)
        safe_addstr(stdscr, y, x + 1, f' {self.title} '.ljust(self.width - 2), title_attr, _bounds=frame_size)

        for i, line in enumerate(self.lines):
            safe_addstr(stdscr, y + 2 + i, x + 3, line[: self.width - 6], attr, _bounds=frame_size)

        fraction = self._progress_fraction()
        bar_width = max(8, self.width - 14)
        if fraction is None:
            fill = 0
            percent = " --%"
        else:
            fill = int(round(bar_width * fraction))
            percent = f"{fraction * 100:3.0f}%"
        bar = '[' + ('#' * fill).ljust(bar_width, '-') + ']'
        safe_addstr(
            stdscr, y + self.height - 5, x + 3,
            f'{bar} {percent}'[: self.width - 6].ljust(self.width - 6),
            info_attr, _bounds=frame_size,
        )

        spinner = self.SPINNER_FRAMES[int(self.elapsed_seconds * 8) % len(self.SPINNER_FRAMES)]
        phase = str(self.progress.get("phase") or "working").replace("_", " ").title()
        current_path = str(self.progress.get("current_path") or "")
        status = (
            f'Cancelling {spinner}  {self.elapsed_seconds:5.1f}s'
            if self.cancel_requested
            else f'{phase} {spinner}  {self.elapsed_seconds:5.1f}s'
        )
        if current_path:
            status = f'{status}  {current_path}'
        safe_addstr(
            stdscr, y + self.height - 4, x + 3,
            status[: self.width - 6].ljust(self.width - 6),
            info_attr, _bounds=frame_size,
        )

        if callable(self.cancel_callback):
            label = '[ Cancelling... ]' if self.cancel_requested else '[ Cancel: Esc/C ]'
            cancel_x = x + max(3, (self.width - len(label)) // 2)
            cancel_y = y + self.height - 2
            safe_addstr(stdscr, cancel_y, cancel_x, label, info_attr, _bounds=frame_size)
            self._cancel_y = cancel_y
            self._cancel_x_start = cancel_x
            self._cancel_x_end = cancel_x + len(label)

    def handle_click(self, mx, my):
        if (
            callable(self.cancel_callback)
            and my == self._cancel_y
            and self._cancel_x_start <= mx < self._cancel_x_end
        ):
            self._request_cancel()
        return -1

    def handle_key(self, key):
        key_code = normalize_key_code(key)
        if callable(self.cancel_callback) and key_code in (27, ord('c'), ord('C')):
            self._request_cancel()
        return -1
""" + "\n")

print("cooperative file-transfer hardening applied")

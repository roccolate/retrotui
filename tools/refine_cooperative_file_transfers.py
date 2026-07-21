#!/usr/bin/env python3
"""Apply compatibility refinements after the cooperative transfer preparer."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, content):
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path, old, new):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    write(path, text.replace(old, new, 1))


replace_once(
    "retrotui/core/file_operations.py",
    """            try:
                result = self._invoke_worker(worker, cancel_event, _publish_progress)
            except TransferCancelled:
""",
    """            try:
                if cancellable:
                    result = self._invoke_worker(worker, cancel_event, _publish_progress)
                else:
                    result = worker()
            except TransferCancelled:
""",
)

for old, new in (
    (
        """            def worker(cancel_event=None, progress_callback=None, transfer=transfer_path_to):
                return transfer(
                    source_path,
                    destination,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )
""",
        """            def worker(cancel_event=None, progress_callback=None, transfer=transfer_path_to):
                if cancel_event is None and progress_callback is None:
                    return transfer(source_path, destination)
                return transfer(
                    source_path,
                    destination,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )
""",
    ),
    (
        """            def worker(cancel_event=None, progress_callback=None):
                return win.copy_selected(
                    destination,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )
""",
        """            def worker(cancel_event=None, progress_callback=None):
                if cancel_event is None and progress_callback is None:
                    return win.copy_selected(destination)
                return win.copy_selected(
                    destination,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )
""",
    ),
    (
        """            def worker(cancel_event=None, progress_callback=None):
                return win.move_selected(
                    destination,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )
""",
        """            def worker(cancel_event=None, progress_callback=None):
                if cancel_event is None and progress_callback is None:
                    return win.move_selected(destination)
                return win.move_selected(
                    destination,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )
""",
    ),
):
    replace_once("retrotui/core/file_operations.py", old, new)

window_path = "retrotui/apps/filemanager/window.py"
for old, new in (
    (
        """        res = perform_copy(
            entry.full_path,
            target,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
""",
        """        if cancel_event is None and progress_callback is None:
            res = perform_copy(entry.full_path, target)
        else:
            res = perform_copy(
                entry.full_path,
                target,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
            )
""",
    ),
    (
        """        res = perform_copy(
            source_path,
            target,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
""",
        """        if cancel_event is None and progress_callback is None:
            res = perform_copy(source_path, target)
        else:
            res = perform_copy(
                source_path,
                target,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
            )
""",
    ),
    (
        """        res = perform_move(
            entry.full_path,
            target,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
""",
        """        if cancel_event is None and progress_callback is None:
            res = perform_move(entry.full_path, target)
        else:
            res = perform_move(
                entry.full_path,
                target,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
            )
""",
    ),
    (
        """        res = perform_move(
            source_path,
            target,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
""",
        """        if cancel_event is None and progress_callback is None:
            res = perform_move(source_path, target)
        else:
            res = perform_move(
                source_path,
                target,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
            )
""",
    ),
):
    replace_once(window_path, old, new)

write("tests/test_file_transfer.py", '''import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


class CooperativeFileTransferTests(unittest.TestCase):
    def test_copy_file_reports_progress_and_commits_complete_payload(self):
        from retrotui.core import file_transfer as transfer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            dest = root / "dest.bin"
            payload = (b"retro-tui-" * 300_000) + b"done"
            source.write_bytes(payload)
            updates = []

            result = transfer.cooperative_copy(
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
        from retrotui.core import file_transfer as transfer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "large.bin"
            dest = root / "dest.bin"
            source.write_bytes(b"x" * (3 * 1024 * 1024))
            cancel_event = threading.Event()

            def on_progress(progress):
                if progress.bytes_done >= 64 * 1024:
                    cancel_event.set()

            with self.assertRaises(transfer.TransferCancelled):
                transfer.cooperative_copy(
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
        from retrotui.core import file_transfer as transfer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tree"
            dest = root / "tree-copy"
            (source / "nested").mkdir(parents=True)
            (source / "a.txt").write_text("alpha", encoding="utf-8")
            (source / "nested" / "b.txt").write_text("beta", encoding="utf-8")

            result = transfer.cooperative_copy(source, dest, chunk_size=2)

            self.assertEqual((dest / "a.txt").read_text(encoding="utf-8"), "alpha")
            self.assertEqual(
                (dest / "nested" / "b.txt").read_text(encoding="utf-8"),
                "beta",
            )
            self.assertEqual(result.files_done, 2)
            self.assertEqual(result.total_files, 2)

    def test_cross_filesystem_move_rolls_back_destination_when_source_cleanup_fails(self):
        from retrotui.core import file_transfer as transfer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            dest = root / "dest.txt"
            source.write_text("payload", encoding="utf-8")

            with (
                mock.patch.object(transfer, "_try_atomic_move", return_value=False),
                mock.patch.object(
                    transfer,
                    "_remove_source_after_copy",
                    side_effect=OSError("cannot remove source"),
                ),
            ):
                with self.assertRaisesRegex(OSError, "rolled back"):
                    transfer.cooperative_move(source, dest)

            self.assertTrue(source.exists())
            self.assertFalse(dest.exists())

    def test_atomic_move_does_not_copy_payload(self):
        from retrotui.core import file_transfer as transfer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            dest = root / "dest.txt"
            source.write_text("payload", encoding="utf-8")

            with mock.patch.object(
                transfer,
                "cooperative_copy",
                side_effect=AssertionError("copy fallback should not run"),
            ):
                result = transfer.cooperative_move(source, dest)

            self.assertFalse(source.exists())
            self.assertEqual(dest.read_text(encoding="utf-8"), "payload")
            self.assertEqual(result.phase, "completed")


if __name__ == "__main__":
    unittest.main()
''')

write("tests/test_file_operation_progress.py", '''import threading
import time
import types
import unittest
from unittest import mock


class _Bus:
    def __init__(self):
        self.events = []

    def publish(self, topic, data=None, **_kwargs):
        self.events.append((topic, data))


class CooperativeProgressTests(unittest.TestCase):
    def test_progress_dialog_requests_cancel_without_closing_itself(self):
        from retrotui.ui.dialog import ProgressDialog

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
        from retrotui.core.actions import ActionResult, ActionType
        from retrotui.core.file_operations import FileOperationManager
        from retrotui.core.file_transfer import TransferCancelled
        from retrotui.ui.dialog import ProgressDialog

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
        from retrotui.core.actions import ActionResult, ActionType
        from retrotui.core.file_operations import FileOperationManager

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
''')

print("cooperative file-transfer compatibility refinements applied")

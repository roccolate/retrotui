import threading
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

    def test_custom_worker_exception_reaches_terminal_error_state(self):
        from retrotui.core.actions import ActionType
        from retrotui.core.file_operations import FileOperationManager

        class CustomWorkerError(Exception):
            pass

        app = types.SimpleNamespace(
            _background_operation=None,
            dialog=None,
            _event_bus=None,
            _dirty=False,
            _dispatch_window_result=mock.Mock(),
        )
        manager = FileOperationManager(app)
        source = object()

        def worker():
            raise CustomWorkerError("custom failure")

        self.assertIsNone(manager._start_background_operation(
            title="Failing",
            message="payload.bin",
            worker=worker,
            source_win=source,
        ))
        manager._worker_scope.join(timeout=1.0)
        manager.poll_background_operation()

        self.assertIsNone(app._background_operation)
        app._dispatch_window_result.assert_called_once()
        result, dispatched_source = app._dispatch_window_result.call_args.args
        self.assertEqual(result.type, ActionType.ERROR)
        self.assertEqual(result.payload, "custom failure")
        self.assertIs(dispatched_source, source)

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

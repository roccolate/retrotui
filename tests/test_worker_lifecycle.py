import threading
import time
import types
import unittest
from unittest import mock

from retrotui.apps.filemanager.window import FileManagerWindow
from retrotui.apps.image_viewer import ImageViewerWindow
from retrotui.apps.retronet import RetroNetWindow, _TabState
from retrotui.apps.wifi_manager import WifiManagerWindow
from retrotui.core.actions import ActionResult, ActionType
from retrotui.core.worker_scope import WorkerScope
from retrotui.ui.window import Window


class WorkerScopeTests(unittest.TestCase):
    def test_shutdown_signals_and_joins_cooperative_worker(self):
        scope = WorkerScope("test", join_timeout=0.5)
        started = threading.Event()
        stopped = threading.Event()

        def worker(cancel_event):
            started.set()
            cancel_event.wait(1.0)
            stopped.set()

        thread = scope.start(worker, name="test-worker")
        self.assertIsNotNone(thread)
        self.assertTrue(started.wait(0.5))
        self.assertTrue(scope.shutdown(require_stopped=True))
        self.assertTrue(stopped.is_set())
        self.assertEqual(scope.active_count, 0)

    def test_closed_scope_rejects_new_workers(self):
        scope = WorkerScope("closed")
        scope.cancel()
        self.assertIsNone(scope.start(lambda _cancel: None))

    def test_bounded_shutdown_can_report_uninterruptible_worker(self):
        scope = WorkerScope("blocked", join_timeout=0.01)
        release = threading.Event()
        scope.start(lambda _cancel: release.wait(1.0), name="blocked-worker")
        try:
            self.assertFalse(scope.shutdown(require_stopped=True))
        finally:
            release.set()
            scope.join(timeout=0.5)


class WindowWorkerOwnershipTests(unittest.TestCase):
    def test_window_close_cancels_owned_worker(self):
        window = Window("test", 0, 0, 20, 8)
        observed = threading.Event()

        def worker(cancel_event):
            cancel_event.wait(1.0)
            observed.set()

        window._start_worker(worker, name="window-worker")
        self.assertTrue(window.close())
        self.assertTrue(observed.wait(0.5))
        self.assertTrue(window.worker_cancelled())

    def test_retronet_request_identity_survives_tab_index_reuse(self):
        window = RetroNetWindow.__new__(RetroNetWindow)
        Window.__init__(window, "RetroNet", 0, 0, 40, 12)
        window._lock = threading.Lock()
        window.tabs = [
            _TabState(tab_id=10, load_generation=2),
            _TabState(tab_id=11, load_generation=1),
        ]
        window.active_tab_idx = 0

        with window._lock:
            self.assertEqual(window._tab_request_is_current_locked(10, 2), 0)
            self.assertIsNone(window._tab_request_is_current_locked(10, 1))
            del window.tabs[0]
            window.tabs.insert(0, _TabState(tab_id=12, load_generation=2))
            self.assertIsNone(window._tab_request_is_current_locked(10, 2))

    def test_component_close_methods_cancel_scope_and_clear_pending_state(self):
        image = ImageViewerWindow.__new__(ImageViewerWindow)
        Window.__init__(image, "image", 0, 0, 20, 8)
        image._cancel_event = threading.Event()
        image._render_lock = threading.Lock()
        image._render_request = (1,)
        image._render_pending = True
        self.assertTrue(image.close())
        self.assertTrue(image._cancel_event.is_set())
        self.assertIsNone(image._render_request)

        preview = FileManagerWindow.__new__(FileManagerWindow)
        preview._worker_scope = WorkerScope("file-preview-test")
        preview._preview_lock = threading.Lock()
        preview._preview_pending = {("key",)}
        preview._preview_cache = {"key": ("key",), "lines": ["old"]}
        preview._preview_redraw_pending = True
        self.assertTrue(preview.close())
        self.assertFalse(preview._preview_pending)
        self.assertIsNone(preview._preview_cache["key"])

        wifi = WifiManagerWindow.__new__(WifiManagerWindow)
        Window.__init__(wifi, "wifi", 0, 0, 50, 15)
        wifi._scan_lock = threading.Lock()
        wifi._connect_lock = threading.Lock()
        wifi._scan_in_progress = True
        wifi._scan_result_ready = True
        wifi._scan_error = "error"
        wifi._connect_in_progress = True
        wifi._connect_result = (True, "")
        wifi._connecting_ssid = "network"
        wifi._dialog = object()
        self.assertTrue(wifi.close())
        self.assertFalse(wifi._scan_in_progress)
        self.assertFalse(wifi._connect_in_progress)
        self.assertIsNone(wifi._dialog)


class FileOperationShutdownTests(unittest.TestCase):
    def test_shutdown_suppresses_late_ui_dispatch(self):
        app = types.SimpleNamespace(
            _background_operation=None,
            dialog=None,
            _event_bus=None,
            _dirty=False,
            _dispatch_window_result=mock.Mock(),
        )
        from retrotui.core.file_operations import FileOperationManager

        manager = FileOperationManager(app)
        release = threading.Event()

        def worker():
            release.wait(1.0)
            return ActionResult(ActionType.REFRESH, "done")

        self.assertIsNone(
            manager._start_background_operation(
                title="Copying",
                message="Please wait",
                worker=worker,
                source_win=object(),
            )
        )
        self.assertFalse(manager.shutdown(timeout=0.01))
        self.assertIsNone(app._background_operation)
        release.set()
        manager._worker_scope.join(timeout=0.5)
        manager.poll_background_operation()
        app._dispatch_window_result.assert_not_called()

    def test_shutdown_rejects_new_file_operations(self):
        app = types.SimpleNamespace(
            _background_operation=None,
            dialog=None,
            _event_bus=None,
        )
        from retrotui.core.file_operations import FileOperationManager

        manager = FileOperationManager(app)
        self.assertTrue(manager.shutdown(timeout=0.0))
        result = manager._start_background_operation(
            title="Copying",
            message="Please wait",
            worker=lambda: None,
            source_win=None,
        )
        self.assertEqual(result.type, ActionType.ERROR)
        self.assertIn("shutting down", result.payload.lower())


if __name__ == "__main__":
    unittest.main()

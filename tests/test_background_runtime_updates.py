import threading
import types
import unittest
from unittest import mock

from retrotui.core.actions import ActionResult, ActionType
from retrotui.core.runtime_updates import RenderUpdate
from retrotui.core.window_manager import WindowManager


class BackgroundRuntimeUpdateTests(unittest.TestCase):
    def _make_manager(self, windows=()):
        # Import lazily so this test module cannot retain stale Dialog classes
        # when test_core_app reloads the RetroTUI module graph.
        from retrotui.core.file_operations import FileOperationManager

        app = types.SimpleNamespace(
            _background_operation=None,
            dialog=None,
            _event_bus=None,
            _dirty=False,
            windows=list(windows),
            _dispatch_window_result=mock.Mock(),
        )
        manager = FileOperationManager(app)
        return app, manager

    @staticmethod
    def _running_state(dialog, *, source=None):
        return {
            "dialog": dialog,
            "source_win": source,
            "source_window_id": getattr(source, "id", None),
            "worker_result": None,
            "done": False,
            "cancelled": False,
            "cancel_requested": False,
            "progress": {"fraction": 0.5},
            "started_at": 0.0,
            "lock": threading.Lock(),
            "dialog_title": "Copying",
        }

    def test_progress_poll_requests_overlay_without_dirtying_full_frame(self):
        dialog = types.SimpleNamespace(
            set_elapsed=mock.Mock(),
            set_progress=mock.Mock(),
            set_cancel_requested=mock.Mock(),
        )
        app, manager = self._make_manager()
        app.dialog = dialog
        app._background_operation = self._running_state(dialog)

        with mock.patch("retrotui.core.file_operations.time.monotonic", return_value=1.01):
            update = manager.poll_background_operation()

        self.assertEqual(update, RenderUpdate.OVERLAY)
        self.assertFalse(app._dirty)
        dialog.set_elapsed.assert_called_once_with(1.01)
        dialog.set_progress.assert_called_once_with({"fraction": 0.5})

    def test_unchanged_progress_visuals_do_not_request_another_render(self):
        dialog = types.SimpleNamespace(
            set_elapsed=mock.Mock(),
            set_progress=mock.Mock(),
            set_cancel_requested=mock.Mock(),
        )
        app, manager = self._make_manager()
        app.dialog = dialog
        app._background_operation = self._running_state(dialog)

        with mock.patch("retrotui.core.file_operations.time.monotonic", return_value=1.01):
            self.assertEqual(manager.poll_background_operation(), RenderUpdate.OVERLAY)
        with mock.patch("retrotui.core.file_operations.time.monotonic", return_value=1.04):
            self.assertEqual(manager.poll_background_operation(), RenderUpdate.NONE)

        dialog.set_elapsed.assert_called_once()
        dialog.set_progress.assert_called_once()

    def test_completion_discards_non_error_result_for_closed_source(self):
        source = types.SimpleNamespace(id=17)
        dialog = types.SimpleNamespace(set_elapsed=mock.Mock(), set_progress=mock.Mock())
        app, manager = self._make_manager(windows=())
        app.dialog = dialog
        state = self._running_state(dialog, source=source)
        state.update(
            done=True,
            worker_result=ActionResult(ActionType.REFRESH, "done"),
        )
        app._background_operation = state

        with mock.patch("retrotui.core.file_operations.time.monotonic", return_value=2.0):
            update = manager.poll_background_operation()

        self.assertEqual(update, RenderUpdate.FULL)
        self.assertIsNone(app._background_operation)
        app._dispatch_window_result.assert_not_called()

    def test_completion_detaches_error_from_closed_source(self):
        source = types.SimpleNamespace(id=18)
        dialog = types.SimpleNamespace(set_elapsed=mock.Mock(), set_progress=mock.Mock())
        app, manager = self._make_manager(windows=())
        app.dialog = dialog
        result = ActionResult(ActionType.ERROR, "failed")
        state = self._running_state(dialog, source=source)
        state.update(done=True, worker_result=result)
        app._background_operation = state

        with mock.patch("retrotui.core.file_operations.time.monotonic", return_value=2.0):
            update = manager.poll_background_operation()

        self.assertEqual(update, RenderUpdate.FULL)
        app._dispatch_window_result.assert_called_once_with(result, None)

    def test_window_registry_checks_identity_and_generation(self):
        window = types.SimpleNamespace(id=9)
        manager = WindowManager(None)
        manager.windows = [window]

        self.assertTrue(manager.is_window_registered(window, expected_id=9))
        self.assertFalse(manager.is_window_registered(window, expected_id=10))
        self.assertFalse(manager.is_window_registered(types.SimpleNamespace(id=9), expected_id=9))


class BackgroundOverlayRenderTests(unittest.TestCase):
    def test_overlay_refresh_does_not_erase_or_redraw_desktop(self):
        from retrotui.core import event_loop

        stdscr = types.SimpleNamespace(
            getmaxyx=mock.Mock(return_value=(25, 80)),
            erase=mock.Mock(),
            noutrefresh=mock.Mock(),
        )
        dialog = types.SimpleNamespace(draw=mock.Mock())
        app = types.SimpleNamespace(
            stdscr=stdscr,
            dialog=dialog,
            _dirty=False,
            _frame_size=(25, 80),
            _notifications=None,
        )

        with mock.patch.object(event_loop.curses, "doupdate", create=True) as doupdate:
            self.assertTrue(event_loop._refresh_dialog_overlay(app))

        dialog.draw.assert_called_once_with(stdscr, frame_size=(25, 80))
        stdscr.erase.assert_not_called()
        stdscr.noutrefresh.assert_called_once_with()
        doupdate.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

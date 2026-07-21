import types
import unittest
from unittest import mock

from retrotui.core.drag_drop import DragDropManager


class DragDropPrecedenceTests(unittest.TestCase):
    def _manager(self):
        app = types.SimpleNamespace(
            windows=[],
            _dispatch_window_result=mock.Mock(),
        )
        return app, DragDropManager(app)

    def test_explicit_drop_handler_precedes_generic_open_path(self):
        app, manager = self._manager()
        result = object()
        target = types.SimpleNamespace(
            accept_dropped_path=mock.Mock(return_value=result),
            open_path=mock.Mock(return_value=None),
        )

        manager.dispatch_drop(
            target,
            {"type": "file_path", "path": "/tmp/demo.txt"},
        )

        target.accept_dropped_path.assert_called_once_with("/tmp/demo.txt")
        target.open_path.assert_not_called()
        app._dispatch_window_result.assert_called_once_with(result, target)

    def test_open_path_is_fallback_when_no_explicit_drop_handler_exists(self):
        app, manager = self._manager()
        result = object()
        target = types.SimpleNamespace(
            open_path=mock.Mock(return_value=result),
        )

        manager.dispatch_drop(
            target,
            {"type": "file_path", "path": "/tmp/demo.txt"},
        )

        target.open_path.assert_called_once_with("/tmp/demo.txt")
        app._dispatch_window_result.assert_called_once_with(result, target)

    def test_explicit_handler_failure_does_not_fall_back_to_navigation(self):
        app, manager = self._manager()
        target = types.SimpleNamespace(
            accept_dropped_path=mock.Mock(side_effect=PermissionError("denied")),
            open_path=mock.Mock(return_value=None),
        )

        manager.dispatch_drop(
            target,
            {"type": "file_path", "path": "/tmp/demo.txt"},
        )

        target.accept_dropped_path.assert_called_once_with("/tmp/demo.txt")
        target.open_path.assert_not_called()
        app._dispatch_window_result.assert_not_called()

    def test_target_capability_accepts_specific_or_generic_handler(self):
        self.assertTrue(
            DragDropManager.supports_file_drop_target(
                types.SimpleNamespace(accept_dropped_path=lambda path: path)
            )
        )
        self.assertTrue(
            DragDropManager.supports_file_drop_target(
                types.SimpleNamespace(open_path=lambda path: path)
            )
        )
        self.assertFalse(
            DragDropManager.supports_file_drop_target(types.SimpleNamespace())
        )

    def test_invalid_payload_never_calls_target(self):
        app, manager = self._manager()
        target = types.SimpleNamespace(
            accept_dropped_path=mock.Mock(),
            open_path=mock.Mock(),
        )

        manager.dispatch_drop(target, None)
        manager.dispatch_drop(target, {})
        manager.dispatch_drop(target, {"type": "other", "path": "/tmp/demo.txt"})
        manager.dispatch_drop(target, {"type": "file_path"})

        target.accept_dropped_path.assert_not_called()
        target.open_path.assert_not_called()
        app._dispatch_window_result.assert_not_called()


if __name__ == "__main__":
    unittest.main()

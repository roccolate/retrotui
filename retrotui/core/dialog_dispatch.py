"""
Dialog dispatch logic extracted from the main RetroTUI application class.

``DialogDispatcher`` handles ActionResult objects returned by windows and
processes dialog button results, keeping the core App class leaner.
"""
import logging

from ..ui.dialog import Dialog
from .actions import ActionType, AppAction

LOGGER = logging.getLogger(__name__)


class DialogDispatcher:
    """Handles ActionResult dispatching and dialog result resolution for RetroTUI.

    Takes the app instance as a constructor parameter and delegates to its
    methods/attributes when accessing application state.
    """

    # Dispatch table: ActionType -> method name on the app (methods that require source_win).
    # REQUEST_SAVE_CONFIRM is intentionally NOT here: the dialog needs the
    # payload's ``on_discard`` callback, so it is handled inline below.
    _RESULT_DISPATCH = {
        ActionType.REQUEST_SAVE_AS: 'show_save_as_dialog',
        ActionType.REQUEST_OPEN_PATH: 'show_open_dialog',
        ActionType.REQUEST_RENAME_ENTRY: 'show_rename_dialog',
        ActionType.REQUEST_DELETE_CONFIRM: 'show_delete_confirm_dialog',
        ActionType.REQUEST_EMPTY_TRASH_CONFIRM: 'show_empty_trash_confirm_dialog',
        ActionType.REQUEST_RESTORE_TRASH: 'show_restore_trash',
        ActionType.REQUEST_COPY_ENTRY: 'show_copy_dialog',
        ActionType.REQUEST_MOVE_ENTRY: 'show_move_dialog',
        ActionType.REQUEST_NEW_DIR: 'show_new_dir_dialog',
        ActionType.REQUEST_NEW_FILE: 'show_new_file_dialog',
    }

    def __init__(self, app):
        self._app = app

    def dispatch_window_result(self, result, source_win):
        """Handle ActionResult returned by window/dialog callbacks."""
        if not result or result is True:
            return True

        if not hasattr(result, 'type') or not hasattr(result, 'payload'):
            LOGGER.debug('Ignoring non-ActionResult return from window callback: %r', result)
            return True

        result_type = result.type
        result_payload = result.payload

        if result_type == ActionType.REFRESH:
            return True

        LOGGER.debug('Dispatching window result: type=%s payload=%r', result_type, result_payload)

        # Simple dialog dispatches (require source_win)
        method_name = self._RESULT_DISPATCH.get(result_type)
        if method_name is not None:
            if source_win:
                getattr(self._app, method_name)(source_win)
            return True

        if result_type == ActionType.OPEN_FILE and result_payload:
            self._app.open_file_viewer(result_payload)
            return True

        if result_type == ActionType.REQUEST_URL:
            self._app.show_url_dialog(source_win, result_payload)
            return True

        if result_type == ActionType.REQUEST_BOOKMARKS:
            if source_win is not None and hasattr(self._app, 'show_bookmarks_window'):
                self._app.show_bookmarks_window(source_win)
            return True

        if result_type == ActionType.REQUEST_ADD_BOOKMARK:
            if source_win is not None and hasattr(self._app, 'show_add_bookmark_dialog'):
                self._app.show_add_bookmark_dialog(source_win)
            return True

        if result_type == ActionType.EXECUTE:
            exec_action = self._app._normalize_action(result_payload)
            if exec_action == AppAction.CLOSE_WINDOW and source_win:
                self._app.close_window(source_win)
            elif exec_action:
                self._app.execute_action(exec_action)
            return True

        if result_type in (
            ActionType.REQUEST_COPY_BETWEEN_PANES,
            ActionType.REQUEST_MOVE_BETWEEN_PANES,
        ):
            operation = (
                'copy'
                if result_type == ActionType.REQUEST_COPY_BETWEEN_PANES
                else 'move'
            )
            destination = self._app._resolve_between_panes_destination(source_win, result_payload)
            if not source_win:
                self._app.dialog = Dialog(
                    'Operation Error',
                    f'Cannot {operation}: no source window context.',
                    ['OK'],
                    width=54,
                )
                return True
            if not destination:
                self._app.dialog = Dialog(
                    'Operation Error',
                    f'Cannot {operation}: destination pane path is unavailable.',
                    ['OK'],
                    width=62,
                )
                return True
            source_path = None
            if isinstance(result_payload, dict):
                source_path = result_payload.get('source')
            op_result = self._app._run_file_operation_with_progress(
                source_win,
                operation=operation,
                destination=destination,
                source_path=source_path,
            )
            if op_result is not None:
                self.dispatch_window_result(op_result, source_win)
            return True

        if result_type == ActionType.REQUEST_KILL_CONFIRM and source_win:
            self._app.show_kill_confirm_dialog(source_win, result_payload)
            return True

        if result_type == ActionType.SAVE_ERROR:
            message = result_payload or 'Unknown save error.'
            self._app.dialog = Dialog('Save Error', str(message), ['OK'], width=50)
            return True

        if result_type == ActionType.REQUEST_SAVE_CONFIRM and source_win:
            # Hand the payload's ``on_discard`` callback through so Discard
            # actually discards. The simple dispatch loop above would drop
            # the payload (it only forwards ``source_win``), so we dispatch
            # this ActionType inline. Without this pass-through the Discard
            # button silently does nothing and the next open_path bypasses
            # the confirmation (silent data loss).
            self._app._show_save_confirm_dialog(source_win, result_payload)
            return True

        if result_type == ActionType.ERROR:
            message = result_payload or 'Unknown error.'
            self._app.dialog = Dialog('Error', str(message), ['OK'], width=50)
            return True

        if result_type == ActionType.UPDATE_CONFIG:
            payload = result_payload or {}
            self._app.apply_preferences(**payload, apply_to_open_windows=False)
            self._app.persist_config()
            return True

        LOGGER.debug('Unhandled ActionResult type: %s', result_type)
        return False

    def _dialog_source_is_live(self, dialog):
        """Return whether the dialog's captured source is still registered."""
        source = getattr(dialog, "source_window", None)
        if source is None:
            return True
        try:
            windows = getattr(self._app, "windows")
        except (AttributeError, TypeError):
            # Minimal test scaffolding may not expose a window registry.
            return True
        if windows is None:
            return True
        expected_id = getattr(dialog, "source_window_id", None)
        try:
            for window in windows:
                if window is source:
                    return expected_id is None or getattr(window, "id", None) == expected_id
        except TypeError:
            return True
        return False

    @staticmethod
    def _dialog_callback(dialog, accepted):
        callback = getattr(dialog, "on_accept" if accepted else "on_cancel", None)
        if callback is None and accepted:
            # Compatibility for existing third-party dialogs.
            callback = getattr(dialog, "callback", None)
        return callback

    def resolve_dialog_result(self, result_idx):
        """Resolve a dialog through explicit workflow metadata."""
        if result_idx < 0 or not self._app.dialog:
            return

        dialog = self._app.dialog
        accepted = result_idx == 0
        source = getattr(dialog, "source_window", None)
        source_live = self._dialog_source_is_live(dialog)
        callback_result = None
        callback = self._dialog_callback(dialog, accepted)

        if callable(callback):
            if source is not None and not source_live:
                LOGGER.warning(
                    "Ignoring dialog workflow %r for closed source window %r",
                    getattr(dialog, "workflow_id", None),
                    source,
                )
            elif accepted and hasattr(dialog, "value"):
                callback_result = callback(dialog.value)
            else:
                callback_result = callback()

        if self._app.dialog is dialog:
            self._app.dialog = None

        if callback_result is not None:
            dispatch_source = source if source_live else None
            app_dispatch = getattr(self._app, "_dispatch_window_result", None)
            if callable(app_dispatch):
                app_dispatch(callback_result, dispatch_source)
            else:
                self.dispatch_window_result(callback_result, dispatch_source)

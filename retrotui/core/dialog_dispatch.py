"""
Dialog dispatch logic extracted from the main RetroTUI application class.

``DialogDispatcher`` handles ActionResult objects returned by windows and
processes dialog button results, keeping the core App class leaner.
"""
import logging

from ..ui.dialog import Dialog, InputDialog
from .actions import ActionResult, ActionType, AppAction

LOGGER = logging.getLogger(__name__)


class DialogDispatcher:
    """Handles ActionResult dispatching and dialog result resolution for RetroTUI.

    Takes the app instance as a constructor parameter and delegates to its
    methods/attributes when accessing application state.
    """

    # Dispatch table: ActionType -> method name on the app (methods that require source_win)
    _RESULT_DISPATCH = {
        ActionType.REQUEST_SAVE_AS: 'show_save_as_dialog',
        ActionType.REQUEST_OPEN_PATH: 'show_open_dialog',
        ActionType.REQUEST_RENAME_ENTRY: 'show_rename_dialog',
        ActionType.REQUEST_DELETE_CONFIRM: 'show_delete_confirm_dialog',
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
            return

        if not isinstance(result, ActionResult):
            LOGGER.debug('Ignoring non-ActionResult return from window callback: %r', result)
            return

        if result.type == ActionType.REFRESH:
            return

        LOGGER.debug('Dispatching window result: type=%s payload=%r', result.type, result.payload)

        # Simple dialog dispatches (require source_win)
        method_name = self._RESULT_DISPATCH.get(result.type)
        if method_name is not None:
            if source_win:
                getattr(self._app, method_name)(source_win)
            return

        if result.type == ActionType.OPEN_FILE and result.payload:
            self._app.open_file_viewer(result.payload)
            return

        if result.type == ActionType.REQUEST_URL:
            self._app.show_url_dialog(source_win, result.payload)
            return

        if result.type == ActionType.EXECUTE:
            exec_action = self._app._normalize_action(result.payload)
            if exec_action == AppAction.CLOSE_WINDOW and source_win:
                self._app.close_window(source_win)
            elif exec_action:
                self._app.execute_action(exec_action)
            return

        if result.type in (
            ActionType.REQUEST_COPY_BETWEEN_PANES,
            ActionType.REQUEST_MOVE_BETWEEN_PANES,
        ):
            operation = (
                'copy'
                if result.type == ActionType.REQUEST_COPY_BETWEEN_PANES
                else 'move'
            )
            destination = self._app._resolve_between_panes_destination(source_win, result.payload)
            if not source_win:
                self._app.dialog = Dialog(
                    'Operation Error',
                    f'Cannot {operation}: no source window context.',
                    ['OK'],
                    width=54,
                )
                return
            if not destination:
                self._app.dialog = Dialog(
                    'Operation Error',
                    f'Cannot {operation}: destination pane path is unavailable.',
                    ['OK'],
                    width=62,
                )
                return
            op_result = self._app._run_file_operation_with_progress(
                source_win,
                operation=operation,
                destination=destination,
            )
            if op_result is not None:
                self.dispatch_window_result(op_result, source_win)
            return

        if result.type == ActionType.REQUEST_KILL_CONFIRM and source_win:
            self._app.show_kill_confirm_dialog(source_win, result.payload)
            return

        if result.type == ActionType.SAVE_ERROR:
            message = result.payload or 'Unknown save error.'
            self._app.dialog = Dialog('Save Error', str(message), ['OK'], width=50)
            return

        if result.type == ActionType.ERROR:
            message = result.payload or 'Unknown error.'
            self._app.dialog = Dialog('Error', str(message), ['OK'], width=50)
            return

        if result.type == ActionType.UPDATE_CONFIG:
            payload = result.payload or {}
            self._app.apply_preferences(**payload, apply_to_open_windows=False)
            self._app.persist_config()
            return

        LOGGER.debug('Unhandled ActionResult type: %s', result.type)

    def resolve_dialog_result(self, result_idx):
        """Apply dialog button result and run dialog callback when needed."""
        if result_idx < 0 or not self._app.dialog:
            return

        dialog = self._app.dialog
        btn_text = dialog.buttons[result_idx] if result_idx < len(dialog.buttons) else ''
        callback_result = None

        if dialog.title == 'Exit RetroTUI' and btn_text == 'Yes':
            self._app.running = False
        elif result_idx == 0:
            callback = getattr(dialog, 'callback', None)
            if callable(callback):
                if isinstance(dialog, InputDialog):
                    callback_result = callback(dialog.value)
                else:
                    callback_result = callback()

        if self._app.dialog is dialog:
            self._app.dialog = None
        if callback_result is not None:
            self.dispatch_window_result(callback_result, self._app.get_active_window())

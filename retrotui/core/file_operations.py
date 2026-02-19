"""File operation manager for RetroTUI."""
import os
import logging
import threading
import time

from ..ui.dialog import Dialog, InputDialog, ProgressDialog
from .actions import ActionResult, ActionType

LOGGER = logging.getLogger(__name__)


class FileOperationManager:
    """Manages file operation dialogs and background file operations."""

    LONG_FILE_OPERATION_BYTES = 8 * 1024 * 1024
    BACKGROUND_OPERATION_JOIN_TIMEOUT = 5.0

    def __init__(self, app):
        """Initialize with reference to the main app for dialog and dispatch access.

        Background operation state is stored on the app object (app._background_operation)
        so that external code and tests that access it directly continue to work.
        """
        self._app = app
        # Initialise the state slot on the app if it is not already present.
        if not hasattr(self._app, '_background_operation'):
            self._app._background_operation = None

    # ------------------------------------------------------------------
    # Dialog helpers
    # ------------------------------------------------------------------

    def show_save_as_dialog(self, win):
        """Show dialog to get filename for saving."""
        dialog = InputDialog('Save As', 'Enter filename:', width=40)
        dialog.callback = lambda filename, target=win: target.save_as(filename)
        self._app.dialog = dialog

    def show_open_dialog(self, win):
        """Show dialog to get filename/path for opening in current window."""
        dialog = InputDialog('Open File', 'Enter filename/path:', width=52)
        dialog.callback = lambda filepath, target=win: target.open_path(filepath)
        self._app.dialog = dialog

    def show_rename_dialog(self, win):
        """Show dialog to rename selected File Manager entry."""
        entry = getattr(win, '_selected_entry', lambda: None)()
        if entry is None:
            self._app.dialog = Dialog('Rename Error', 'No item selected.', ['OK'], width=44)
            return
        if entry.name == '..':
            self._app.dialog = Dialog('Rename Error', 'Cannot rename parent entry.', ['OK'], width=44)
            return

        prompt = f"Rename:\n{entry.name}"
        dialog = InputDialog('Rename', prompt, initial_value=entry.name, width=56)
        dialog.callback = lambda new_name, target=win: target.rename_selected(new_name)
        self._app.dialog = dialog

    def show_delete_confirm_dialog(self, win):
        """Show confirmation dialog before deleting selected File Manager entry."""
        entry = self._window_selected_entry(win)
        if entry is None:
            self._app.dialog = Dialog('Delete Error', 'No item selected.', ['OK'], width=44)
            return
        if entry.name == '..':
            self._app.dialog = Dialog('Delete Error', 'Cannot delete parent entry.', ['OK'], width=44)
            return

        kind = 'directory' if entry.is_dir else 'file'
        message = (
            f"Delete {kind}:\n{entry.name}\n\n"
            "Item will be moved to Trash.\n"
            "Use Undo Delete (U) to restore."
        )
        dialog = Dialog('Confirm Delete', message, ['Delete', 'Cancel'], width=58)
        dialog.callback = lambda target=win: self._app._run_file_operation_with_progress(
            target,
            operation='delete',
        )
        self._app.dialog = dialog

    def show_copy_dialog(self, win):
        """Show destination input for copy operation in File Manager."""
        entry = self._window_selected_entry(win)
        if entry is None or entry.name == '..':
            self._app.dialog = Dialog('Copy Error', 'Select a valid item to copy.', ['OK'], width=48)
            return

        prompt = f"Copy:\n{entry.name}\n\nDestination path:"
        dialog = InputDialog('Copy To', prompt, initial_value=win.current_path, width=62)
        dialog.callback = lambda dest, target=win: self._app._run_file_operation_with_progress(
            target,
            operation='copy',
            destination=dest,
        )
        self._app.dialog = dialog

    def show_move_dialog(self, win):
        """Show destination input for move operation in File Manager."""
        entry = self._window_selected_entry(win)
        if entry is None or entry.name == '..':
            self._app.dialog = Dialog('Move Error', 'Select a valid item to move.', ['OK'], width=48)
            return

        prompt = f"Move:\n{entry.name}\n\nDestination path:"
        dialog = InputDialog('Move To', prompt, initial_value=win.current_path, width=62)
        dialog.callback = lambda dest, target=win: self._app._run_file_operation_with_progress(
            target,
            operation='move',
            destination=dest,
        )
        self._app.dialog = dialog

    def show_new_dir_dialog(self, win):
        """Show input dialog to create a new directory in current path."""
        dialog = InputDialog('New Folder', 'Enter folder name:', width=52)
        dialog.callback = lambda name, target=win: target.create_directory(name)
        self._app.dialog = dialog

    def show_new_file_dialog(self, win):
        """Show input dialog to create a new file in current path."""
        dialog = InputDialog('New File', 'Enter file name:', width=52)
        dialog.callback = lambda name, target=win: target.create_file(name)
        self._app.dialog = dialog

    def show_kill_confirm_dialog(self, win, payload):
        """Show confirmation dialog before sending signal to a process."""
        data = payload or {}
        pid = data.get('pid')
        command = data.get('command', '')
        if not pid:
            self._app.dialog = Dialog('Kill Error', 'No process selected.', ['OK'], width=44)
            return

        title = 'Confirm Kill'
        message = (
            f"Kill process PID {pid}?\n"
            f"{command[:40]}\n\n"
            "Signal: SIGTERM (15)"
        )
        dialog = Dialog(title, message, ['Kill', 'Cancel'], width=58)
        dialog.callback = (
            lambda target=win, data=data: target.kill_process(data)
            if callable(getattr(target, 'kill_process', None))
            else ActionResult(ActionType.ERROR, 'Window does not support process kill.')
        )
        self._app.dialog = dialog

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _window_selected_entry(win):
        """Resolve selected entry accessor from supported window APIs."""
        selector = getattr(win, 'selected_entry_for_operation', None)
        if callable(selector):
            return selector()
        selector = getattr(win, '_selected_entry', None)
        if callable(selector):
            return selector()
        return None

    @staticmethod
    def _resolve_between_panes_destination(win, payload):
        """Resolve destination path for copy/move between panes requests."""
        if isinstance(payload, dict):
            destination = str(payload.get('destination') or '').strip()
            if destination:
                return destination

        if not win or not getattr(win, 'dual_pane_enabled', False):
            return None
        active_pane = int(getattr(win, 'active_pane', 0) or 0)
        if active_pane == 0:
            return getattr(win, 'secondary_path', None)
        return getattr(win, 'current_path', None)

    # ------------------------------------------------------------------
    # Background operation management
    # ------------------------------------------------------------------

    def _is_long_file_operation(self, entry):
        """Return True when operation should show a modal progress dialog."""
        if entry is None or getattr(entry, 'name', None) == '..':
            return False
        if getattr(entry, 'is_dir', False):
            return True

        size = getattr(entry, 'size', None)
        if size is None:
            full_path = getattr(entry, 'full_path', None)
            if not full_path:
                return False
            try:
                size = os.path.getsize(full_path)
            except OSError:
                return False
        return int(size) >= self.LONG_FILE_OPERATION_BYTES

    def _start_background_operation(self, *, title, message, worker, source_win):
        """Run blocking filesystem operation in a worker thread and show progress."""
        state = getattr(self._app, '_background_operation', None)
        if state:
            return ActionResult(ActionType.ERROR, 'Another operation is already running.')

        progress_dialog = ProgressDialog(title, message, width=62)
        op_state = {
            'dialog': progress_dialog,
            'source_win': source_win,
            'worker_result': None,
            'done': False,
            'started_at': time.monotonic(),
            'thread': None,
        }

        def _runner():
            try:
                op_state['worker_result'] = worker()
            except Exception as exc:  # pragma: no cover - defensive worker path
                op_state['worker_result'] = ActionResult(ActionType.ERROR, str(exc))
            finally:
                op_state['done'] = True

        thread = threading.Thread(target=_runner, name='retrotui-file-op')
        op_state['thread'] = thread
        self._app._background_operation = op_state
        self._app.dialog = progress_dialog
        thread.start()
        return None

    def has_background_operation(self):
        """Return whether a background file operation is currently running."""
        return bool(getattr(self._app, '_background_operation', None))

    def poll_background_operation(self):
        """Advance progress state and dispatch completion when worker finishes."""
        state = getattr(self._app, '_background_operation', None)
        if not state:
            return

        elapsed = max(0.0, time.monotonic() - state['started_at'])
        dialog = state.get('dialog')
        if dialog and hasattr(dialog, 'set_elapsed'):
            dialog.set_elapsed(elapsed)

        if not state.get('done'):
            return

        if self._app.dialog is dialog:
            self._app.dialog = None

        self._app._background_operation = None
        result = state.get('worker_result')
        if result is not None:
            self._app._dispatch_window_result(result, state.get('source_win'))

    def _run_file_operation_with_progress(self, win, *, operation, destination=None):
        """Run file operation directly or via background worker with progress dialog."""
        entry = self._window_selected_entry(win)
        operation = str(operation).lower()

        if operation == 'copy':
            worker = lambda target=win, dest=destination: target.copy_selected(dest)
            title = 'Copying'
            details = f"Copying:\n{getattr(entry, 'name', 'item')}"
        elif operation == 'move':
            worker = lambda target=win, dest=destination: target.move_selected(dest)
            title = 'Moving'
            details = f"Moving:\n{getattr(entry, 'name', 'item')}"
        elif operation == 'delete':
            worker = lambda target=win: target.delete_selected()
            title = 'Deleting'
            details = f"Deleting:\n{getattr(entry, 'name', 'item')}"
        else:
            return ActionResult(ActionType.ERROR, f'Unsupported file operation: {operation}')

        if not self._is_long_file_operation(entry):
            return worker()

        message = f'{details}\n\nPlease wait...'
        # Delegate back through the app so that any mocks on app._start_background_operation
        # are honoured and the public interface of RetroTUI is preserved.
        return self._app._start_background_operation(
            title=title,
            message=message,
            worker=worker,
            source_win=win,
        )

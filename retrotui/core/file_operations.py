"""File operation manager for RetroTUI."""
import inspect
import os
import logging
import threading
import time
from types import SimpleNamespace

from ..ui.dialog import Dialog, InputDialog, ProgressDialog
from .actions import ActionResult, ActionType
from .file_transfer import TransferCancelled
from .dialog_workflow import DialogWorkflowId, bind_dialog
from .worker_scope import WorkerScope

LOGGER = logging.getLogger(__name__)
_BACKGROUND_WORKER_ERRORS = (
    ArithmeticError,
    AssertionError,
    AttributeError,
    LookupError,
    NameError,
    OSError,
    RuntimeError,
    SyntaxError,
    TypeError,
    ValueError,
)


class _CombinedCancelEvent:
    """Cancellation probe that becomes set when any owned event is set."""

    def __init__(self, *events):
        self._events = tuple(event for event in events if event is not None)

    def is_set(self):
        return any(event.is_set() for event in self._events)


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
        self._shutting_down = False
        self._worker_scope = WorkerScope(
            "file-operations",
            join_timeout=self.BACKGROUND_OPERATION_JOIN_TIMEOUT,
        )
        # Initialise the state slot on the app if it is not already present.
        if not hasattr(self._app, '_background_operation'):
            self._app._background_operation = None

    def _notify_error(self, message):
        """Show an error as a toast notification (or fallback to dialog).

        Uses toast when the notification system is available (the common
        runtime path).  Falls back to a modal dialog only when running
        under minimal test scaffolding that doesn't wire up the bus.
        """
        bus = getattr(self._app, '_event_bus', None)
        if bus is not None:
            # Bus exists → notification manager is available via lazy property.
            self._app.notifications.notify(message, title="Error", level="error")
            self._app._dirty = True
        else:
            self._app.dialog = Dialog('Error', message, ['OK'], width=44)

    # ------------------------------------------------------------------
    # Dialog helpers
    # ------------------------------------------------------------------

    def _show_input_dialog(self, win, title, prompt, width, callback_method, **dialog_kwargs):
        """Show an input dialog that calls a window method with the entered value."""
        self._app.dialog = bind_dialog(
            InputDialog(title, prompt, width=width, **dialog_kwargs),
            workflow_id=DialogWorkflowId.CALLBACK,
            source_window=win,
            on_accept=lambda value, target=win: getattr(target, callback_method)(value),
        )

    def show_save_as_dialog(self, win):
        """Show dialog to get filename for saving."""
        self._show_input_dialog(win, 'Save As', 'Enter filename:', 40, 'save_as')

    def show_open_dialog(self, win):
        """Show dialog to get filename/path for opening in current window."""
        self._show_input_dialog(win, 'Open File', 'Enter filename/path:', 52, 'open_path')

    def show_rename_dialog(self, win):
        """Show dialog to rename selected File Manager entry."""
        entry = getattr(win, '_selected_entry', lambda: None)()
        if entry is None:
            self._notify_error('No item selected.')
            return
        if entry.name == '..':
            self._notify_error('Cannot rename parent entry.')
            return

        prompt = f"Rename:\n{entry.name}"
        self._app.dialog = bind_dialog(
            InputDialog('Rename', prompt, initial_value=entry.name, width=56),
            workflow_id=DialogWorkflowId.CALLBACK,
            source_window=win,
            on_accept=lambda new_name, target=win: target.rename_selected(new_name),
        )

    def show_delete_confirm_dialog(self, win):
        """Show confirmation dialog before deleting selected File Manager entry."""
        entry = self._window_selected_entry(win)
        if entry is None:
            self._notify_error('No item selected.')
            return
        if entry.name == '..':
            self._notify_error('Cannot delete parent entry.')
            return

        kind = 'directory' if entry.is_dir else 'file'
        message = (
            f"Delete {kind}:\n{entry.name}\n\n"
            "Item will be moved to Trash.\n"
            "Use Undo Delete (U) to restore."
        )
        self._app.dialog = bind_dialog(
            Dialog('Confirm Delete', message, ['Delete', 'Cancel'], width=58),
            workflow_id=DialogWorkflowId.CALLBACK,
            source_window=win,
            on_accept=lambda target=win: self._app._run_file_operation_with_progress(
                target,
                operation='delete',
            ),
        )

    def show_empty_trash_confirm_dialog(self, win):
        """Show confirmation dialog before permanently emptying the trash."""
        try:
            trash_root = win._trash_root() if hasattr(win, '_trash_root') else None
        except Exception:
            trash_root = None
        if trash_root is None:
            self._notify_error('Trash is unavailable.')
            return
        try:
            names = os.listdir(trash_root)
        except OSError as exc:
            self._notify_error(str(exc))
            return
        if not names:
            self._notify_error('Trash is already empty.')
            return
        sample = ", ".join(names[:5])
        if len(names) > 5:
            sample += f" (and {len(names) - 5} more)"
        message = (
            f"Permanently delete all {len(names)} item(s) from Trash?\n\n"
            f"{sample}\n\n"
            "This cannot be undone."
        )
        empty = getattr(win, 'empty_trash', None)
        self._app.dialog = bind_dialog(
            Dialog('Empty Trash', message, ['Empty', 'Cancel'], width=64),
            workflow_id=DialogWorkflowId.CALLBACK,
            source_window=win,
            on_accept=(lambda target=win: target.empty_trash()) if callable(empty) else None,
        )

    def show_copy_dialog(self, win):
        """Show destination input for copy operation in File Manager."""
        entry = self._window_selected_entry(win)
        if entry is None or entry.name == '..':
            self._notify_error('Select a valid item to copy.')
            return

        prompt = f"Copy:\n{entry.name}\n\nDestination path:"
        self._app.dialog = bind_dialog(
            InputDialog('Copy To', prompt, initial_value=win.current_path, width=62),
            workflow_id=DialogWorkflowId.CALLBACK,
            source_window=win,
            on_accept=lambda dest, target=win: self._app._run_file_operation_with_progress(
                target,
                operation='copy',
                destination=dest,
            ),
        )

    def show_move_dialog(self, win):
        """Show destination input for move operation in File Manager."""
        entry = self._window_selected_entry(win)
        if entry is None or entry.name == '..':
            self._notify_error('Select a valid item to move.')
            return

        prompt = f"Move:\n{entry.name}\n\nDestination path:"
        self._app.dialog = bind_dialog(
            InputDialog('Move To', prompt, initial_value=win.current_path, width=62),
            workflow_id=DialogWorkflowId.CALLBACK,
            source_window=win,
            on_accept=lambda dest, target=win: self._app._run_file_operation_with_progress(
                target,
                operation='move',
                destination=dest,
            ),
        )

    def show_new_dir_dialog(self, win):
        """Show input dialog to create a new directory in current path."""
        self._show_input_dialog(win, 'New Folder', 'Enter folder name:', 52, 'create_directory')

    def show_new_file_dialog(self, win):
        """Show input dialog to create a new file in current path."""
        self._show_input_dialog(win, 'New File', 'Enter file name:', 52, 'create_file')

    def show_kill_confirm_dialog(self, win, payload):
        """Show confirmation dialog before sending signal to a process."""
        data = payload or {}
        pid = data.get('pid')
        command = data.get('command', '')
        if not pid:
            self._notify_error('No process selected.')
            return

        title = 'Confirm Kill'
        message = (
            f"Kill process PID {pid}?\n"
            f"{command[:40]}\n\n"
            "Signal: SIGTERM (15)"
        )
        self._app.dialog = bind_dialog(
            Dialog(title, message, ['Kill', 'Cancel'], width=58),
            workflow_id=DialogWorkflowId.CALLBACK,
            source_window=win,
            on_accept=(
                lambda target=win, data=data: target.kill_process(data)
                if callable(getattr(target, 'kill_process', None))
                else ActionResult(ActionType.ERROR, 'Window does not support process kill.')
            ),
        )

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
            destination = str(payload.get('destination') or payload.get('dest') or '').strip()
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

    @staticmethod
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

        cancellable = getattr(worker, '_retrotui_cancellable', False) is True
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
                if cancellable:
                    result = self._invoke_worker(worker, cancel_event, _publish_progress)
                else:
                    result = worker()
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

    def has_background_operation(self):
        """Return whether a background file operation is currently running."""
        return bool(
            not self._shutting_down
            and getattr(self._app, '_background_operation', None)
        )

    def shutdown(self, timeout=None):
        """Stop accepting work and detach completion from the UI.

        Filesystem primitives are not always interruptible. The bounded join
        result tells the application whether physical completion was verified,
        while clearing app state guarantees a late worker cannot dispatch into
        a torn-down UI.
        """
        self._shutting_down = True
        stopped = self._worker_scope.shutdown(
            timeout=timeout,
            require_stopped=True,
        )
        state = getattr(self._app, '_background_operation', None)
        if state:
            dialog = state.get('dialog')
            if getattr(self._app, 'dialog', None) is dialog:
                self._app.dialog = None
            self._app._background_operation = None
        return stopped

    def poll_background_operation(self):
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

    def _run_file_operation_with_progress(self, win, *, operation, destination=None, source_path=None):
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
                if cancel_event is None and progress_callback is None:
                    return transfer(source_path, destination)
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
                if cancel_event is None and progress_callback is None:
                    return win.copy_selected(destination)
                return win.copy_selected(
                    destination,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )

            title = 'Copying'
            details = f"Copying:\n{getattr(entry, 'name', 'item')}"
        elif operation == 'move':
            def worker(cancel_event=None, progress_callback=None):
                if cancel_event is None and progress_callback is None:
                    return win.move_selected(destination)
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


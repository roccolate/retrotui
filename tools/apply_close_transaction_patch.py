#!/usr/bin/env python3
"""Apply the focused transactional-close stabilization patch."""
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, found {count}: {old!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "retrotui/ui/window.py",
    '''    def on_ipc_message(self, message):
        """Handle an IPC message from another window.  Override in subclasses."""

    def close_button_pos(self):
''',
    '''    def on_ipc_message(self, message):
        """Handle an IPC message from another window.  Override in subclasses."""

    def request_close(self):
        """Return True when the window may be closed immediately."""
        return True

    def close_button_pos(self):
''',
)

replace_once(
    "retrotui/core/window_manager.py",
    '''    def close_window(self, win):
        """Close a window. Idempotent: safe to call more than once."""
        # Clear menu owner if it points at the window being closed, even on
        # re-entry. This must run before the membership check below so a
        # stale reference is recovered.
        if getattr(self._app, "_active_window_menu_owner", None) is win:
            menu = getattr(win, "window_menu", None)
            if menu is not None:
                menu.active = False
            self._app._active_window_menu_owner = None
        if win not in self.windows:
            return
        closer = getattr(win, 'close', None)
        if callable(closer):
            try:
                closer()
            except _WINDOW_CLOSE_HOOK_ERRORS:  # pragma: no cover - defensive window cleanup path
                LOGGER.debug('Window close hook failed for %r', win, exc_info=True)
        if win in self.windows:
            self.windows.remove(win)
        if self._active_window is win:
            self._active_window = None
        self._layers_dirty = True
        self._emit_event("window.closed", win)
        self._activate_last_visible_window()
''',
    '''    def close_window(self, win, *, force=False):
        """Request and, when authorized, close *win*.

        Returns True only when the window was removed. ``force=True`` is
        reserved for shutdown and bypasses the interactive close request.
        """
        if win not in self.windows:
            return False

        if not force:
            requester = getattr(win, "request_close", None)
            if callable(requester):
                try:
                    request_result = requester()
                except _WINDOW_CLOSE_HOOK_ERRORS:
                    LOGGER.debug('Window close request failed for %r', win, exc_info=True)
                    return False
                if request_result is False:
                    return False
                if request_result is not None and request_result is not True:
                    dispatcher = getattr(self._app, "_dispatch_window_result", None)
                    if callable(dispatcher):
                        dispatcher(request_result, win)
                    return False

        if getattr(self._app, "_active_window_menu_owner", None) is win:
            menu = getattr(win, "window_menu", None)
            if menu is not None:
                menu.active = False
            self._app._active_window_menu_owner = None

        closer = getattr(win, 'close', None)
        if callable(closer):
            try:
                closer()
            except _WINDOW_CLOSE_HOOK_ERRORS:  # pragma: no cover - defensive window cleanup path
                LOGGER.debug('Window close hook failed for %r', win, exc_info=True)
        if win in self.windows:
            self.windows.remove(win)
        if self._active_window is win:
            self._active_window = None
        self._layers_dirty = True
        self._emit_event("window.closed", win)
        self._activate_last_visible_window()
        return True
''',
)

replace_once(
    "retrotui/core/app.py",
    '''        for win in list(self.windows):
            self._close_window_safely(win)
''',
    '''        for win in list(self.windows):
            self.window_mgr.close_window(win, force=True)
''',
)

replace_once(
    "retrotui/core/app.py",
    '''    def close_window(self, win):
        """Close a window."""
        self.window_mgr.close_window(win)
''',
    '''    def close_window(self, win, *, force=False):
        """Request that a window close, or force it during shutdown."""
        return self.window_mgr.close_window(win, force=force)
''',
)

replace_once(
    "retrotui/core/app.py",
    '''    def _show_save_confirm_dialog(self, win, payload=None):
        """Prompt the user before discarding unsaved work in *win*."""
        # The ``on_discard`` callback is attached via the ActionResult payload
        # at the call site (notepad.py emits it when open_path hits a dirty
        # buffer). Prefer the payload; fall back to a window method for tests
        # or direct callers.
        from ..ui.dialog import Dialog
        try:
            title = getattr(win, "title", "Notepad")
        except Exception:
            title = "Notepad"
        message = (
            f"{title} has unsaved changes.\n"
            "Discard them and open the new file?"
        )
        on_discard = None
        if isinstance(payload, dict):
            candidate = payload.get("on_discard")
            if callable(candidate):
                on_discard = candidate
        if on_discard is None:
            fallback = getattr(win, "_do_open_path_force", None)
            if callable(fallback):
                on_discard = fallback

        def _on_discard():
            if on_discard is not None:
                on_discard()

        self.dialog = Dialog(
            title="Discard unsaved changes?",
            message=message,
            buttons=["Discard", "Cancel"],
            width=58,
        )
        self._pending_discard_callback = _on_discard
''',
    '''    def _show_save_confirm_dialog(self, win, payload=None):
        """Prompt before a destructive operation on unsaved work."""
        from ..ui.dialog import Dialog

        try:
            title = getattr(win, "title", "Notepad")
        except Exception:
            title = "Notepad"
        message = (
            f"{title} has unsaved changes.\n"
            "Discard them and continue?"
        )
        on_discard = None
        on_cancel = None
        if isinstance(payload, dict):
            candidate = payload.get("on_discard")
            if callable(candidate):
                on_discard = candidate
            candidate = payload.get("on_cancel")
            if callable(candidate):
                on_cancel = candidate
            custom_message = payload.get("message")
            if isinstance(custom_message, str) and custom_message.strip():
                message = custom_message
        if on_discard is None:
            fallback = getattr(win, "_do_open_path_force", None)
            if callable(fallback):
                on_discard = fallback

        self.dialog = Dialog(
            title="Discard unsaved changes?",
            message=message,
            buttons=["Discard", "Cancel"],
            width=58,
        )
        self.dialog.kind = "save_confirm"
        self.dialog.source_window = win
        self._pending_discard_callback = on_discard
        self._pending_discard_cancel_callback = on_cancel
        self._pending_discard_source = win
''',
)

replace_once(
    "retrotui/core/dialog_dispatch.py",
    '''        dialog = self._app.dialog
        btn_text = dialog.buttons[result_idx] if result_idx < len(dialog.buttons) else ''
        callback_result = None

        if dialog.title == 'Exit RetroTUI' and btn_text == 'Yes':
            self._app.running = False
        elif dialog.title == 'Discard unsaved changes?':
            # Save-confirm prompt: ``Discard`` (idx 0) runs the pending
            # discard callback; ``Cancel`` (idx 1) is a no-op.
            callback = getattr(self._app, '_pending_discard_callback', None)
            self._app._pending_discard_callback = None
            if result_idx == 0 and callable(callback):
                callback()
        elif result_idx == 0:
            callback = getattr(dialog, 'callback', None)
            if callable(callback):
                if hasattr(dialog, 'value'):
                    callback_result = callback(dialog.value)
                else:
                    callback_result = callback()

        if self._app.dialog is dialog:
            self._app.dialog = None
        if callback_result is not None:
            app_dispatch = getattr(self._app, '_dispatch_window_result', None)
            if callable(app_dispatch):
                app_dispatch(callback_result, self._app.get_active_window())
            else:
                self.dispatch_window_result(callback_result, self._app.get_active_window())
''',
    '''        dialog = self._app.dialog
        btn_text = dialog.buttons[result_idx] if result_idx < len(dialog.buttons) else ''
        callback_result = None
        callback_source = getattr(dialog, 'source_window', None)

        if dialog.title == 'Exit RetroTUI' and btn_text == 'Yes':
            self._app.running = False
        elif getattr(dialog, 'kind', None) == 'save_confirm' or dialog.title == 'Discard unsaved changes?':
            callback_source = getattr(
                self._app, '_pending_discard_source', callback_source
            )
            if result_idx == 0:
                callback = getattr(self._app, '_pending_discard_callback', None)
            else:
                callback = getattr(self._app, '_pending_discard_cancel_callback', None)
            self._app._pending_discard_callback = None
            self._app._pending_discard_cancel_callback = None
            self._app._pending_discard_source = None
            if callable(callback):
                callback_result = callback()
        elif result_idx == 0:
            callback = getattr(dialog, 'callback', None)
            if callable(callback):
                if hasattr(dialog, 'value'):
                    callback_result = callback(dialog.value)
                else:
                    callback_result = callback()

        if self._app.dialog is dialog:
            self._app.dialog = None
        if callback_result is not None:
            source_win = callback_source or self._app.get_active_window()
            app_dispatch = getattr(self._app, '_dispatch_window_result', None)
            if callable(app_dispatch):
                app_dispatch(callback_result, source_win)
            else:
                self.dispatch_window_result(callback_result, source_win)
''',
)

replace_once(
    "retrotui/apps/notepad.py",
    '''        self._search_query = ''
        self._force_close = False
''',
    '''        self._search_query = ''
        self._force_close = False
        self._close_confirm_pending = False
        self._open_path_confirm_pending = None
''',
)

replace_once(
    "retrotui/apps/notepad.py",
    '''        self._redo_stack.clear()
        self._force_close = False
        # Whole buffer was replaced; reset the per-line cache list.
''',
    '''        self._redo_stack.clear()
        self._force_close = False
        self._close_confirm_pending = False
        self._open_path_confirm_pending = None
        # Whole buffer was replaced; reset the per-line cache list.
''',
)

replace_once(
    "retrotui/apps/notepad.py",
    '''        self.modified = False
        self._update_title()
        return True
''',
    '''        self.modified = False
        self._force_close = False
        self._close_confirm_pending = False
        self._update_title()
        return True
''',
)

replace_once(
    "retrotui/apps/notepad.py",
    '''            return ActionResult(
                ActionType.REQUEST_SAVE_CONFIRM,
                payload={"on_discard": self._do_open_path_force},
            )
''',
    '''            return ActionResult(
                ActionType.REQUEST_SAVE_CONFIRM,
                payload={
                    "on_discard": self._do_open_path_force,
                    "on_cancel": self._cancel_open_path,
                    "message": (
                        f"{self.title} has unsaved changes.\n"
                        "Discard them and open the new file?"
                    ),
                },
            )
''',
)

replace_once(
    "retrotui/apps/notepad.py",
    '''    def _do_open_path_force(self):
        """Discard current buffer and open the pending path."""
        pending = self._open_path_confirm_pending
        self._open_path_confirm_pending = None
        if pending:
            self._do_open_path(pending)


    def _invalidate_wrap(self, line_idx=None):
''',
    '''    def _do_open_path_force(self):
        """Discard current buffer and open the pending path."""
        pending = self._open_path_confirm_pending
        self._open_path_confirm_pending = None
        if pending:
            self._do_open_path(pending)

    def _cancel_open_path(self):
        """Cancel a pending destructive open request."""
        self._open_path_confirm_pending = None

    def request_close(self):
        """Return a confirmation request when the buffer is modified."""
        if not self.modified or self._force_close:
            return True
        if self._close_confirm_pending:
            return False
        self._close_confirm_pending = True
        return ActionResult(
            ActionType.REQUEST_SAVE_CONFIRM,
            payload={
                "on_discard": self._confirm_close,
                "on_cancel": self._cancel_close_request,
                "message": (
                    f"{self.title} has unsaved changes.\n"
                    "Discard them and close the window?"
                ),
            },
        )

    def _confirm_close(self):
        self._close_confirm_pending = False
        self._force_close = True
        return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)

    def _cancel_close_request(self):
        self._close_confirm_pending = False


    def _invalidate_wrap(self, line_idx=None):
''',
)

replace_once(
    "retrotui/apps/notepad.py",
    '''    def _push_undo(self):
        self._force_close = False
''',
    '''    def _push_undo(self):
        self._force_close = False
        self._close_confirm_pending = False
''',
)

replace_once(
    "retrotui/apps/notepad.py",
    '''        elif action == AppAction.NP_CLOSE:
            if self.modified and not self._force_close:
                self._force_close = True
                return ActionResult(ActionType.ERROR, "Unsaved changes! Press Close again to discard.")
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
''',
    '''        elif action == AppAction.NP_CLOSE:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
''',
)

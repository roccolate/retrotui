"""Trash bin application window."""

import curses
import os

from ..core.actions import ActionResult, ActionType, AppAction
from ..core.trash_transaction import (
    is_internal_trash_name,
    list_trash_items,
    recover_trash_transactions,
    transactional_permanent_delete,
)
from ..ui.menu import WindowMenu
from ..utils import normalize_key_code
from .filemanager import FileManagerWindow
from .filemanager.operations import (
    _trash_base_dir,
    perform_restore,
)


class TrashWindow(FileManagerWindow):
    """File-manager variant constrained to the user trash directory."""

    KEY_F5 = getattr(curses, "KEY_F5", -1)
    is_trash_window = True

    def _trash_base_dir(self):
        return _trash_base_dir()

    def __init__(self, x, y, w, h):
        trash_path = self._trash_base_dir()
        os.makedirs(trash_path, exist_ok=True)
        self.trash_root = os.path.realpath(trash_path)
        self.recovery_errors = recover_trash_transactions(self.trash_root)
        super().__init__(
            x,
            y,
            max(56, w),
            max(16, h),
            start_path=trash_path,
            show_hidden_default=True,
        )
        self.dual_pane_enabled = False
        self.active_pane = 0
        self.window_menu = WindowMenu(
            {
                "File": [
                    ("Open       Enter", AppAction.FM_OPEN),
                    ("Restore       R", "trash_restore"),
                    ("Delete       Del", AppAction.FM_DELETE),
                    ("Empty Trash    E", "trash_empty"),
                    ("-------------", None),
                    ("Close          Q", "trash_close"),
                ],
                "View": [
                    ("Refresh      F5", AppAction.FM_REFRESH),
                ],
            }
        )
        if self.recovery_errors:
            self.error_message = "Trash recovery: " + "; ".join(self.recovery_errors)
        self._rebuild_content()

    def _rebuild_content(self):
        super()._rebuild_content()
        self._update_title()

    def _trash_root(self):
        """Return normalized root path used by this trash view."""
        return self.trash_root

    def _build_listing(self, path):
        """Hide parent and transaction bookkeeping at trash root."""
        entries, content, error_message = super()._build_listing(path)
        if os.path.realpath(path) != self._trash_root():
            return entries, content, error_message

        header = content[:2]
        rows = content[2:]
        visible_entries = []
        visible_rows = []
        for index, entry in enumerate(entries):
            if entry.name == ".." or is_internal_trash_name(entry.name):
                continue
            visible_entries.append(entry)
            if index < len(rows):
                visible_rows.append(rows[index])
        return visible_entries, header + visible_rows, error_message

    def _update_title(self):
        """Show trash-specific window title."""
        count = len([entry for entry in self.entries if entry.name != ".."])
        root = self._trash_root()
        here = os.path.realpath(self.current_path)
        location = "root" if here == root else os.path.basename(here) or "/"
        self.title = f"Trash - {location} ({count} items)"

    def navigate_to(self, path):
        """Restrict navigation to trash root subtree only."""
        root = self._trash_root()
        real_path = os.path.realpath(path)
        if real_path == root or real_path.startswith(root + os.sep):
            super().navigate_to(real_path)

    @staticmethod
    def _delete_path(
        path,
        *,
        trash_root=None,
        cancel_event=None,
        progress_callback=None,
    ):
        """Stage and cooperatively remove a trash path permanently."""
        root = trash_root or os.path.dirname(os.path.abspath(path))
        return transactional_permanent_delete(
            path,
            root,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )

    def delete_selected(self, *, cancel_event=None, progress_callback=None):
        """Delete selected trash entry permanently."""
        entry = self._selected_entry()
        if entry is None:
            return ActionResult(ActionType.ERROR, "No item selected.")
        if entry.name == "..":
            return ActionResult(ActionType.ERROR, "Cannot delete parent entry.")

        selected = self.selected_index
        try:
            self._delete_path(
                entry.full_path,
                trash_root=self._trash_root(),
                cancel_event=cancel_event,
                progress_callback=progress_callback,
            )
        except (OSError, ValueError) as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        self._rebuild_content()
        if self.entries:
            self.selected_index = min(selected, len(self.entries) - 1)
            self._ensure_visible()
        return None

    def undo_last_delete(self):
        """Undo is not applicable inside Trash window."""
        return ActionResult(ActionType.ERROR, "Undo Delete is not available in Trash.")

    def request_restore_selected(self):
        """Request app-managed restore so large items run in the worker scope."""
        entry = self._selected_entry()
        if entry is None:
            return ActionResult(ActionType.ERROR, "No item selected.")
        if entry.name == "..":
            return ActionResult(ActionType.ERROR, "Cannot restore parent entry.")
        return ActionResult(ActionType.REQUEST_RESTORE_TRASH)

    def restore_selected(self, *, cancel_event=None, progress_callback=None):
        """Restore selected trash entry to its original location."""
        entry = self._selected_entry()
        if entry is None:
            return ActionResult(ActionType.ERROR, "No item selected.")
        if entry.name == "..":
            return ActionResult(ActionType.ERROR, "Cannot restore parent entry.")
        result, _ = perform_restore(
            entry.full_path,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
        if result.type == ActionType.REFRESH:
            self._rebuild_content()
        return result

    def empty_trash(self, *, cancel_event=None, progress_callback=None):
        """Permanently remove all user-visible entries under trash root."""
        root = self._trash_root()
        try:
            paths = list_trash_items(root)
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        if not paths:
            return ActionResult(ActionType.ERROR, "Trash is already empty.")

        errors = []
        for path in paths:
            try:
                progress = self._delete_path(
                    path,
                    trash_root=root,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                )
                if getattr(progress, "phase", None) == "deferred":
                    break
            except (OSError, ValueError) as exc:
                errors.append(f"{os.path.basename(path)}: {exc}")

        self.current_path = root
        self._rebuild_content()
        if errors:
            return ActionResult(ActionType.ERROR, "Failed to delete: " + "; ".join(errors))
        return None

    def _confirm_empty_trash(self):
        """Request confirmation before emptying trash."""
        return ActionResult(ActionType.REQUEST_EMPTY_TRASH_CONFIRM)

    def execute_action(self, action):
        """Execute trash-specific menu actions."""
        if action == "trash_empty":
            return self._confirm_empty_trash()
        if action == "trash_restore":
            return self.request_restore_selected()
        if action == "trash_close":
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return super().execute_action(action)

    def handle_key(self, key):
        """Handle trash app shortcuts."""
        key_code = normalize_key_code(key)
        if key_code in (ord("e"), ord("E")):
            return self._confirm_empty_trash()
        if key_code in (ord("r"), ord("R")) and not (
            self.window_menu and self.window_menu.active
        ):
            return self.request_restore_selected()
        if key_code in (self.KEY_F5,):
            self._rebuild_content()
            return None
        return super().handle_key(key)

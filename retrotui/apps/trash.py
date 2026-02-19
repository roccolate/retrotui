"""Trash bin application window."""

import curses
import os
import shutil

from ..core.actions import ActionResult, ActionType, AppAction
from ..ui.menu import WindowMenu
from ..utils import normalize_key_code
from .filemanager import FileManagerWindow
from .filemanager.operations import _trash_base_dir


class TrashWindow(FileManagerWindow):
    """File-manager variant constrained to the user trash directory."""

    KEY_F5 = getattr(curses, "KEY_F5", -1)

    def _trash_base_dir(self):
        return _trash_base_dir()

    def __init__(self, x, y, w, h):
        trash_path = self._trash_base_dir()
        os.makedirs(trash_path, exist_ok=True)
        self.trash_root = os.path.realpath(trash_path)
        super().__init__(x, y, max(56, w), max(16, h), start_path=trash_path, show_hidden_default=True)
        self.dual_pane_enabled = False
        self.active_pane = 0
        self.window_menu = WindowMenu(
            {
                "File": [
                    ("Open       Enter", AppAction.FM_OPEN),
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
        self._rebuild_content()

    def _rebuild_content(self):
        super()._rebuild_content()
        self._update_title()

    def _trash_root(self):
        """Return normalized root path used by this trash view."""
        return self.trash_root

    def _build_listing(self, path):
        """Build listing and hide parent entry at trash root level."""
        entries, content, error_message = super()._build_listing(path)
        if os.path.realpath(path) == self._trash_root():
            if entries and entries[0].name == "..":
                entries = entries[1:]
                if len(content) > 2:
                    content = content[:2] + content[3:]
        return entries, content, error_message

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
    def _delete_path(path):
        """Delete a file/symlink or directory tree permanently."""
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
            return
        os.remove(path)

    def delete_selected(self):
        """Delete selected trash entry permanently."""
        entry = self._selected_entry()
        if entry is None:
            return ActionResult(ActionType.ERROR, "No item selected.")
        if entry.name == "..":
            return ActionResult(ActionType.ERROR, "Cannot delete parent entry.")

        selected = self.selected_index
        try:
            self._delete_path(entry.full_path)
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        self._rebuild_content()
        if self.entries:
            self.selected_index = min(selected, len(self.entries) - 1)
            self._ensure_visible()
        return None

    def undo_last_delete(self):
        """Undo is not applicable inside Trash window."""
        return ActionResult(ActionType.ERROR, "Undo Delete is not available in Trash.")

    def empty_trash(self):
        """Permanently remove all entries under trash root."""
        root = self._trash_root()
        try:
            names = os.listdir(root)
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))

        for name in names:
            path = os.path.join(root, name)
            try:
                self._delete_path(path)
            except OSError as exc:
                return ActionResult(ActionType.ERROR, str(exc))

        self.current_path = root
        self._rebuild_content()
        return None

    def execute_action(self, action):
        """Execute trash-specific menu actions."""
        if action == "trash_empty":
            return self.empty_trash()
        if action == "trash_close":
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return super().execute_action(action)

    def handle_key(self, key):
        """Handle trash app shortcuts."""
        key_code = normalize_key_code(key)
        if key_code in (ord("e"), ord("E")):
            return self.empty_trash()
        if key_code in (ord("r"), ord("R"), self.KEY_F5):
            self._rebuild_content()
            return None
        return super().handle_key(key)

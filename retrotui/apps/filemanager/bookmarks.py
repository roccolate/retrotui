"""
Bookmark management for File Manager.
"""
import os
from ...core.actions import ActionResult, ActionType

def get_default_bookmarks():
    """Build default bookmark slots 1..4."""
    candidates = {
        1: os.path.expanduser('~'),
        2: os.path.sep,
        3: os.path.join(os.path.sep, 'var', 'log'),
        4: os.path.join(os.path.sep, 'etc'),
    }
    bookmarks = {}
    for slot, raw_path in candidates.items():
        path = os.path.realpath(os.path.expanduser(raw_path))
        if os.path.isdir(path):
            bookmarks[slot] = path
    if 1 not in bookmarks:
        home = os.path.realpath(os.path.expanduser('~'))
        bookmarks[1] = home if os.path.isdir(home) else os.path.sep
    return bookmarks

def set_bookmark(bookmarks, slot, path):
    """Assign bookmark slot to provided path."""
    if slot not in (1, 2, 3, 4):
        return ActionResult(ActionType.ERROR, 'Invalid bookmark slot.')
    target = os.path.realpath(path)
    if not os.path.isdir(target):
        return ActionResult(ActionType.ERROR, 'Bookmark target is not a directory.')
    bookmarks[slot] = target
    return None

def navigate_bookmark(bookmarks, slot):
    """Return path for bookmark slot or ActionResult error."""
    target = bookmarks.get(slot)
    if not target:
        return ActionResult(ActionType.ERROR, f'Bookmark {slot} is not set.')
    if not os.path.isdir(target):
        return ActionResult(ActionType.ERROR, f"Bookmark {slot} path no longer exists.")
    return target

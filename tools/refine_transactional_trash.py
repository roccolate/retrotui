#!/usr/bin/env python3
"""Apply compatibility refinements to generated transactional trash code."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path, old, new):
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


core_path = ROOT / "retrotui/core/trash_transaction.py"
text = core_path.read_text(encoding="utf-8")
if "def transactional_empty_trash(" not in text:
    text += '''


def transactional_empty_trash(
    trash_root: str,
    *,
    cancel_event: Any | None = None,
    progress_callback: Callable[[TransferProgress], Any] | None = None,
) -> TransferProgress:
    """Stage and remove every visible trash item cooperatively.

    Cancellation before an item's staging leaves that item visible. Cancellation
    after staging commits its logical deletion and leaves a journaled tombstone
    for recovery to finish on the next Trash startup.
    """
    root = os.path.abspath(os.fspath(trash_root))
    paths = list_trash_items(root)
    completed = TransferProgress(
        phase="completed",
        files_done=0,
        total_files=len(paths),
        current_path=root,
    )
    if not paths:
        _publish(progress_callback, completed)
        return completed

    files_done = 0
    for path in paths:
        _check_cancel(cancel_event)
        result = transactional_permanent_delete(
            path,
            root,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
        )
        files_done += 1
        if result.phase == "deferred":
            deferred = TransferProgress(
                phase="deferred",
                bytes_done=result.bytes_done,
                total_bytes=result.total_bytes,
                files_done=files_done,
                total_files=len(paths),
                current_path=result.current_path,
            )
            _publish(progress_callback, deferred)
            return deferred

    completed = TransferProgress(
        phase="completed",
        files_done=files_done,
        total_files=len(paths),
        current_path=root,
    )
    _publish(progress_callback, completed)
    return completed
'''
core_path.write_text(text, encoding="utf-8")

window_path = ROOT / "retrotui/apps/filemanager/window.py"
window_text = window_path.read_text(encoding="utf-8")
pattern = re.compile(
    r"(?P<indent>\s*)result = perform_undo\(\n"
    r"(?P=indent)    self\._last_trash_move,\n"
    r"(?P=indent)    cancel_event=cancel_event,\n"
    r"(?P=indent)    progress_callback=progress_callback,\n"
    r"(?P=indent)\)"
)
match = pattern.search(window_text)
if not match:
    raise RuntimeError("window.py: generated perform_undo call not found")
indent = match.group("indent")
replacement = (
    f"{indent}if cancel_event is None and progress_callback is None:\n"
    f"{indent}    result = perform_undo(self._last_trash_move)\n"
    f"{indent}else:\n"
    f"{indent}    result = perform_undo(\n"
    f"{indent}        self._last_trash_move,\n"
    f"{indent}        cancel_event=cancel_event,\n"
    f"{indent}        progress_callback=progress_callback,\n"
    f"{indent}    )"
)
window_path.write_text(
    window_text[:match.start()] + replacement + window_text[match.end():],
    encoding="utf-8",
)

replace_once(
    "tests/test_filemanager_additional.py",
    "from retrotui.core.actions import ActionType\n",
    "from retrotui.core.actions import ActionType\n"
    "from retrotui.apps.filemanager import operations as file_operations\n",
)
replace_once(
    "tests/test_filemanager_additional.py",
    '''        # pick an entry and monkeypatch shutil.move to raise
        for i, e in enumerate(self.win.entries):
            if not e.is_dir and e.name != '..':
                self.win.selected_index = i
                break
        orig = shutil.move
        try:
            shutil.move = lambda a, b: (_ for _ in ()).throw(OSError('nope'))
            res = self.win.delete_selected()
            self.assertIsNotNone(res)
            self.assertEqual(res.type, ActionType.ERROR)
        finally:
            shutil.move = orig
''',
    '''        # Simulate failure at the transactional move boundary.
        for i, e in enumerate(self.win.entries):
            if not e.is_dir and e.name != '..':
                self.win.selected_index = i
                break
        original = file_operations.transactional_move_to_trash
        try:
            def fail_transaction(*_args, **_kwargs):
                raise OSError('nope')

            file_operations.transactional_move_to_trash = fail_transaction
            res = self.win.delete_selected()
            self.assertIsNotNone(res)
            self.assertEqual(res.type, ActionType.ERROR)
        finally:
            file_operations.transactional_move_to_trash = original
''',
)

print("transactional trash compatibility refinements applied")

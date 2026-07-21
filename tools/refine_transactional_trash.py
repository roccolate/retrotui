#!/usr/bin/env python3
"""Add the batch empty-trash primitive to the generated transaction core."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "retrotui/core/trash_transaction.py"
text = PATH.read_text(encoding="utf-8")

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
            return TransferProgress(
                phase="deferred",
                bytes_done=result.bytes_done,
                total_bytes=result.total_bytes,
                files_done=files_done,
                total_files=len(paths),
                current_path=result.current_path,
            )

    completed = TransferProgress(
        phase="completed",
        files_done=files_done,
        total_files=len(paths),
        current_path=root,
    )
    _publish(progress_callback, completed)
    return completed
'''

PATH.write_text(text, encoding="utf-8")
print("transactional empty-trash primitive applied")

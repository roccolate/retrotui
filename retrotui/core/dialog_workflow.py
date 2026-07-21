"""Explicit workflow metadata for application-level dialogs."""
from __future__ import annotations

from enum import Enum

__all__ = ("DialogWorkflowId", "bind_dialog")


class DialogWorkflowId(str, Enum):
    """Stable identifiers for application-level dialog workflows."""

    EXIT = "app.exit"
    SAVE_CONFIRM = "document.save_confirm"
    CALLBACK = "dialog.callback"


def bind_dialog(
    dialog,
    *,
    workflow_id,
    source_window=None,
    on_accept=None,
    on_cancel=None,
):
    """Attach explicit workflow ownership and callbacks to *dialog*."""
    if isinstance(workflow_id, DialogWorkflowId):
        workflow_id = workflow_id.value
    dialog.workflow_id = str(workflow_id)
    dialog.source_window = source_window
    dialog.source_window_id = getattr(source_window, "id", None)
    dialog.on_accept = on_accept
    dialog.on_cancel = on_cancel
    # Transitional public alias for existing integrations and tests.
    if callable(on_accept):
        dialog.callback = on_accept
    return dialog

"""
Shared clipboard helpers for RetroTUI windows.
"""
from __future__ import annotations

import shutil
import subprocess

_STATE = {"text": ""}


def clear_clipboard() -> None:
    """Clear internal clipboard text."""
    _STATE["text"] = ""


def has_clipboard_text() -> bool:
    """Return True when internal clipboard is not empty."""
    return bool(_STATE["text"])


def _detect_backend() -> str | None:
    """Return available system clipboard backend key, or None."""
    has_wl_copy = shutil.which("wl-copy")
    has_wl_paste = shutil.which("wl-paste")
    if has_wl_copy and has_wl_paste:
        return "wl"
    if shutil.which("xclip"):
        return "xclip"
    if shutil.which("xsel"):
        return "xsel"
    return None


def _system_copy(text: str) -> bool:
    """Try to copy text to system clipboard backend."""
    backend = _detect_backend()
    if backend is None:
        return False
    try:
        if backend == "wl":
            result = subprocess.run(
                ["wl-copy", "--type", "text/plain"],
                input=text,
                text=True,
                capture_output=True,
                check=False,
            )
        elif backend == "xclip":
            result = subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                text=True,
                capture_output=True,
                check=False,
            )
        else:
            result = subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=text,
                text=True,
                capture_output=True,
                check=False,
            )
    except OSError:
        return False
    return result.returncode == 0


def _system_paste() -> str | None:
    """Try to read text from system clipboard backend."""
    backend = _detect_backend()
    if backend is None:
        return None
    try:
        if backend == "wl":
            result = subprocess.run(
                ["wl-paste", "--no-newline"],
                text=True,
                capture_output=True,
                check=False,
            )
        elif backend == "xclip":
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                text=True,
                capture_output=True,
                check=False,
            )
        else:
            result = subprocess.run(
                ["xsel", "--clipboard", "--output"],
                text=True,
                capture_output=True,
                check=False,
            )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout or ""


def copy_text(text: str, sync_system: bool = True) -> str:
    """Store text in internal clipboard and optionally mirror to system clipboard."""
    _STATE["text"] = text or ""
    if sync_system:
        _system_copy(_STATE["text"])
    return _STATE["text"]


def paste_text(sync_system: bool = True) -> str:
    """Return clipboard text, optionally refreshing from system clipboard."""
    if sync_system:
        system_text = _system_paste()
        if system_text is not None:
            _STATE["text"] = system_text
    return _STATE["text"]

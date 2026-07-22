"""Secure, crash-resistant text file publication helpers."""
from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path


def _existing_regular_mode(target: Path) -> int | None:
    """Return the permission bits of an existing regular target."""
    try:
        target_stat = os.stat(target, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(target_stat.st_mode):
        return None
    return stat.S_IMODE(target_stat.st_mode)


def _fsync_parent_directory(parent: Path) -> None:
    """Best-effort directory sync after publishing a replacement on POSIX."""
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        directory_fd = os.open(parent, flags)
    except OSError:
        return
    try:
        try:
            os.fsync(directory_fd)
        except OSError:
            # Some filesystems do not support syncing directory descriptors.
            pass
    finally:
        os.close(directory_fd)


def _apply_preserved_mode(temp_path: Path, preserved_mode: int) -> None:
    """Apply mode bits after close on platforms without ``fchmod``."""
    if os.name == "nt":
        # Windows does not implement ``chmod(..., follow_symlinks=False)``.
        # The path is an unpredictable sibling created exclusively by mkstemp,
        # so no attacker-controlled predictable staging name is followed here.
        os.chmod(temp_path, preserved_mode)
        return
    os.chmod(temp_path, preserved_mode, follow_symlinks=False)


def atomic_write_text(path, text: str, *, encoding: str = "utf-8") -> Path:
    """Atomically publish *text* without using a predictable temporary path.

    The temporary file is created exclusively in the target directory, flushed
    before publication, and removed on every failure path. Existing regular-file
    permission bits are retained. New files keep the private mode supplied by
    :func:`tempfile.mkstemp`.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    preserved_mode = _existing_regular_mode(target)

    fd = -1
    temp_path: Path | None = None
    mode_applied_to_fd = False
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.retrotui-",
            suffix=".tmp",
            dir=os.fspath(target.parent),
        )
        temp_path = Path(temp_name)

        if preserved_mode is not None and hasattr(os, "fchmod"):
            os.fchmod(fd, preserved_mode)
            mode_applied_to_fd = True

        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as stream:
            fd = -1
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())

        if preserved_mode is not None and not mode_applied_to_fd:
            _apply_preserved_mode(temp_path, preserved_mode)

        os.replace(temp_path, target)
        temp_path = None
        _fsync_parent_directory(target.parent)
        return target
    finally:
        if fd >= 0:
            os.close(fd)
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass

"""Shared test helpers.

These helpers avoid writing outside the repo (sandbox restriction) and provide
a small fake `curses` module for platforms where `_curses` is unavailable.
"""

from __future__ import annotations

import shutil
import types
import uuid
from pathlib import Path


class RepoTemporaryDirectory:
    """Minimal TemporaryDirectory-like helper that stays inside the repo."""

    def __init__(self, path: Path):
        self._path = path
        self.name = str(path)

    def cleanup(self) -> None:
        shutil.rmtree(self._path, ignore_errors=True)

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.cleanup()
        return False


def make_repo_tmpdir(prefix: str = "_tmp_") -> RepoTemporaryDirectory:
    """Create a temp directory under tests/ (ignored by git).

    The sandbox only allows writes inside the workspace, so using the system temp
    directory (e.g. %TEMP%) can fail with PermissionError.

    We also avoid tempfile.TemporaryDirectory here: on some Windows/Python builds
    it can create directories with restrictive ACLs that prevent file creation.
    """

    tests_dir = Path(__file__).resolve().parent
    for _ in range(100):
        path = tests_dir / f"{prefix}{uuid.uuid4().hex[:12]}"
        try:
            path.mkdir()
        except FileExistsError:
            continue
        return RepoTemporaryDirectory(path)

    raise RuntimeError("failed to create a repo temp directory")


def make_fake_curses() -> types.ModuleType:
    """Return a minimal fake curses module for unit tests."""

    fake = types.ModuleType("curses")

    # Common attributes used across the codebase.
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.A_DIM = 4

    fake.COLOR_RED = 1
    fake.COLOR_GREEN = 2
    fake.COLOR_YELLOW = 3

    # Key codes (values are conventional but arbitrary for our logic tests).
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_LEFT = 260
    fake.KEY_RIGHT = 261
    fake.KEY_HOME = 262
    fake.KEY_END = 360
    fake.KEY_PPAGE = 339
    fake.KEY_NPAGE = 338
    fake.KEY_BACKSPACE = 263
    fake.KEY_DC = 330
    fake.KEY_ENTER = 343
    fake.KEY_MOUSE = 409
    fake.KEY_RESIZE = 410
    fake.KEY_F2 = 266
    fake.KEY_F4 = 268
    fake.KEY_F5 = 269
    fake.KEY_F6 = 270
    fake.KEY_F7 = 271
    fake.KEY_F8 = 272
    fake.KEY_F9 = 273
    fake.KEY_F10 = 274

    # Mouse flags (bitmasks).
    fake.BUTTON1_PRESSED = 0x2
    fake.BUTTON1_RELEASED = 0x4
    fake.BUTTON1_CLICKED = 0x8
    fake.BUTTON1_DOUBLE_CLICKED = 0x10
    fake.BUTTON4_PRESSED = 0x20
    fake.BUTTON5_PRESSED = 0x40
    fake.ALL_MOUSE_EVENTS = 0xFFFF
    fake.REPORT_MOUSE_POSITION = 0x10000

    # API surface used by the code under test.
    fake.error = Exception
    fake.color_pair = lambda value: int(value) * 10
    fake.init_pair = lambda *_args, **_kwargs: None
    fake.start_color = lambda: None
    fake.use_default_colors = lambda: None
    fake.init_color = lambda *_args, **_kwargs: None
    fake.can_change_color = lambda: False
    fake.COLORS = 16
    fake.beep = lambda: None

    return fake

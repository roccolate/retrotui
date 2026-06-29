"""
File viewer type detection, opening, and video/URL dialog flows.
"""

import os
import logging

from ..constants import BINARY_DETECT_CHUNK_SIZE
from ..utils import is_video_file, play_ascii_video as _play_ascii_video_backend
from ..apps.notepad import NotepadWindow
from ..apps.logviewer import LogViewerWindow
from ..apps.image_viewer import ImageViewerWindow
from ..apps.hexviewer import HexViewerWindow
from ..apps.markdown_viewer import MarkdownViewerWindow
from ..ui.dialog import Dialog, InputDialog
from .actions import ActionResult, ActionType

LOGGER = logging.getLogger(__name__)

# Margin subtracted from screen dimensions when sizing viewer windows.
_WINDOW_MARGIN = 4
_LOG_EXTENSIONS = {'.log', '.out', '.err'}


def detect_viewer_type(filepath, default_word_wrap=False):
    """Determine the appropriate viewer for a file.

    Returns a tuple ``(WindowClass, base_x, base_y, max_w, max_h, extra_kwargs)``.
    """
    lower_path = filepath.lower()
    ext = os.path.splitext(lower_path)[1]

    # ``/log/`` substring match misclassifies paths like
    # ``/home/user/blog/file.txt``; compare against the path components
    # instead so only real ``log`` directory segments trigger the log
    # viewer.
    if ext in _LOG_EXTENSIONS:
        return (LogViewerWindow, 16, 4, 74, 22, {})
    normalised = lower_path.replace("\\", "/")
    try:
        parts = [p for p in normalised.split("/") if p]
    except AttributeError:
        parts = []
    if "log" in parts:
        return (LogViewerWindow, 16, 4, 74, 22, {})

    if ext in ImageViewerWindow.IMAGE_EXTENSIONS:
        return (ImageViewerWindow, 14, 3, 84, 26, {})

    if ext == '.md':
        return (MarkdownViewerWindow, 18, 3, 70, 25, {})

    # Content-based detection: null bytes indicate a binary file.
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(BINARY_DETECT_CHUNK_SIZE)
            if b'\x00' in chunk:
                return (HexViewerWindow, 12, 3, 92, 26, {})
    except OSError:
        pass

    # Default: plain-text viewer.
    return (
        NotepadWindow,
        18, 3, 70, 25,
        {'wrap_default': default_word_wrap},
    )


def open_file_viewer(app, filepath):
    """Open file in the best available viewer."""
    if is_video_file(filepath):
        play_ascii_video(app, filepath)
        return

    cls, base_x, base_y, max_w, max_h, extra_kwargs = detect_viewer_type(
        filepath,
        default_word_wrap=getattr(app, 'default_word_wrap', False),
    )
    h, w = app.stdscr.getmaxyx()
    ox, oy = app._next_window_offset(base_x, base_y)
    win = cls(
        ox, oy,
        min(max_w, w - _WINDOW_MARGIN),
        min(max_h, h - _WINDOW_MARGIN),
        filepath=filepath,
        **extra_kwargs,
    )
    app._spawn_window(win)


def play_ascii_video(app, filepath, subtitle_path=None):
    """Run ASCII video playback and surface backend errors in a dialog."""
    success, error = _play_ascii_video_backend(app.stdscr, filepath, subtitle_path=subtitle_path)
    if not success:
        app.dialog = Dialog('ASCII Video Error', error, ['OK'], width=58)


def show_url_dialog(app, source_win, default_url=None):
    """Show input dialog for web URLs."""
    initial = default_url or getattr(source_win, 'url', '')
    dialog = InputDialog('RetroNet Explorer', 'Enter URL:', initial_value=initial, width=64)
    dialog.callback = source_win.open_path
    app.dialog = dialog


def show_video_open_dialog(app):
    """Open dialog flow to play a video path without using File Manager."""
    dialog = InputDialog('Open Video', 'Enter video path:', width=64)
    dialog.callback = lambda filepath: handle_video_path_input(app, filepath)
    app.dialog = dialog


def handle_video_path_input(app, filepath):
    """Validate selected video path and request optional subtitle path."""
    raw_path = str(filepath or '').strip()
    if not raw_path:
        return ActionResult(ActionType.ERROR, 'Video path cannot be empty.')
    video_path = os.path.abspath(os.path.expanduser(raw_path))
    if not os.path.isfile(video_path):
        return ActionResult(ActionType.ERROR, f'Video file not found:\n{video_path}')
    if not is_video_file(video_path):
        return ActionResult(ActionType.ERROR, f'Unsupported video format:\n{video_path}')

    dialog = InputDialog(
        'Subtitles (Optional)',
        'Enter subtitle path (.srt/.ass/.vtt) or leave empty:',
        width=70,
    )
    dialog.callback = (
        lambda subtitle_path, selected_video=video_path: handle_subtitle_path_input(
            app,
            selected_video,
            subtitle_path,
        )
    )
    app.dialog = dialog
    return None


def handle_subtitle_path_input(app, video_path, subtitle_path):
    """Validate optional subtitle path and start playback."""
    subtitle = str(subtitle_path or '').strip()
    if subtitle:
        subtitle = os.path.abspath(os.path.expanduser(subtitle))
        if not os.path.isfile(subtitle):
            return ActionResult(ActionType.ERROR, f'Subtitle file not found:\n{subtitle}')
    else:
        subtitle = None
    play_ascii_video(app, video_path, subtitle_path=subtitle)
    return None

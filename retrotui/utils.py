"""
Utility functions for RetroTUI.
"""
import curses
import os
import sys
import shutil
import subprocess
import time
import locale
from .constants import (
    C_DESKTOP, C_WIN_TITLE, C_WIN_INACTIVE, C_ICON, C_MENUBAR, C_MENU_ITEM,
    C_MENU_SEL, C_WIN_BORDER, C_WIN_TITLE_INV, C_WIN_BODY, C_BUTTON,
    C_BUTTON_SEL, C_DIALOG, C_STATUS, C_ICON_SEL, C_SCROLLBAR, C_FM_SELECTED,
    C_FM_DIR, C_TASKBAR, BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_H, BOX_V,
    SB_TL, SB_TR, SB_BL, SB_BR, SB_H, SB_V, VIDEO_EXTENSIONS
)
from .theme import ROLE_TO_PAIR_ID, get_theme


def init_colors(theme_key_or_obj=None):
    """Initialize curses color pairs from the active semantic theme."""
    curses.start_color()
    curses.use_default_colors()

    if theme_key_or_obj is None:
        theme = get_theme(None)
    elif isinstance(theme_key_or_obj, str):
        theme = get_theme(theme_key_or_obj)
    else:
        theme = theme_key_or_obj

    use_extended = bool(
        theme.custom_colors
        and theme.pairs_256
        and curses.can_change_color()
        and curses.COLORS >= 256
    )
    if use_extended:
        for color_id, rgb in theme.custom_colors.items():
            curses.init_color(color_id, *rgb)
        pair_map = theme.pairs_256_win32 if sys.platform == 'win32' and getattr(theme, 'pairs_256_win32', None) else theme.pairs_256
    else:
        pair_map = theme.pairs_base_win32 if sys.platform == 'win32' and getattr(theme, 'pairs_base_win32', None) else theme.pairs_base

    for role, pair_id in ROLE_TO_PAIR_ID.items():
        fg, bg = pair_map[role]
        curses.init_pair(pair_id, fg, bg)

    # Initialize terminal ANSI colors (0-7) with window background
    term_bg = pair_map["window_body"][1]
    for i in range(8):
        # pair 50+i: fg=i, bg=term_bg
        curses.init_pair(50 + i, i, term_bg)


def theme_attr(role):
    """Return curses color attribute for a semantic role."""
    return curses.color_pair(ROLE_TO_PAIR_ID[role])

def safe_addstr(win, y, x, text, attr=0):
    """Write string safely, clipping to window bounds."""
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    max_len = w - x - 1
    if max_len <= 0:
        return
    try:
        win.addnstr(y, x, text, max_len, attr)
    except curses.error:
        pass

def normalize_key_code(key):
    """Normalize keys from get_wch()/getch() into comparable integer codes."""
    if isinstance(key, int):
        return key
    if not isinstance(key, str) or not key or len(key) != 1:
        return None
    if key in ('\n', '\r'):
        return 10
    if key == '\x1b':
        return 27
    if key == '\t':
        return 9
    if key == '\x7f':
        return 127
    if key == '\b':
        return 8
    return ord(key)

def draw_box(win, y, x, h, w, attr=0, double=True):
    """Draw a box with double or single line borders."""
    if double:
        tl, tr, bl, br, hz, vt = BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_H, BOX_V
    else:
        tl, tr, bl, br, hz, vt = SB_TL, SB_TR, SB_BL, SB_BR, SB_H, SB_V

    safe_addstr(win, y, x, tl + hz * (w - 2) + tr, attr)
    for i in range(1, h - 1):
        safe_addstr(win, y + i, x, vt, attr)
        safe_addstr(win, y + i, x + w - 1, vt, attr)
    safe_addstr(win, y + h - 1, x, bl + hz * (w - 2) + br, attr)

def check_unicode_support():
    """Check if terminal supports Unicode."""
    try:
        '╔'.encode(locale.getpreferredencoding())
        return True
    except (UnicodeEncodeError, LookupError):
        return False

def get_system_info():
    """Get system information for About dialog."""
    info = []
    try:
        uname = os.uname()
        info.append(f'OS: {uname.sysname} {uname.release}')
        info.append(f'Host: {uname.nodename}')
        info.append(f'Arch: {uname.machine}')
    except (AttributeError, OSError):
        info.append('OS: Linux')

    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemTotal'):
                    mem_kb = int(line.split()[1])
                    info.append(f'RAM: {mem_kb // 1024} MB')
                    break
    except (OSError, ValueError, IndexError):
        pass

    info.append(f'Terminal: {os.environ.get("TERM", "unknown")}')
    info.append(f'Shell: {os.path.basename(os.environ.get("SHELL", "unknown"))}')
    info.append(f'Python: {sys.version.split()[0]}')
    return info

def is_video_file(filepath):
    """Return True if filepath extension looks like video."""
    _, ext = os.path.splitext(filepath.lower())
    return ext in VIDEO_EXTENSIONS

def _with_subtitle_args(cmd, subtitle_path, *, backend):
    """Append subtitle arguments for the selected backend."""
    if not subtitle_path:
        return cmd
    if backend == 'mpv':
        return cmd + [f'--sub-file={subtitle_path}']
    return cmd + ['-sub', subtitle_path]

def play_ascii_video(stdscr, filepath, subtitle_path=None):
    """
    Play video in terminal using mpv (preferred) or mplayer (fallback).
    Returns (success, error_message).
    """
    video_path = os.path.abspath(os.path.expanduser(str(filepath)))
    subtitle_path = str(subtitle_path or '').strip()
    subtitle_path = os.path.abspath(os.path.expanduser(subtitle_path)) if subtitle_path else None

    mpv = shutil.which('mpv')
    mplayer = shutil.which('mplayer')

    if not mpv and not mplayer:
        return (
            False,
            'No se encontro mpv ni mplayer.\n\n'
            'Instala uno de los siguientes:\n'
            '  sudo apt install mpv\n'
            '  sudo apt install mplayer'
        )

    # Build command list: try best option first
    if mpv:
        base = [
            mpv,
            '--vo=tct',
            '--really-quiet',
            '--osd-level=1',
            '--osd-duration=2200',
            '--osd-playing-msg=RetroTUI: Space pause | Left/Right seek | q quit',
        ]
        with_sub = _with_subtitle_args(base, subtitle_path, backend='mpv')
        commands = [
            (with_sub + [video_path], 'mpv (tct)'),
            (with_sub + ['--ao=null', video_path], 'mpv (tct, no audio)'),
        ]
    else:
        base = [mplayer, '-vo', 'caca', '-really-quiet', '-osdlevel', '1']
        with_sub = _with_subtitle_args(base, subtitle_path, backend='mplayer')
        commands = [
            (with_sub + [video_path], 'mplayer (caca)'),
            (with_sub + ['-ao', 'null', video_path], 'mplayer (caca, no audio)'),
            (
                _with_subtitle_args([mplayer, '-vo', 'aa', '-really-quiet'], subtitle_path, backend='mplayer')
                + ['-ao', 'null', video_path],
                'mplayer (aa, no audio)',
            ),
        ]

    exit_code = 1
    backend_used = ''
    playback_succeeded = False
    try:
        curses.def_prog_mode()
        curses.endwin()
        for cmd, name in commands:
            start = time.time()
            result = subprocess.run(cmd)
            elapsed = time.time() - start
            exit_code = result.returncode
            backend_used = name
            if exit_code == 0 or elapsed > 2:
                playback_succeeded = True
                break  # Video played (even if audio failed)
        if playback_succeeded:
            return True, None
        backend_label = backend_used or 'desconocido'
        return False, (
            'No se pudo reproducir el video.\n'
            f'Backend probado: {backend_label}\n'
            f'Codigo de salida: {exit_code}'
        )
    except OSError as e:
        return False, f'No se pudo ejecutar:\n{e}'
    finally:
        try:
            curses.reset_prog_mode()
            if stdscr:
                stdscr.refresh()
        except curses.error:
            pass

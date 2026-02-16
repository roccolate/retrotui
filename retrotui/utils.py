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

def init_colors():
    """Initialize Windows 3.1 color scheme."""
    curses.start_color()
    curses.use_default_colors()

    if curses.can_change_color() and curses.COLORS >= 256:
        # Custom Win3.1 palette
        curses.init_color(20, 0, 500, 500)      # Teal desktop
        curses.init_color(21, 0, 0, 500)         # Dark blue title
        curses.init_color(22, 800, 800, 800)     # Light gray
        curses.init_color(23, 600, 600, 600)     # Medium gray
        curses.init_pair(C_DESKTOP,       curses.COLOR_CYAN, 20)
        curses.init_pair(C_WIN_TITLE,     curses.COLOR_WHITE, 21)
        curses.init_pair(C_WIN_INACTIVE,  curses.COLOR_WHITE, 23)
        curses.init_pair(C_ICON,          curses.COLOR_BLACK, 20)  # Black on teal
    else:
        curses.init_pair(C_DESKTOP,       curses.COLOR_CYAN, curses.COLOR_CYAN)
        curses.init_pair(C_WIN_TITLE,     curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(C_WIN_INACTIVE,  curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(C_ICON,          curses.COLOR_BLACK, curses.COLOR_CYAN)

    curses.init_pair(C_MENUBAR,       curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_MENU_ITEM,     curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_MENU_SEL,      curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(C_WIN_BORDER,    curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(C_WIN_TITLE_INV, curses.COLOR_BLUE, curses.COLOR_WHITE)
    curses.init_pair(C_WIN_BODY,      curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_BUTTON,        curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_BUTTON_SEL,    curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(C_DIALOG,        curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_STATUS,        curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(C_ICON_SEL,      curses.COLOR_YELLOW, curses.COLOR_BLUE)
    curses.init_pair(C_SCROLLBAR,     curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_FM_SELECTED,   curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(C_FM_DIR,        curses.COLOR_BLUE, curses.COLOR_WHITE)
    curses.init_pair(C_TASKBAR,       curses.COLOR_BLACK, curses.COLOR_WHITE)

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
        'â•”'.encode(locale.getpreferredencoding())
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

def play_ascii_video(stdscr, filepath):
    """
    Play video in terminal using mpv (preferred) or mplayer (fallback).
    Returns (success, error_message).
    """
    mpv = shutil.which('mpv')
    mplayer = shutil.which('mplayer')

    if not mpv and not mplayer:
        return False, 'No se encontrÃ³ mpv ni mplayer.\n\nInstala uno de los siguientes:\n  sudo apt install mpv\n  sudo apt install mplayer'

    # Build command list: try best option first
    if mpv:
        commands = [
            ([mpv, '--vo=tct', '--really-quiet', filepath], 'mpv (tct)'),
            ([mpv, '--vo=tct', '--really-quiet', '--ao=null', filepath], 'mpv (tct, no audio)'),
        ]
    else:
        commands = [
            ([mplayer, '-vo', 'caca', '-really-quiet', filepath], 'mplayer (caca)'),
            ([mplayer, '-vo', 'caca', '-really-quiet', '-ao', 'null', filepath], 'mplayer (caca, no audio)'),
            ([mplayer, '-vo', 'aa', '-really-quiet', '-ao', 'null', filepath], 'mplayer (aa, no audio)'),
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
            f'CÃ³digo de salida: {exit_code}'
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

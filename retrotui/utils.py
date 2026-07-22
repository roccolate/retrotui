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
from wcwidth import wcwidth, wcswidth
from .constants import (
    C_DESKTOP, C_WIN_TITLE, C_WIN_INACTIVE, C_ICON, C_MENUBAR, C_MENU_ITEM,
    C_MENU_SEL, C_WIN_BORDER, C_WIN_TITLE_INV, C_WIN_BODY, C_BUTTON,
    C_BUTTON_SEL, C_DIALOG, C_STATUS, C_ICON_SEL, C_SCROLLBAR, C_FM_SELECTED,
    C_FM_DIR, C_TASKBAR, BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_H, BOX_V,
    SB_TL, SB_TR, SB_BL, SB_BR, SB_H, SB_V, VIDEO_EXTENSIONS,
    _CURSES_ERROR, C_ANSI_FGBG_START,
)
from .theme import ROLE_TO_PAIR_ID, get_theme

# Cache for theme_attr() lookups - invalidated by init_colors().
_theme_attr_cache: dict[str, int] = {}
_CURSES_SETATTR_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_THEME_ATTR_ERRORS = (
    AttributeError,
    KeyError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)
_SAFE_ADDSTR_PROBE_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
_COLOR_MODE_VALUES = {"auto", "base", "256"}

# Provide safe fallbacks for curses constants that may be missing in some test
# environments (for example when tests inject a fake `curses` module or on
# platforms without full curses support). Values are chosen to be stable and
# non-conflicting for bitwise checks in code and tests.
_CURSES_FALLBACKS = {
    'KEY_UP': 259,
    'KEY_DOWN': 258,
    'KEY_LEFT': 260,
    'KEY_RIGHT': 261,
    'KEY_NPAGE': 338,
    'KEY_PPAGE': 339,
    'KEY_DC': 330,
    'KEY_F1': 265,
    'KEY_F2': 266,
    'KEY_F3': 267,
    'KEY_F4': 268,
    'KEY_F5': 269,
    'KEY_F6': 270,
    'KEY_F7': 271,
    'KEY_F8': 272,
    'KEY_F9': 273,
    'KEY_F10': 274,
    'KEY_F11': 275,
    'KEY_F12': 276,
    # Mouse button flags (bitmasks)
    'BUTTON1_PRESSED': 1 << 8,
    'BUTTON1_RELEASED': 1 << 9,
    'BUTTON1_CLICKED': 1 << 10,
    'BUTTON1_DOUBLE_CLICKED': 1 << 11,
}

for _name, _val in _CURSES_FALLBACKS.items():
    if not hasattr(curses, _name):
        try:
            setattr(curses, _name, _val)
        except _CURSES_SETATTR_ERRORS:
            pass


def _resolve_color_mode():
    """Return normalized color mode: auto, base, or 256."""
    raw = str(os.environ.get("RETROTUI_COLOR_MODE", "auto")).strip().lower()
    if raw in _COLOR_MODE_VALUES:
        return raw
    if raw in {"8", "16", "ansi"}:
        return "base"
    if raw in {"xterm-256color", "xterm256"}:
        return "256"
    return "auto"


def _terminal_color_count():
    """Return reported terminal color count, defaulting to 0 on probe errors."""
    try:
        return int(getattr(curses, "COLORS", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _can_change_terminal_palette():
    """Return True when curses reports palette redefinition support."""
    probe = getattr(curses, "can_change_color", None)
    if not callable(probe):
        return False
    try:
        return bool(probe())
    except _THEME_ATTR_ERRORS:
        return False


def _select_theme_pair_map(theme):
    """Select base/256 pair map according to capabilities and env override."""
    mode = _resolve_color_mode()
    supports_256 = bool(theme.pairs_256 and _terminal_color_count() >= 256)
    use_256 = supports_256 and mode != "base"

    if use_256:
        pair_map = theme.pairs_256
        if pair_map:
            return pair_map, True

    return theme.pairs_base, False


def _should_apply_custom_colors(theme, using_256):
    """Return True when custom palette remapping should be applied."""
    if not using_256 or not theme.custom_colors:
        return False
    # Disabled by default for cross-terminal consistency.
    raw = str(os.environ.get("RETROTUI_APPLY_CUSTOM_COLORS", "")).strip().lower()
    return raw in _TRUTHY_ENV_VALUES


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

    pair_map, using_256 = _select_theme_pair_map(theme)

    if _should_apply_custom_colors(theme, using_256) and _can_change_terminal_palette():
        for color_id, rgb in theme.custom_colors.items():
            curses.init_color(color_id, *rgb)

    for role, pair_id in ROLE_TO_PAIR_ID.items():
        fg, bg = pair_map[role]
        curses.init_pair(pair_id, fg, bg)

    # Initialize terminal ANSI colors (0-7) with themed terminal background
    term_bg = pair_map.get("terminal", pair_map["window_body"])[1]
    for i in range(8):
        # pair 50+i: fg=i, bg=term_bg
        curses.init_pair(50 + i, i, term_bg)

    # ANSI fg x bg combos (pair 58..121 = 58 + fg*8 + bg). Required so that
    # SGR sequences like \x1b[31;44m pick a pair encoding both fg and bg,
    # not just fg. Without this, background colors are silently ignored.
    for fg in range(8):
        for bg in range(8):
            curses.init_pair(C_ANSI_FGBG_START + fg * 8 + bg, fg, bg)

    # Invalidate theme_attr cache so next calls pick up new pairs.
    _theme_attr_cache.clear()


def theme_attr(role):
    """Return curses color attribute for a semantic role (cached)."""
    cached = _theme_attr_cache.get(role)
    if cached is not None:
        return cached
    try:
        attr = curses.color_pair(ROLE_TO_PAIR_ID[role])
    except _THEME_ATTR_ERRORS:
        # curses may not be initialized in some test environments; fall back to 0
        attr = 0
    _theme_attr_cache[role] = attr
    return attr

def text_display_width(text) -> int:
    """Return the physical terminal-column width of arbitrary UI text."""
    value = str(text or "")
    width = wcswidth(value)
    if width >= 0:
        return width

    # Preserve safe layout even when a title contains an unprintable codepoint.
    total = 0
    for ch in value:
        ch_width = wcwidth(ch)
        total += ch_width if ch_width >= 0 else 1
    return total


def clip_text_columns(text, max_columns, *, suffix="") -> str:
    """Clip text to physical terminal columns without splitting combining text."""
    value = str(text or "")
    columns = max(0, int(max_columns))
    if columns <= 0:
        return ""
    if text_display_width(value) <= columns:
        return value

    suffix_value = str(suffix or "")
    suffix_width = text_display_width(suffix_value)
    if suffix_width > columns:
        suffix_value = ""
        suffix_width = 0
    content_limit = columns - suffix_width

    clipped = ""
    for ch in value:
        candidate = clipped + ch
        if text_display_width(candidate) > content_limit:
            break
        clipped = candidate
    return clipped + suffix_value


def pad_text_columns(text, columns, *, suffix="") -> str:
    """Clip and right-pad text to an exact physical terminal-column width."""
    width = max(0, int(columns))
    fitted = clip_text_columns(text, width, suffix=suffix)
    return fitted + (" " * max(0, width - text_display_width(fitted)))


def center_text_columns(text, columns, *, suffix="") -> str:
    """Clip and center text inside an exact physical terminal-column width."""
    width = max(0, int(columns))
    fitted = clip_text_columns(text, width, suffix=suffix)
    remaining = max(0, width - text_display_width(fitted))
    left = remaining // 2
    return (" " * left) + fitted + (" " * (remaining - left))


def safe_addstr(win, y, x, text, attr=0, *, _bounds=None):
    """Write string safely, clipping to window bounds.

    When *_bounds* is a ``(h, w)`` tuple the expensive ``getmaxyx()`` call and
    Mock-detection logic are skipped entirely.  The rendering hot-path should
    always supply pre-computed bounds.
    """
    if x < 0 or y < 0:
        return
    if _bounds is not None:
        h, w = _bounds
    else:
        # Slow path: probe getmaxyx with Mock-tolerance for test environments.
        res = win.getmaxyx()
        if not isinstance(res, (list, tuple)):
            try:
                if callable(res):
                    res = res()
            except _SAFE_ADDSTR_PROBE_ERRORS:
                res = None
            if not isinstance(res, (list, tuple)):
                try:
                    h = int(getattr(res, 'h', None) or getattr(res, 'rows', None) or getattr(res, 'height', None))
                    w = int(getattr(res, 'w', None) or getattr(res, 'cols', None) or getattr(res, 'width', None))
                    res = (h, w)
                except _SAFE_ADDSTR_PROBE_ERRORS:
                    return
        h, w = res
    if y >= h or x >= w:
        return
    max_len = w - x
    if max_len <= 0:
        return
    try:
        win.addnstr(y, x, text, max_len, attr)
    except curses.error:
        if max_len <= 1:
            return
        try:
            win.addnstr(y, x, text, max_len - 1, attr)
        except curses.error:
            pass


def toml_basic_string(value: str) -> str:
    """Escape *value* for safe inclusion in a TOML basic string literal.

    Covers the characters most likely to appear in user-edited settings
    (config theme names, icon-style keys, bookmark titles/URLs). This is
    intentionally a minimal subset — full TOML also handles unicode escapes
    and multi-line basic strings, but RetroTUI data never needs them.
    """
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace('"', '\\"')
    )


def decode_toml_basic_string(value: str) -> str:
    """Decode the small TOML escape subset that ``toml_basic_string`` emits.

    Inverse of :func:`toml_basic_string`. Unknown escape sequences are kept
    verbatim — this matches the lenient behaviour of the previous inline
    parsers in ``icon_manager`` and ``config``.
    """
    out = []
    escape = False
    for ch in value:
        if escape:
            out.append({"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}.get(ch, ch))
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        out.append(ch)
    if escape:
        # Trailing backslash with nothing after it; keep the literal char.
        out.append("\\")
    return "".join(out)


def atomic_write_text(path, text: str, *, encoding: str = "utf-8"):
    """Write *text* atomically to *path*.

    Writes to ``<name>.tmp`` next to *path* and then ``os.replace``s the
    temp file over *path*. If the process is killed mid-write the user
    keeps the previous valid file instead of a truncated one. Returns the
    resolved *path*.
    """
    from pathlib import Path  # local import keeps top-level namespace clean

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(text, encoding=encoding, newline="\n")
    os.replace(tmp, target)
    return target


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

def draw_box(win, y, x, h, w, attr=0, double=True, *, _bounds=None):
    """Draw a box with double or single line borders.

    Pass ``_bounds`` to skip the ``getmaxyx()`` probe the underlying
    ``safe_addstr`` would otherwise run for every border segment.
    """
    if double:
        tl, tr, bl, br, hz, vt = BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_H, BOX_V
    else:
        tl, tr, bl, br, hz, vt = SB_TL, SB_TR, SB_BL, SB_BR, SB_H, SB_V

    safe_addstr(win, y, x, tl + hz * (w - 2) + tr, attr, _bounds=_bounds)
    for i in range(1, h - 1):
        safe_addstr(win, y + i, x, vt, attr, _bounds=_bounds)
        safe_addstr(win, y + i, x + w - 1, vt, attr, _bounds=_bounds)
    safe_addstr(win, y + h - 1, x, bl + hz * (w - 2) + br, attr, _bounds=_bounds)

def check_unicode_support():
    """Check if terminal supports Unicode."""
    force_ascii = str(os.environ.get('RETROTUI_FORCE_ASCII', '')).strip().lower()
    if force_ascii in {'1', 'true', 'yes', 'on'}:
        return False

    force_unicode = str(os.environ.get('RETROTUI_FORCE_UNICODE', '')).strip().lower()
    if force_unicode in {'1', 'true', 'yes', 'on'}:
        return True

    probe = '\u2554'
    stdout_encoding = getattr(sys.stdout, 'encoding', None)
    preferred_encoding = locale.getpreferredencoding(False)

    encodings = []
    if stdout_encoding:
        encodings.append(stdout_encoding)
    if preferred_encoding and preferred_encoding not in encodings:
        encodings.append(preferred_encoding)

    for enc in encodings:
        try:
            probe.encode(enc)
        except (UnicodeEncodeError, LookupError):
            continue
        if os.name == 'nt':
            norm = str(enc).replace('_', '-').lower()
            if 'utf-8' not in norm and 'utf8' not in norm:
                continue
        return True
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
        with open('/proc/meminfo', 'r', encoding='utf-8', errors='replace') as f:
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

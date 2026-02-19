"""
Minimal termios shim for Windows to support common tty operations
used by libraries that call `termios.tcgetattr`/`tcsetattr` or
`tty.setraw`/`tty.setcbreak`.

This provides a small subset of the termios API by mapping
local terminal flags to Windows console modes (via Win32 API).

Limitations: not a full POSIX implementation. Suitable for apps
that only need to switch console to raw/no-echo modes.
"""
from ctypes import windll, byref, c_uint

kernel32 = windll.kernel32
STD_INPUT_HANDLE = -10

# Console mode flags
ENABLE_ECHO_INPUT = 0x0004
ENABLE_LINE_INPUT = 0x0002
ENABLE_PROCESSED_INPUT = 0x0001

# Minimal termios flag constants (only those used by Python's tty module)
ECHO = 0x00000008
ICANON = 0x00000100
ISIG = 0x00000080

# Input flags (iflag) - provide IXON/IXOFF so code clearing them is a no-op
IXON = 0x00000400
IXOFF = 0x00001000


# termios.error exception expected by some code
class error(OSError):
    pass

# tcsetattr when to apply
TCSANOW = 0
TCSADRAIN = 1
TCSAFLUSH = 2


def _get_handle_and_mode():
    h = kernel32.GetStdHandle(STD_INPUT_HANDLE)
    # Validate handle: GetStdHandle can return NULL (0) or
    # INVALID_HANDLE_VALUE (-1) on error or when there's no console.
    if h in (0, -1):
        raise OSError("GetStdHandle returned invalid handle")
    mode = c_uint()
    if not kernel32.GetConsoleMode(h, byref(mode)):
        raise OSError("GetConsoleMode failed")
    return h, mode.value


def _set_mode(h, mode):
    if not kernel32.SetConsoleMode(h, c_uint(mode)):
        raise OSError("SetConsoleMode failed")


def tcgetattr(fd):
    """Return a list-like termios attributes object.

    We return a 7-tuple compatible with the POSIX structure used by
    the `tty` module: [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
    Many fields are synthetic on Windows; only `lflag` is meaningful
    for enabling/disabling echo and line input.
    """
    h, mode = _get_handle_and_mode()
    # Map console mode bits to lflag bits (ECHO, ICANON)
    lflag = 0
    if mode & ENABLE_ECHO_INPUT:
        lflag |= ECHO
    if mode & ENABLE_LINE_INPUT:
        lflag |= ICANON
    if mode & ENABLE_PROCESSED_INPUT:
        lflag |= ISIG

    # Return placeholders for other fields
    return [0, 0, 0, lflag, 0, 0, bytearray(32)]


def tcsetattr(fd, when, attributes):
    """Set terminal attributes. We only honour changes to lflag that
    affect echo and canonical mode.
    """
    if not isinstance(attributes, (list, tuple)) or len(attributes) < 4:
        raise ValueError("attributes must be a list with at least 4 items")

    lflag = attributes[3]
    h, old = _get_handle_and_mode()
    new = old
    # ECHO
    if lflag & ECHO:
        new |= ENABLE_ECHO_INPUT
    else:
        new &= ~ENABLE_ECHO_INPUT
    # ICANON (line input)
    if lflag & ICANON:
        new |= ENABLE_LINE_INPUT
    else:
        new &= ~ENABLE_LINE_INPUT

    # ISIG (processed input / signal handling)
    if lflag & ISIG:
        new |= ENABLE_PROCESSED_INPUT
    else:
        new &= ~ENABLE_PROCESSED_INPUT

    _set_mode(h, new)


def cfmakeraw(attributes):
    """Modify attributes in-place to set raw mode (approximation)."""
    # Clear ECHO, ICANON and ISIG in lflag
    attributes[3] &= ~(ECHO | ICANON | ISIG)
    return attributes

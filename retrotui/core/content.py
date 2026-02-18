"""Static UI content builders for RetroTUI core."""

from ..utils import get_system_info


def build_welcome_content(version: str) -> list[str]:
    """Build startup window content."""
    return [
        "",
        " +--------------------------------------+",
        f" |        Welcome to RetroTUI v{version:<6}   |",
        " |                                      |",
        " |  A Windows 3.1 style desktop         |",
        " |  environment for the Linux console.  |",
        " |                                      |",
        " |  Highlights:                         |",
        " |  - Modular package structure         |",
        " |  - ASCII video player                |",
        " |  - Per-window menus                  |",
        " |  - Text editor + file manager        |",
        " |                                      |",
        " |  Use mouse or keyboard to navigate.  |",
        " |  Press F9 to hide this forever.      |",
        " |  Press Ctrl+Q to exit.               |",
        " +--------------------------------------+",
        "",
    ]


def build_about_message(version: str) -> str:
    """Build About dialog body."""
    sys_info = get_system_info()
    return (
        f"RetroTUI v{version}\n"
        "A retro desktop environment for Linux console.\n\n"
        "System Information:\n"
        + "\n".join(sys_info)
        + "\n\nMouse: GPM/xterm protocol\nNo X11 required!"
    )


def build_help_message() -> str:
    """Build keyboard/mouse help text."""
    return (
        "Keyboard Controls:\n\n"
        "Tab       - Cycle windows\n"
        "Escape    - Close menu/dialog\n"
        "Enter     - Activate selection\n"
        "Ctrl+Q    - Exit\n"
        "F10       - Open menu\n"
        "Arrow keys - Navigate\n"
        "PgUp/PgDn - Scroll content\n\n"
        "File Manager:\n\n"
        "Up/Down   - Move selection\n"
        "Enter     - Open dir/file\n"
        "Backspace - Parent directory\n"
        "H         - Toggle hidden files\n"
        "Home/End  - First/last entry\n\n"
        "Notepad Editor:\n\n"
        "Arrows    - Move cursor\n"
        "Home/End  - Start/end of line\n"
        "PgUp/PgDn - Page up/down\n"
        "Backspace - Delete backward\n"
        "Delete    - Delete forward\n"
        "Ctrl+W    - Toggle word wrap\n\n"
        "Mouse Controls:\n\n"
        "Click      - Select/activate\n"
        "Drag title - Move window\n"
        "Drag border - Resize window\n"
        "Dbl-click title - Maximize\n"
        "[_]       - Minimize\n"
        "[#]       - Maximize/restore\n"
        "Scroll    - Scroll/select"
    )


def build_settings_content() -> list[str]:
    """Build placeholder settings panel text."""
    return [
        " +-- Display Settings ------------------+",
        " |                                      |",
        " |  Theme: [x] Windows 3.1              |",
        " |         [ ] DOS / CGA                |",
        " |         [ ] Windows 95               |",
        " |                                      |",
        " |  Desktop Pattern: . : *              |",
        " |                                      |",
        " |  Colors: 256-color mode              |",
        " |                                      |",
        " +--------------------------------------+",
    ]


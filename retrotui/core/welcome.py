"""Welcome-window construction and startup preference handling."""

import curses

from ..constants import WELCOME_WIN_HEIGHT, WELCOME_WIN_WIDTH
from ..ui.window import Window
from .actions import ActionResult, ActionType
from .content import build_welcome_content


def open_welcome_window(app, version):
    """Create, wire, and register the optional startup welcome window."""
    if not getattr(app, "show_welcome", False):
        return None

    height, width = app.stdscr.getmaxyx()
    win = Window(
        "Welcome to RetroTUI",
        width // 2 - WELCOME_WIN_WIDTH // 2,
        height // 2 - WELCOME_WIN_HEIGHT // 2,
        WELCOME_WIN_WIDTH,
        WELCOME_WIN_HEIGHT,
        content=build_welcome_content(version),
        resizable=False,
        minimizable=False,
        maximizable=False,
    )

    def refresh_content():
        win.content = build_welcome_content(
            version,
            show_on_startup=app.show_welcome,
        )

    def persist_preference(show_on_startup):
        app.apply_preferences(show_welcome=show_on_startup)
        refresh_content()
        app.persist_config()
        app._dirty = True

    def toggle_preference():
        persist_preference(not app.show_welcome)
        return ActionResult(ActionType.REFRESH)

    def checkbox_row():
        for index, line in enumerate(getattr(win, "content", ())):
            if "Show welcome on startup" in line:
                return win.y + 1 + index
        return None

    def handle_key(key):
        if getattr(curses, "KEY_F9", -1) == key or key == "KEY_F9":
            persist_preference(False)
            app.close_window(win)
            return ActionResult(ActionType.REFRESH)
        if key in (
            " ",
            "\n",
            "\r",
            10,
            13,
            getattr(curses, "KEY_ENTER", -1),
        ):
            return toggle_preference()
        return Window.handle_key(win, key)

    def handle_click(mx, my, bstate=None):
        _ = bstate
        row = checkbox_row()
        if row is not None and my == row:
            body_x, _body_y, body_width, _body_height = win.body_rect()
            if body_x <= mx < body_x + body_width:
                return toggle_preference()
        return Window.handle_click(win, mx, my)

    win.handle_key = handle_key
    win.handle_click = handle_click
    app._spawn_window(win)
    return win

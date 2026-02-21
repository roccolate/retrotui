"""Main loop helpers for RetroTUI."""

import curses


def clamp_windows_to_terminal(app):
    """Keep window origins inside current terminal bounds."""
    new_h, new_w = app.stdscr.getmaxyx()
    for win in app.windows:
        win.x = max(0, min(win.x, new_w - min(win.w, new_w)))
        win.y = max(1, min(win.y, new_h - min(win.h, new_h) - 1))


def draw_frame(app):
    """Render a full frame before reading input."""
    app.stdscr.erase()
    app.normalize_window_layers()
    app.draw_desktop()
    app.draw_icons()

    if not app.has_background_operation():
        for win in app.windows:
            win.draw(app.stdscr)

    _, width = app.stdscr.getmaxyx()
    app.menu.draw_bar(app.stdscr, width)
    app.menu.draw_dropdown(app.stdscr)
    app.draw_taskbar()
    app.draw_statusbar()

    if app.dialog:
        app.dialog.draw(app.stdscr)

    # Context menu drawn on top of menus but under modal dialogs.
    ctx = app.context_menu
    if ctx and ctx.is_open():
        ctx.draw(app.stdscr)

    app.stdscr.noutrefresh()
    curses.doupdate()


def read_input_key(stdscr):
    """Read one key from curses, returning None on timeout/no input."""
    try:
        return stdscr.get_wch()
    except curses.error:
        return None


def dispatch_input(app, key):
    """Dispatch one normalized input event."""
    if key is None:
        return

    # Handle context menu input first (modal behavior).
    ctx = app.context_menu
    if ctx and ctx.is_open():
        if isinstance(key, int) and key == curses.KEY_MOUSE:
            try:
                event = curses.getmouse()
                _, mx, my, _, bstate = event
                action = ctx.handle_click(mx, my)
                if action:
                    app.execute_action(action)
                    return
                # Click outside closed the menu — let event fall through.
                if ctx.is_open():
                     return
            except curses.error:
                pass
        else:
            action = ctx.handle_input(key)
            if action:
                app.execute_action(action)
            return

    if isinstance(key, int) and key == curses.KEY_MOUSE:
        try:
            event = curses.getmouse()
            app.handle_mouse(event)
        except curses.error:
            return
        return

    if isinstance(key, int) and key == curses.KEY_RESIZE:
        curses.update_lines_cols()
        clamp_windows_to_terminal(app)
        return

    app.handle_key(key)


def run_app_loop(app):
    """Run main draw/input loop with terminal cleanup on exit."""
    try:
        while app.running:
            app.poll_background_operation()
            draw_frame(app)
            key = read_input_key(app.stdscr)
            dispatch_input(app, key)
            app.poll_background_operation()
    finally:
        app.cleanup()

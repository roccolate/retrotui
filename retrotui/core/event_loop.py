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
    app._frame_size = app.stdscr.getmaxyx()
    app.stdscr.erase()
    app.normalize_window_layers()
    app.draw_desktop()
    app.draw_icons()

    if not app.has_background_operation():
        for win in app.windows:
            if getattr(win, "visible", True):
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
    """Dispatch one normalized input event.

    Returns True when the event likely changed UI state and should trigger redraw.
    """
    if key is None:
        return False

    # Handle context menu input first (modal behavior).
    ctx = app.context_menu
    if ctx and ctx.is_open():
        if isinstance(key, int) and key == curses.KEY_MOUSE:
            try:
                event = curses.getmouse()
                _, mx, my, _, _bstate = event
                action = ctx.handle_click(mx, my)
                if action:
                    app.execute_action(action)
                    return True
                # Click outside may close the menu; either way this was UI input.
                if ctx.is_open():
                    return True
            except curses.error:
                return False
        else:
            action = ctx.handle_input(key)
            if action:
                app.execute_action(action)
            return True

    if isinstance(key, int) and key == curses.KEY_MOUSE:
        try:
            event = curses.getmouse()
            return bool(app.handle_mouse(event))
        except curses.error:
            return False

    if isinstance(key, int) and key == curses.KEY_RESIZE:
        curses.update_lines_cols()
        clamp_windows_to_terminal(app)
        return True

    app.handle_key(key)
    return True


def _has_live_terminals(app):
    """Return True if any window has an active PTY session producing output."""
    for w in app.windows:
        session = getattr(w, '_session', None)
        if session is not None and getattr(session, 'running', False):
            return True
    return False


def run_app_loop(app):
    """Run main draw/input loop with terminal cleanup on exit."""
    install_handlers = getattr(app, "_install_runtime_signal_handlers", None)
    if callable(install_handlers):
        install_handlers()
    try:
        while app.running:
            app.poll_background_operation()
            # Always redraw when live terminals may have pending PTY output.
            if _has_live_terminals(app):
                app._dirty = True
            if getattr(app, '_dirty', True):
                draw_frame(app)
                app._dirty = False
            key = read_input_key(app.stdscr)
            if key is None:
                consume_sigint = getattr(app, "_consume_pending_sigint", None)
                if callable(consume_sigint):
                    key = consume_sigint()
            if dispatch_input(app, key):
                app._dirty = True
            app.poll_background_operation()
    finally:
        app.cleanup()

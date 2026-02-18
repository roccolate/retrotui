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
    normalize_layers = getattr(app, 'normalize_window_layers', None)
    if callable(normalize_layers):
        normalize_layers()
    app.draw_desktop()
    app.draw_icons()

    has_bg = getattr(app, 'has_background_operation', None)
    background_active = bool(has_bg()) if callable(has_bg) else False
    if not background_active:
        for win in app.windows:
            win.draw(app.stdscr)

    _, width = app.stdscr.getmaxyx()
    app.menu.draw_bar(app.stdscr, width)
    app.menu.draw_dropdown(app.stdscr)
    app.draw_taskbar()
    app.draw_statusbar()

    if app.dialog:
        app.dialog.draw(app.stdscr)

    # Context menu (if any) should be drawn on top of menus but under modal dialogs
    ctx = getattr(app, 'context_menu', None)
    if ctx and getattr(ctx, 'is_open', None) and ctx.is_open():
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

    # Handle context menu input first (modal behavior)
    ctx = getattr(app, 'context_menu', None)
    if ctx and getattr(ctx, 'is_open', None) and ctx.is_open():
        if isinstance(key, int) and key == curses.KEY_MOUSE:
            try:
                event = curses.getmouse()
                # If click is outside, context menu closes and returns None,
                # then we might want to process the click on the underlying window?
                # For now, let context menu consume the click if it handles it.
                _, mx, my, _, bstate = event
                action = ctx.handle_click(mx, my)
                if action:
                    app.execute_action(action)
                    return
                # If context menu closed but no action, it means we clicked outside.
                # We should allow the app to process this click (e.g. select another window)
                # But we must be careful not to re-process the click that opened the menu?
                # Actually, handle_click returns None and closes menu if outside.
                # So we let execution continue to app.handle_mouse(event) below IF menu closed.
                if ctx.is_open():
                     return
            except curses.error:
                pass
        else:
            # Keyboard input to context menu
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
    poll_background = getattr(app, 'poll_background_operation', None)
    try:
        while app.running:
            if callable(poll_background):
                poll_background()
            draw_frame(app)
            key = read_input_key(app.stdscr)
            dispatch_input(app, key)
            if callable(poll_background):
                poll_background()
    finally:
        app.cleanup()

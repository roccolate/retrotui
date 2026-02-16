"""Mouse routing helpers for RetroTUI."""

import curses


def handle_drag_resize_mouse(app, mx, my, bstate):
    """Handle active drag or resize operations."""
    any_dragging = any(w.dragging for w in app.windows)
    if any_dragging:
        if bstate & app.stop_drag_flags:
            for win in app.windows:
                win.dragging = False
            return True
        for win in app.windows:
            if win.dragging:
                h, w = app.stdscr.getmaxyx()
                new_x = mx - win.drag_offset_x
                new_y = my - win.drag_offset_y
                win.x = max(0, min(new_x, w - win.w))
                win.y = max(1, min(new_y, h - win.h - 1))
                return True
        return True

    any_resizing = any(w.resizing for w in app.windows)
    if any_resizing:
        if bstate & app.stop_drag_flags:
            for win in app.windows:
                win.resizing = False
                win.resize_edge = None
            return True
        for win in app.windows:
            if win.resizing:
                h, w = app.stdscr.getmaxyx()
                win.apply_resize(mx, my, w, h)
                return True
        return True
    return False


def handle_global_menu_mouse(app, mx, my, bstate):
    """Handle mouse interaction when the global menu is active."""
    if not app.menu.active:
        return False
    if bstate & curses.REPORT_MOUSE_POSITION:
        app.menu.handle_hover(mx, my)
        return True
    if bstate & app.click_flags:
        action = app.menu.handle_click(mx, my)
        if action:
            app.execute_action(action)
        return True
    if app.menu.hit_test_dropdown(mx, my) or my == 0:
        return True
    return False


def handle_window_mouse(app, mx, my, bstate):
    """Route mouse events to windows in z-order."""
    for win in reversed(app.windows):
        if not win.visible:
            continue

        click_flags = app.click_flags

        if win.on_close_button(mx, my) and (bstate & click_flags):
            app.close_window(win)
            return True

        if win.on_minimize_button(mx, my) and (bstate & click_flags):
            app.set_active_window(win)
            win.toggle_minimize()
            visible = [w for w in app.windows if w.visible]
            if visible:
                app.set_active_window(visible[-1])
            return True

        if win.on_maximize_button(mx, my) and (bstate & click_flags):
            app.set_active_window(win)
            h, w = app.stdscr.getmaxyx()
            win.toggle_maximize(w, h)
            return True

        if bstate & curses.BUTTON1_PRESSED:
            edge = win.on_border(mx, my)
            if edge:
                win.resizing = True
                win.resize_edge = edge
                app.set_active_window(win)
                return True

        if win.on_title_bar(mx, my):
            if bstate & curses.BUTTON1_DOUBLE_CLICKED:
                app.set_active_window(win)
                h, w = app.stdscr.getmaxyx()
                win.toggle_maximize(w, h)
                return True
            if bstate & curses.BUTTON1_PRESSED:
                if not win.maximized:
                    win.dragging = True
                    win.drag_offset_x = mx - win.x
                    win.drag_offset_y = my - win.y
                app.set_active_window(win)
                return True
            if bstate & curses.BUTTON1_CLICKED:
                app.set_active_window(win)
                return True

        if (bstate & curses.REPORT_MOUSE_POSITION) and win.window_menu and win.window_menu.active:
            if win.window_menu.handle_hover(mx, my, win.x, win.y, win.w):
                return True

        if win.window_menu and win.window_menu.active and not win.contains(mx, my):
            if bstate & click_flags:
                win.window_menu.active = False

        if win.contains(mx, my):
            if bstate & click_flags:
                app.set_active_window(win)
                for other_win in app.windows:
                    other_menu = getattr(other_win, "window_menu", None)
                    if other_win is win or not other_menu or not other_menu.active:
                        continue
                    other_menu.active = False
                result = win.handle_click(mx, my)
                app._dispatch_window_result(result, win)
                return True

            if bstate & curses.BUTTON4_PRESSED:
                win.handle_scroll('up', 3)
                return True

            if bstate & app.scroll_down_mask:
                win.handle_scroll('down', 3)
                return True
    return False


def handle_desktop_mouse(app, mx, my, bstate):
    """Handle desktop icon interactions and deselection."""
    if bstate & curses.BUTTON1_DOUBLE_CLICKED:
        icon_idx = app.get_icon_at(mx, my)
        if icon_idx >= 0:
            app.execute_action(app.icons[icon_idx]['action'])
            return True

    if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
        icon_idx = app.get_icon_at(mx, my)
        if icon_idx >= 0:
            app.selected_icon = icon_idx
            return True

    app.selected_icon = -1
    app.menu.active = False
    return True


def handle_mouse_event(app, event):
    """Handle mouse events."""
    try:
        _, mx, my, _, bstate = event
    except (TypeError, ValueError):
        return

    if app._handle_dialog_mouse(mx, my, bstate):
        return

    if my == 0 and (bstate & app.click_flags):
        action = app.menu.handle_click(mx, my)
        if action:
            app.execute_action(action)
        return

    if app._handle_drag_resize_mouse(mx, my, bstate):
        return

    if app._handle_global_menu_mouse(mx, my, bstate):
        return

    if (bstate & app.click_flags) and app.handle_taskbar_click(mx, my):
        return

    if app._handle_window_mouse(mx, my, bstate):
        return

    app._handle_desktop_mouse(mx, my, bstate)

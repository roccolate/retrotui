"""Mouse routing helpers for RetroTUI."""

import curses
import inspect
import time


def _invoke_mouse_handler(handler, mx, my, bstate):
    """Call mouse handlers with backward-compatible signature support."""
    try:
        params = inspect.signature(handler).parameters.values()
    except (TypeError, ValueError):
        params = ()

    positional = 0
    has_varargs = False
    for param in params:
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            has_varargs = True
            break
        if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            positional += 1

    if has_varargs or positional >= 3:
        return handler(mx, my, bstate)
    return handler(mx, my)


def _clear_pending_file_drags(app):
    """Clear pending drag candidates exposed by file-manager-like windows."""
    for win in getattr(app, 'windows', []):
        clearer = getattr(win, 'clear_pending_drag', None)
        if callable(clearer):
            clearer()


def _set_drag_target(app, target):
    """Track active drop target and update per-window highlight flags."""
    for win in getattr(app, 'windows', []):
        setattr(win, 'drop_target_highlight', bool(target is not None and win is target))
    setattr(app, 'drag_target_window', target)


def _clear_drag_state(app):
    """Reset drag payload/source/target state."""
    setattr(app, 'drag_payload', None)
    setattr(app, 'drag_source_window', None)
    _set_drag_target(app, None)


def _supports_file_drop_target(win):
    """Return True when window can accept dropped file paths."""
    return callable(getattr(win, 'open_path', None)) or callable(
        getattr(win, 'accept_dropped_path', None)
    )


def _find_drop_target_window(app, mx, my):
    """Return topmost visible drop target under pointer, excluding source window."""
    source = getattr(app, 'drag_source_window', None)
    for win in reversed(getattr(app, 'windows', [])):
        if not getattr(win, 'visible', False):
            continue
        contains = getattr(win, 'contains', None)
        if not callable(contains) or not contains(mx, my):
            continue
        if win is source:
            return None
        if _supports_file_drop_target(win):
            return win
        return None
    return None


def _dispatch_drop(app, target, payload):
    """Apply one dropped payload to target window and dispatch returned action."""
    if target is None or not isinstance(payload, dict):
        return
    if payload.get('type') != 'file_path':
        return
    path = payload.get('path')
    if not path:
        return

    result = None
    open_path = getattr(target, 'open_path', None)
    accept_path = getattr(target, 'accept_dropped_path', None)
    if callable(open_path):
        result = open_path(path)
    elif callable(accept_path):
        result = accept_path(path)

    if result is not None:
        dispatcher = getattr(app, '_dispatch_window_result', None)
        if callable(dispatcher):
            dispatcher(result, target)


def _is_button1_click_event(bstate):
    """Return True for discrete button-1 click-like events (not motion reports)."""
    report_flag = getattr(curses, 'REPORT_MOUSE_POSITION', 0)
    if bstate & report_flag:
        return False
    return bool(
        bstate
        & (
            getattr(curses, 'BUTTON1_CLICKED', 0)
            | getattr(curses, 'BUTTON1_PRESSED', 0)
            | getattr(curses, 'BUTTON1_RELEASED', 0)
        )
    )


def _is_desktop_double_click(app, icon_idx, bstate):
    """Detect double-click for desktop icons with a time-based fallback."""
    if bstate & getattr(curses, 'BUTTON1_DOUBLE_CLICKED', 0):
        return True

    if not _is_button1_click_event(bstate):
        return False

    now = time.monotonic()
    last_idx = getattr(app, '_last_icon_click_idx', None)
    last_ts = float(getattr(app, '_last_icon_click_ts', 0.0) or 0.0)
    interval = float(getattr(app, 'double_click_interval', 0.35) or 0.35)
    is_double = (last_idx == icon_idx) and ((now - last_ts) <= interval)
    setattr(app, '_last_icon_click_idx', icon_idx)
    setattr(app, '_last_icon_click_ts', now)
    return is_double


def handle_file_drag_drop_mouse(app, mx, my, bstate):
    """Handle file drag-and-drop between windows (File Manager -> Notepad/Terminal)."""
    report_flag = getattr(curses, 'REPORT_MOUSE_POSITION', 0)
    pressed_flag = getattr(curses, 'BUTTON1_PRESSED', 0)
    move_drag = bool((bstate & report_flag) and (bstate & pressed_flag))
    stop_drag = bool(bstate & getattr(curses, 'BUTTON1_RELEASED', 0))
    if not stop_drag:
        inferred_stop = getattr(app, 'stop_drag_flags', 0) & ~pressed_flag & ~report_flag
        stop_drag = bool(bstate & inferred_stop)
    drag_payload = getattr(app, 'drag_payload', None)

    if drag_payload is not None:
        if stop_drag:
            target = _find_drop_target_window(app, mx, my)
            _dispatch_drop(app, target, drag_payload)
            _clear_drag_state(app)
            _clear_pending_file_drags(app)
            return True
        if move_drag:
            _set_drag_target(app, _find_drop_target_window(app, mx, my))
            return True
        return True

    if stop_drag:
        _clear_pending_file_drags(app)
        _set_drag_target(app, None)
        return False

    if not move_drag:
        return False

    for win in reversed(getattr(app, 'windows', [])):
        consumer = getattr(win, 'consume_pending_drag', None)
        if not callable(consumer):
            continue
        payload = consumer(mx, my, bstate)
        if payload is None:
            continue
        setattr(app, 'drag_payload', payload)
        setattr(app, 'drag_source_window', win)
        _set_drag_target(app, _find_drop_target_window(app, mx, my))
        return True
    return False


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
            if (bstate & curses.REPORT_MOUSE_POSITION) and (bstate & curses.BUTTON1_PRESSED) and hasattr(
                win, "handle_mouse_drag"
            ):
                drag_handler = getattr(win, "handle_mouse_drag", None)
                if callable(drag_handler):
                    drag_result = _invoke_mouse_handler(drag_handler, mx, my, bstate)
                    app._dispatch_window_result(drag_result, win)
                    return True

            if bstate & click_flags:
                app.set_active_window(win)
                for other_win in app.windows:
                    other_menu = getattr(other_win, "window_menu", None)
                    if other_win is win or not other_menu or not other_menu.active:
                        continue
                    other_menu.active = False
                result = _invoke_mouse_handler(win.handle_click, mx, my, bstate)
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
    icon_idx = app.get_icon_at(mx, my)
    if icon_idx >= 0 and _is_desktop_double_click(app, icon_idx, bstate):
        setattr(app, '_last_icon_click_idx', None)
        setattr(app, '_last_icon_click_ts', 0.0)
        app.execute_action(app.icons[icon_idx]['action'])
        return True

    if icon_idx >= 0 and _is_button1_click_event(bstate):
        app.selected_icon = icon_idx
        return True
    if icon_idx >= 0 and (bstate & getattr(curses, 'REPORT_MOUSE_POSITION', 0)):
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

    # Detect right-click (BUTTON3) and consult app-level handler if present.
    button3_flags = (
        getattr(curses, 'BUTTON3_PRESSED', 0)
        | getattr(curses, 'BUTTON3_CLICKED', 0)
        | getattr(curses, 'BUTTON3_RELEASED', 0)
    )
    if bstate & button3_flags:
        handler = getattr(app, '_handle_right_click', None)
        if callable(handler):
            try:
                handled = handler(mx, my, bstate)
            except Exception:
                handled = False
            if handled:
                return

    if app._handle_dialog_mouse(mx, my, bstate):
        return

    if handle_file_drag_drop_mouse(app, mx, my, bstate):
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

"""Main loop helpers for RetroTUI."""

import curses
import logging
import os
import time

from ..constants import (
    TERMINAL_INPUT_TIMEOUT_MS,
    TERMINAL_LIVE_INPUT_TIMEOUT_MS,
    TERMINAL_BACKGROUND_INPUT_TIMEOUT_MS,
    TERMINAL_ANIMATED_INPUT_TIMEOUT_MS,
    _CURSES_ERROR,
)

LOGGER = logging.getLogger(__name__)

_INPUT_TIMEOUT_APPLY_ERRORS = (
    AttributeError,
    OSError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)


def clamp_windows_to_terminal(app):
    """Keep window origins inside current terminal bounds."""
    new_h, new_w = app.stdscr.getmaxyx()
    for win in app.windows:
        win.x = max(0, min(win.x, new_w - min(win.w, new_w)))
        win.y = max(1, min(win.y, new_h - min(win.h, new_h) - 1))


def draw_frame(app):
    """Render a full frame before reading input."""
    frame_size = app.stdscr.getmaxyx()
    app._render_cycle_id = int(getattr(app, "_render_cycle_id", 0)) + 1
    app._frame_size = frame_size
    frame_h, frame_w = frame_size
    app.stdscr.erase()
    app.normalize_window_layers()
    app.draw_desktop(frame_size=frame_size)
    app.draw_icons(frame_size=frame_size)

    if not app.has_background_operation():
        for win in app.windows:
            if getattr(win, "visible", True):
                win.draw(app.stdscr, frame_size=frame_size)

    app.menu.draw_bar(app.stdscr, frame_w, frame_size=frame_size)
    app.menu.draw_dropdown(app.stdscr, frame_size=frame_size)
    app.draw_taskbar(frame_size=frame_size)
    app.draw_statusbar(frame_size=frame_size)

    if app.dialog:
        app.dialog.draw(app.stdscr, frame_size=frame_size)

    # Context menu drawn on top of menus but under modal dialogs.
    ctx = app.context_menu
    if ctx and ctx.is_open():
        ctx.draw(app.stdscr, frame_size=frame_size)

    # Toast notifications overlay (top-right corner).
    _notifications = getattr(app, '_notifications', None)
    if _notifications is not None and _notifications.has_visible:
        _notifications.draw(app.stdscr, frame_w, frame_h)

    app.stdscr.noutrefresh()
    curses.doupdate()


def read_input_key(stdscr):
    """Read one key from curses, returning None on timeout/no input."""
    try:
        return stdscr.get_wch()
    except KeyboardInterrupt:
        # Treat host Ctrl+C as an in-app control key to avoid abrupt exit.
        return "\x03"
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
            except (curses.error, ValueError, TypeError):
                return False
            try:
                _, mx, my, *_rest = event
                _bstate = _rest[-1] if _rest else 0
            except (TypeError, ValueError):
                return False
            action = ctx.handle_click(mx, my)
            if action:
                app.execute_action(action)
                return True
            # Click outside may close the menu; either way this was UI input.
            if ctx.is_open():
                return True
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
        except (curses.error, ValueError, TypeError):
            return False

    if isinstance(key, int) and key == curses.KEY_RESIZE:
        curses.update_lines_cols()
        clamp_windows_to_terminal(app)
        # Re-validate size non-fatally so a shrink doesn't silently leave
        # rows/cols out of range (``_validate_terminal_size`` raises, which
        # is right at startup but disruptive on resize).
        check = getattr(app, "_check_terminal_size_post_resize", None)
        too_small = bool(check()) if callable(check) else False
        if too_small:
            app._terminal_too_small = True
        else:
            app._terminal_too_small = False
        app._dirty = True
        return True

    app.handle_key(key)
    return True


def _has_live_terminals(app):
    """Return True if any window has an active PTY session producing output."""
    for w in app.windows:
        if not getattr(w, "visible", True):
            continue
        session = getattr(w, '_session', None)
        if session is not None and getattr(session, 'running', False):
            return True
    return False


def _has_animated_windows(app):
    """Return True if any visible window requests periodic redraws."""
    for w in app.windows:
        if not getattr(w, "visible", True):
            continue
        if getattr(w, "needs_redraw", False):
            return True
    return False


def _tick_visible_windows(app):
    """Run per-window update hooks outside rendering.

    Window ``tick`` methods may poll background state or collect pending output,
    but must not call curses drawing APIs.
    """
    changed = False
    for w in app.windows:
        if not getattr(w, "visible", True):
            continue
        tick = getattr(w, "tick", None)
        if not callable(tick):
            continue
        try:
            changed = bool(tick()) or changed
        except _INPUT_TIMEOUT_APPLY_ERRORS:
            LOGGER.debug("window tick failed", exc_info=True)
    return changed


def _select_input_timeout_ms(app, *, has_live=None, has_animated=None):
    """Return the target input timeout for the current runtime state.

    ``has_live``/``has_animated`` may be supplied by the caller when it
    has already computed them for the redraw decision; otherwise the
    helpers are invoked on demand. Reusing the cached values avoids two
    extra ``app.windows`` walks per loop iteration.
    """
    idle = int(getattr(app, "input_timeout_idle_ms", TERMINAL_INPUT_TIMEOUT_MS))
    timeout_ms = max(1, idle)

    if has_live is None:
        has_live = _has_live_terminals(app)
    if has_animated is None:
        has_animated = _has_animated_windows(app)

    if has_live:
        live = int(
            getattr(
                app,
                "input_timeout_live_terminal_ms",
                TERMINAL_LIVE_INPUT_TIMEOUT_MS,
            )
        )
        return max(1, live)

    if has_animated:
        anim = int(
            getattr(
                app,
                "input_timeout_animated_ms",
                TERMINAL_ANIMATED_INPUT_TIMEOUT_MS,
            )
        )
        return max(1, min(timeout_ms, anim))

    has_background_operation = getattr(app, "has_background_operation", None)
    if callable(has_background_operation) and bool(has_background_operation()):
        bg = int(
            getattr(
                app,
                "input_timeout_background_ms",
                TERMINAL_BACKGROUND_INPUT_TIMEOUT_MS,
            )
        )
        return max(1, min(timeout_ms, bg))

    return timeout_ms


def _apply_input_timeout(app, timeout_ms):
    """Apply stdscr timeout only when it changed."""
    if getattr(app, "_active_input_timeout_ms", None) == timeout_ms:
        return
    setter = getattr(app.stdscr, "timeout", None)
    if not callable(setter):
        return
    try:
        setter(timeout_ms)
    except _INPUT_TIMEOUT_APPLY_ERRORS:
        return
    app._active_input_timeout_ms = timeout_ms


def _profile_enabled():
    value = (
        os.environ.get("RETROTUI_PROFILE")
        or os.environ.get("RETROTUI_DEBUG")
        or ""
    ).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _coerce_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    return _coerce_float(os.environ.get(name), default)


def _ensure_runtime_metrics(app):
    metrics = getattr(app, "_runtime_metrics", None)
    if isinstance(metrics, dict):
        return metrics
    now = time.perf_counter()
    metrics = {
        "enabled": _profile_enabled(),
        "started_at": now,
        "last_report_at": now,
        "report_interval_s": _env_float("RETROTUI_PROFILE_INTERVAL", 5.0),
        "loops": 0,
        "redraws": 0,
        "dispatched_events": 0,
        "mouse_events": 0,
        "resize_events": 0,
        "key_events": 0,
        "empty_polls": 0,
        "draw_time_s": 0.0,
        "dispatch_time_s": 0.0,
        "input_wait_time_s": 0.0,
    }
    app._runtime_metrics = metrics
    return metrics


def _record_input_stats(metrics, key):
    if key is None:
        metrics["empty_polls"] += 1
        return
    if isinstance(key, int) and key == getattr(curses, "KEY_MOUSE", -1):
        metrics["mouse_events"] += 1
        return
    if isinstance(key, int) and key == getattr(curses, "KEY_RESIZE", -1):
        metrics["resize_events"] += 1
        return
    metrics["key_events"] += 1


def _emit_runtime_metrics(metrics, final=False):
    if not metrics.get("enabled"):
        return
    now = time.perf_counter()
    if not final:
        interval = max(0.1, _coerce_float(metrics.get("report_interval_s"), 5.0))
        if now - metrics.get("last_report_at", now) < interval:
            return
        metrics["last_report_at"] = now
    elapsed = max(1e-6, now - metrics.get("started_at", now))
    redraws = int(metrics.get("redraws", 0))
    events = int(metrics.get("dispatched_events", 0))
    loops = int(metrics.get("loops", 0))
    draw_time_s = float(metrics.get("draw_time_s", 0.0))
    dispatch_time_s = float(metrics.get("dispatch_time_s", 0.0))
    input_wait_s = float(metrics.get("input_wait_time_s", 0.0))
    redraw_ratio = redraws / max(1, loops)
    LOGGER.debug(
        "profile%s elapsed_s=%.3f loops=%d redraws=%d redraw_ratio=%.3f "
        "events=%d mouse=%d resize=%d key=%d empty_polls=%d draw_ms=%.2f "
        "dispatch_ms=%.2f input_wait_ms=%.2f",
        "_final" if final else "",
        elapsed,
        loops,
        redraws,
        redraw_ratio,
        events,
        int(metrics.get("mouse_events", 0)),
        int(metrics.get("resize_events", 0)),
        int(metrics.get("key_events", 0)),
        int(metrics.get("empty_polls", 0)),
        draw_time_s * 1000.0,
        dispatch_time_s * 1000.0,
        input_wait_s * 1000.0,
    )


def _refresh_idle_clock(app):
    """Refresh only the menu clock while idle, avoiding a full frame redraw."""
    if getattr(app, "_dirty", False):
        return False

    frame_size = getattr(app, "_frame_size", None)
    width = None
    if isinstance(frame_size, tuple) and len(frame_size) == 2:
        width = frame_size[1]

    menu = getattr(app, "menu", None)
    refresh_clock = getattr(menu, "refresh_clock", None)
    if callable(refresh_clock):
        try:
            updated = bool(refresh_clock(app.stdscr, width=width))
        except _INPUT_TIMEOUT_APPLY_ERRORS:
            return False

    if not updated:
        return False
    try:
        app.stdscr.noutrefresh()
        curses.doupdate()
    except _INPUT_TIMEOUT_APPLY_ERRORS:
        return False
    return True


def run_app_loop(app):
    """Run main draw/input loop with terminal cleanup on exit."""
    metrics = _ensure_runtime_metrics(app)
    install_handlers = getattr(app, "_install_runtime_signal_handlers", None)
    if callable(install_handlers):
        install_handlers()
    try:
        while app.running:
            try:
                metrics["loops"] += 1
                # Keep background progression deterministic: one poll per loop.
                app.poll_background_operation()
                # Expire toast notifications and force redraw while visible.
                _notif = getattr(app, '_notifications', None)
                if _notif is not None:
                    if _notif.tick():
                        app._dirty = True
                    if _notif.has_visible:
                        app._dirty = True
                if _tick_visible_windows(app):
                    app._dirty = True
                # Live terminals / animated windows drive both the redraw
                # cadence AND the input-timeout selection. Compute them
                # once and reuse to avoid walking ``app.windows`` twice.
                has_live = _has_live_terminals(app)
                has_animated = _has_animated_windows(app)
                if has_live or has_animated:
                    app._dirty = True
                if getattr(app, '_dirty', True):
                    draw_start = time.perf_counter()
                    draw_frame(app)
                    metrics["draw_time_s"] += time.perf_counter() - draw_start
                    metrics["redraws"] += 1
                    app._dirty = False
                _apply_input_timeout(app, _select_input_timeout_ms(app, has_live=has_live, has_animated=has_animated))
                input_start = time.perf_counter()
                key = read_input_key(app.stdscr)
                metrics["input_wait_time_s"] += time.perf_counter() - input_start
                if key is None:
                    consume_signal_key = getattr(app, "_consume_pending_signal_key", None)
                    if callable(consume_signal_key):
                        key = consume_signal_key()
                    else:
                        consume_sigint = getattr(app, "_consume_pending_sigint", None)
                        if callable(consume_sigint):
                            key = consume_sigint()
                if key is None and _refresh_idle_clock(app):
                    metrics["redraws"] += 1
                _record_input_stats(metrics, key)
                dispatch_start = time.perf_counter()
                if dispatch_input(app, key):
                    app._dirty = True
                    metrics["dispatched_events"] += 1
                metrics["dispatch_time_s"] += time.perf_counter() - dispatch_start
                _emit_runtime_metrics(metrics, final=False)
            except KeyboardInterrupt:
                # Fallback safety net for terminals that still surface Ctrl+C as host interrupt.
                app.handle_key("\x03")
                app._dirty = True
                metrics["dispatched_events"] += 1
                continue
            except Exception:
                # A buggy ``tick``/``handle_key``/``dispatch_input`` chain
                # used to escape the inner ``try`` and propagate into the
                # outer ``finally``, where ``app.cleanup()`` would mask the
                # original traceback if it also raised. Log and continue
                # instead so the user keeps the app running.
                LOGGER.exception("Unhandled exception in main loop iteration")
                app._dirty = True
                continue
    finally:
        _emit_runtime_metrics(metrics, final=True)
        app.cleanup()

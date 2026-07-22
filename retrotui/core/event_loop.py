"""Main loop helpers for RetroTUI."""

import curses
import inspect
import logging
import os
import time
from dataclasses import dataclass

from ..constants import (
    BOTTOM_BARS_HEIGHT,
    MENU_BAR_HEIGHT,
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

DEFAULT_EVENT_LOOP_FAILURE_LIMIT = 3
DEFAULT_EVENT_LOOP_ERROR_BACKOFF_S = 0.05


def _event_loop_failure_limit(app):
    """Return a bounded consecutive-failure threshold."""
    try:
        value = int(
            getattr(app, "event_loop_failure_limit", DEFAULT_EVENT_LOOP_FAILURE_LIMIT)
        )
    except (TypeError, ValueError):
        value = DEFAULT_EVENT_LOOP_FAILURE_LIMIT
    return max(1, value)


def _event_loop_backoff_s(app, failure_count):
    """Return a short bounded delay for a failing global loop iteration."""
    try:
        base = float(
            getattr(
                app,
                "event_loop_error_backoff_s",
                DEFAULT_EVENT_LOOP_ERROR_BACKOFF_S,
            )
        )
    except (TypeError, ValueError):
        base = DEFAULT_EVENT_LOOP_ERROR_BACKOFF_S
    return min(0.5, max(0.0, base) * max(1, int(failure_count)))


@dataclass
class _ComponentFailureState:
    """Runtime-owned failure state for one component hook."""

    component: object
    phase: str
    failure_count: int = 0
    first_error: BaseException | None = None
    disabled: bool = False


def _component_failure_states(app):
    """Return the app-owned component failure registry."""
    states = getattr(app, "_component_failure_states", None)
    if isinstance(states, dict):
        return states
    states = {}
    app._component_failure_states = states
    return states


def _component_failure_state(app, component, phase, *, create=True):
    states = _component_failure_states(app)
    key = (id(component), str(phase))
    state = states.get(key)
    if state is not None and state.component is component:
        return state
    if not create:
        return None
    state = _ComponentFailureState(component=component, phase=str(phase))
    states[key] = state
    return state


def _component_failure_snapshot(app, component, phase):
    """Return a diagnostics snapshot without exposing mutable registry state."""
    state = _component_failure_state(app, component, phase, create=False)
    if state is None:
        return {
            "failure_count": 0,
            "first_error": None,
            "disabled": False,
        }
    return {
        "failure_count": state.failure_count,
        "first_error": state.first_error,
        "disabled": state.disabled,
    }


def _mirror_component_failure(component, phase, state):
    """Best-effort compatibility mirror for old diagnostics and tests."""
    values = {
        f"_retrotui_{phase}_failure_count": state.failure_count,
        f"_retrotui_{phase}_first_error": state.first_error,
        f"_retrotui_{phase}_disabled": state.disabled,
    }
    for name, value in values.items():
        try:
            setattr(component, name, value)
        except (AttributeError, TypeError):
            continue


def _component_hook_disabled(app, component, phase):
    state = _component_failure_state(app, component, phase, create=False)
    return bool(state is not None and state.disabled)


def _prune_component_failure_states(app):
    """Drop registry entries for windows that are no longer registered."""
    states = getattr(app, "_component_failure_states", None)
    if not isinstance(states, dict) or not states:
        return
    try:
        live_windows = tuple(app.windows)
    except (AttributeError, TypeError):
        return
    live_by_id = {id(window): window for window in live_windows}
    for key, state in tuple(states.items()):
        if live_by_id.get(key[0]) is not state.component:
            states.pop(key, None)


def _reset_component_failure(app, component, phase):
    """Reset one component failure streak after a successful call."""
    state = _component_failure_state(app, component, phase, create=False)
    if state is None or state.disabled:
        return
    state.failure_count = 0
    state.first_error = None
    _mirror_component_failure(component, phase, state)


def _record_component_failure(app, component, phase, exc):
    """Record and eventually isolate a repeatedly failing window hook."""
    state = _component_failure_state(app, component, phase)
    state.failure_count += 1
    if state.first_error is None:
        state.first_error = exc
    _mirror_component_failure(component, phase, state)

    title = getattr(component, "title", component.__class__.__name__)
    if state.failure_count == 1:
        LOGGER.exception("window %s failed during %s", title, phase)
    else:
        LOGGER.warning(
            "window %s repeated %s failure (%d/%d): %s",
            title,
            phase,
            state.failure_count,
            _event_loop_failure_limit(app),
            exc,
        )

    if state.failure_count < _event_loop_failure_limit(app):
        return False

    state.disabled = True
    _mirror_component_failure(component, phase, state)
    # Existing scheduling/visibility fields are adjusted when writable, but
    # isolation no longer depends on adding private attributes to the plugin.
    try:
        if phase == "tick":
            setattr(component, "tick_when_hidden", False)
            setattr(component, "wants_periodic_tick", False)
        elif phase == "draw":
            setattr(component, "visible", False)
    except (AttributeError, TypeError):
        pass
    LOGGER.error("disabled window %s after repeated %s failures", title, phase)
    return True


def _method_accepts_frame_size(component, method_name):
    """Return whether a component method accepts the frame_size keyword."""
    cache_attr = f"_retrotui_{method_name}_accepts_frame_size"
    cached = getattr(component, cache_attr, None)
    if isinstance(cached, bool):
        return cached

    method = getattr(component, method_name)
    try:
        params = inspect.signature(method).parameters.values()
    except (TypeError, ValueError):
        accepts = False
    else:
        accepts = any(
            param.name == "frame_size"
            or param.kind == inspect.Parameter.VAR_KEYWORD
            for param in params
        )

    try:
        setattr(component, cache_attr, accepts)
    except (AttributeError, TypeError):
        pass
    return accepts


def _draw_component(component, stdscr, frame_size):
    """Draw a component while supporting legacy draw(stdscr) implementations."""
    draw = getattr(component, "draw", None)
    if not callable(draw):
        return
    if _method_accepts_frame_size(component, "draw"):
        draw(stdscr, frame_size=frame_size)
    else:
        draw(stdscr)


def _draw_window_component(app, component, stdscr, frame_size):
    """Draw one window and isolate it after repeated deterministic failures."""
    if (
        _component_hook_disabled(app, component, "draw")
        or getattr(component, "_retrotui_draw_disabled", False)
    ):
        return
    try:
        _draw_component(component, stdscr, frame_size)
    except Exception as exc:  # Window/plugin boundary: isolate third-party code.
        _record_component_failure(app, component, "draw", exc)
        return
    _reset_component_failure(app, component, "draw")


def clamp_windows_to_terminal(app):
    """Keep window origins inside current terminal bounds."""
    new_h, new_w = app.stdscr.getmaxyx()
    for win in app.windows:
        win.x = max(0, min(win.x, new_w - min(win.w, new_w)))
        win.y = max(
            MENU_BAR_HEIGHT,
            min(win.y, new_h - min(win.h, new_h) - BOTTOM_BARS_HEIGHT),
        )


def draw_frame(app):
    """Render a full frame before reading input."""
    _prune_component_failure_states(app)
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
                _draw_window_component(app, win, app.stdscr, frame_size)

    app.menu.draw_bar(app.stdscr, frame_w, frame_size=frame_size)
    app.menu.draw_dropdown(app.stdscr, frame_size=frame_size)
    app.draw_taskbar(frame_size=frame_size)
    app.draw_statusbar(frame_size=frame_size)

    if app.dialog:
        _draw_component(app.dialog, app.stdscr, frame_size)

    # Context menu drawn on top of menus but under modal dialogs.
    ctx = app.context_menu
    if ctx and ctx.is_open():
        _draw_component(ctx, app.stdscr, frame_size)

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
    """Return True if a visible or service-ticked window has a live PTY."""
    for w in app.windows:
        if _component_hook_disabled(app, w, "tick"):
            continue
        visible = getattr(w, "visible", True)
        if not visible and not getattr(w, "tick_when_hidden", False):
            continue
        session = getattr(w, '_session', None)
        if session is not None and getattr(session, 'running', False):
            return True
    return False


def _has_periodic_windows(app):
    """Return True if any visible window requests periodic scheduling."""
    for window in app.windows:
        if _component_hook_disabled(app, window, "tick"):
            continue
        if not getattr(window, "visible", True):
            continue
        if bool(getattr(window, "wants_periodic_tick", False)):
            return True
    return False


def _visible_notification_signature(notifications):
    """Return the identity of the currently rendered toast stack."""
    try:
        toasts = tuple(notifications.visible_toasts)
    except (AttributeError, TypeError):
        return ()
    return tuple(
        (id(toast), getattr(toast, "created_at", None))
        for toast in toasts
    )


def _tick_notifications(app):
    """Advance toast expiry and invalidate only on visible changes."""
    previous = getattr(app, "_notification_visible_signature", ())
    notifications = getattr(app, "_notifications", None)
    if notifications is None:
        if previous:
            app._notification_visible_signature = ()
            return True
        return False

    tick = getattr(notifications, "tick", None)
    expired = bool(tick()) if callable(tick) else False
    signature = _visible_notification_signature(notifications)
    app._notification_visible_signature = signature
    return expired or signature != previous


def _tick_and_probe_windows(app):
    """Run update hooks and collect the public runtime scheduling signals.

    ``tick()`` is the only per-window redraw signal. A True return means
    visible state changed. ``wants_periodic_tick`` only selects a shorter
    polling cadence, while ``tick_when_hidden`` allows service progression.
    """
    _prune_component_failure_states(app)
    changed = False
    has_live = False
    has_periodic = False
    for window in app.windows:
        visible = getattr(window, "visible", True)
        tick_when_hidden = bool(getattr(window, "tick_when_hidden", False))
        if not visible and not tick_when_hidden:
            continue

        tick = getattr(window, "tick", None)
        if (
            callable(tick)
            and not _component_hook_disabled(app, window, "tick")
            and not getattr(window, "_retrotui_tick_disabled", False)
        ):
            try:
                tick_changed = bool(tick())
            except Exception as exc:  # Window/plugin boundary.
                _record_component_failure(app, window, "tick", exc)
            else:
                _reset_component_failure(app, window, "tick")
                if visible:
                    changed = tick_changed or changed

        if not has_live:
            session = getattr(window, "_session", None)
            if session is not None and getattr(session, "running", False):
                has_live = True
        if visible and not has_periodic:
            has_periodic = bool(
                getattr(window, "wants_periodic_tick", False)
            )
    return changed, has_live, has_periodic


def _tick_visible_windows(app):
    """Run per-window update hooks outside rendering.

    Window ``tick`` methods may poll background state or collect pending output,
    but must not call curses drawing APIs.
    """
    _prune_component_failure_states(app)
    changed = False
    for w in app.windows:
        visible = getattr(w, "visible", True)
        if not visible and not getattr(w, "tick_when_hidden", False):
            continue
        tick = getattr(w, "tick", None)
        if (
            not callable(tick)
            or _component_hook_disabled(app, w, "tick")
            or getattr(w, "_retrotui_tick_disabled", False)
        ):
            continue
        try:
            tick_changed = bool(tick())
        except Exception as exc:  # Window/plugin boundary.
            _record_component_failure(app, w, "tick", exc)
        else:
            _reset_component_failure(app, w, "tick")
            if visible:
                changed = tick_changed or changed
    return changed


def _select_input_timeout_ms(app, *, has_live=None, has_periodic=None):
    """Return the target input timeout for the current runtime state.

    Live services and periodic windows affect polling cadence only. Redraws
    remain controlled by ``tick()`` returns and app-level invalidation.
    """
    idle = int(getattr(app, "input_timeout_idle_ms", TERMINAL_INPUT_TIMEOUT_MS))
    timeout_ms = max(1, idle)

    if has_live is None:
        has_live = _has_live_terminals(app)
    if has_periodic is None:
        has_periodic = _has_periodic_windows(app)

    if has_live:
        live = int(
            getattr(
                app,
                "input_timeout_live_terminal_ms",
                TERMINAL_LIVE_INPUT_TIMEOUT_MS,
            )
        )
        return max(1, live)

    if has_periodic:
        periodic = int(
            getattr(
                app,
                "input_timeout_periodic_ms",
                TERMINAL_ANIMATED_INPUT_TIMEOUT_MS,
            )
        )
        return max(1, min(timeout_ms, periodic))

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
    updated = False
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
    """Run the main loop with bounded recovery and guaranteed cleanup."""
    metrics = _ensure_runtime_metrics(app)
    install_handlers = getattr(app, "_install_runtime_signal_handlers", None)
    if callable(install_handlers):
        install_handlers()

    consecutive_errors = 0
    first_error = None
    first_error_phase = None
    phase = "startup"
    app._event_loop_first_error = None
    app._event_loop_first_error_phase = None
    cleanup_ok = True

    try:
        while app.running:
            try:
                metrics["loops"] += 1
                phase = "background"
                app.poll_background_operation()

                if _tick_notifications(app):
                    app._dirty = True

                phase = "tick"
                _tick_changed, has_live, has_periodic = _tick_and_probe_windows(app)
                if _tick_changed:
                    app._dirty = True

                phase = "render"
                if getattr(app, "_dirty", True):
                    draw_start = time.perf_counter()
                    draw_frame(app)
                    metrics["draw_time_s"] += time.perf_counter() - draw_start
                    metrics["redraws"] += 1
                    app._dirty = False

                phase = "input"
                _apply_input_timeout(
                    app,
                    _select_input_timeout_ms(
                        app, has_live=has_live, has_periodic=has_periodic
                    ),
                )
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

                phase = "dispatch"
                dispatch_start = time.perf_counter()
                if dispatch_input(app, key):
                    app._dirty = True
                    metrics["dispatched_events"] += 1
                metrics["dispatch_time_s"] += time.perf_counter() - dispatch_start
                _emit_runtime_metrics(metrics, final=False)

                # A complete iteration breaks the global failure streak.
                consecutive_errors = 0
                first_error = None
                first_error_phase = None
                app._event_loop_first_error = None
                app._event_loop_first_error_phase = None
            except KeyboardInterrupt:
                app.handle_key("\x03")
                app._dirty = True
                metrics["dispatched_events"] += 1
                consecutive_errors = 0
                first_error = None
                first_error_phase = None
                continue
            except Exception as exc:
                consecutive_errors += 1
                if first_error is None:
                    first_error = exc
                    first_error_phase = phase
                    app._event_loop_first_error = exc
                    app._event_loop_first_error_phase = phase
                    LOGGER.exception(
                        "Unhandled exception in main loop phase %s", phase
                    )
                else:
                    LOGGER.error(
                        "Repeated main-loop failure in phase %s (%d/%d): %s",
                        phase,
                        consecutive_errors,
                        _event_loop_failure_limit(app),
                        exc,
                    )

                if consecutive_errors >= _event_loop_failure_limit(app):
                    app.running = False
                    app._event_loop_abort_reason = (
                        f"{first_error_phase} failed {consecutive_errors} "
                        f"consecutive times: {first_error}"
                    )
                    LOGGER.critical(
                        "Event loop circuit breaker opened: %s",
                        app._event_loop_abort_reason,
                        exc_info=(
                            type(first_error),
                            first_error,
                            first_error.__traceback__,
                        ),
                    )
                    break

                app._dirty = True
                delay = _event_loop_backoff_s(app, consecutive_errors)
                if delay > 0:
                    time.sleep(delay)
                continue
    finally:
        _emit_runtime_metrics(metrics, final=True)
        try:
            cleanup_ok = app.cleanup() is not False
        except Exception:
            cleanup_ok = False
            if first_error is None:
                raise
            LOGGER.exception(
                "cleanup failed after event-loop error; preserving original cause"
            )
    return cleanup_ok

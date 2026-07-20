#!/usr/bin/env python3
"""Apply the focused event-loop circuit-breaker patch."""
from pathlib import Path


PATH = Path("retrotui/core/event_loop.py")
text = PATH.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match, found {count}: {old[:120]!r}")
    text = text.replace(old, new, 1)


replace_once(
    '''_INPUT_TIMEOUT_APPLY_ERRORS = (
    AttributeError,
    OSError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)
''',
    '''_INPUT_TIMEOUT_APPLY_ERRORS = (
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


def _component_failure_attr(phase, suffix):
    return f"_retrotui_{phase}_{suffix}"


def _reset_component_failure(component, phase):
    """Reset one component failure streak after a successful call."""
    try:
        setattr(component, _component_failure_attr(phase, "failure_count"), 0)
        setattr(component, _component_failure_attr(phase, "first_error"), None)
    except (AttributeError, TypeError):
        pass


def _record_component_failure(app, component, phase, exc):
    """Record and eventually isolate a repeatedly failing window hook."""
    count_attr = _component_failure_attr(phase, "failure_count")
    first_attr = _component_failure_attr(phase, "first_error")
    disabled_attr = _component_failure_attr(phase, "disabled")
    count = int(getattr(component, count_attr, 0) or 0) + 1
    try:
        setattr(component, count_attr, count)
        if getattr(component, first_attr, None) is None:
            setattr(component, first_attr, exc)
    except (AttributeError, TypeError):
        pass

    title = getattr(component, "title", component.__class__.__name__)
    if count == 1:
        LOGGER.exception("window %s failed during %s", title, phase)
    else:
        LOGGER.warning(
            "window %s repeated %s failure (%d/%d): %s",
            title,
            phase,
            count,
            _event_loop_failure_limit(app),
            exc,
        )

    if count < _event_loop_failure_limit(app):
        return False

    try:
        setattr(component, disabled_attr, True)
        if phase == "tick":
            setattr(component, "tick_when_hidden", False)
            setattr(component, "wants_periodic_tick", False)
        elif phase == "draw":
            setattr(component, "visible", False)
    except (AttributeError, TypeError):
        pass
    LOGGER.error("disabled window %s after repeated %s failures", title, phase)
    return True
''',
)

replace_once(
    '''def _draw_component(component, stdscr, frame_size):
    """Draw a component while supporting legacy draw(stdscr) implementations."""
    draw = getattr(component, "draw", None)
    if not callable(draw):
        return
    if _method_accepts_frame_size(component, "draw"):
        draw(stdscr, frame_size=frame_size)
    else:
        draw(stdscr)
''',
    '''def _draw_component(component, stdscr, frame_size):
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
    if getattr(component, "_retrotui_draw_disabled", False):
        return
    try:
        _draw_component(component, stdscr, frame_size)
    except Exception as exc:  # Window/plugin boundary: isolate third-party code.
        _record_component_failure(app, component, "draw", exc)
        return
    _reset_component_failure(component, "draw")
''',
)

replace_once(
    '                _draw_component(win, app.stdscr, frame_size)\n',
    '                _draw_window_component(app, win, app.stdscr, frame_size)\n',
)

replace_once(
    '''        tick = getattr(window, "tick", None)
        if callable(tick):
            try:
                tick_changed = bool(tick())
                if visible:
                    changed = tick_changed or changed
            except _INPUT_TIMEOUT_APPLY_ERRORS:
                LOGGER.debug("window tick failed", exc_info=True)
''',
    '''        tick = getattr(window, "tick", None)
        if callable(tick) and not getattr(window, "_retrotui_tick_disabled", False):
            try:
                tick_changed = bool(tick())
            except Exception as exc:  # Window/plugin boundary.
                _record_component_failure(app, window, "tick", exc)
            else:
                _reset_component_failure(window, "tick")
                if visible:
                    changed = tick_changed or changed
''',
)

replace_once(
    '''        tick = getattr(w, "tick", None)
        if not callable(tick):
            continue
        try:
            tick_changed = bool(tick())
            if visible:
                changed = tick_changed or changed
        except _INPUT_TIMEOUT_APPLY_ERRORS:
            LOGGER.debug("window tick failed", exc_info=True)
''',
    '''        tick = getattr(w, "tick", None)
        if not callable(tick) or getattr(w, "_retrotui_tick_disabled", False):
            continue
        try:
            tick_changed = bool(tick())
        except Exception as exc:  # Window/plugin boundary.
            _record_component_failure(app, w, "tick", exc)
        else:
            _reset_component_failure(w, "tick")
            if visible:
                changed = tick_changed or changed
''',
)

marker = "\ndef run_app_loop(app):\n"
start = text.find(marker)
if start < 0:
    raise SystemExit("run_app_loop marker not found")
text = text[: start + 1] + '''def run_app_loop(app):
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

    try:
        while app.running:
            try:
                metrics["loops"] += 1
                phase = "background"
                app.poll_background_operation()

                _notif = getattr(app, "_notifications", None)
                if _notif is not None:
                    if _notif.tick():
                        app._dirty = True
                    if _notif.has_visible:
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
                app.handle_key("\\x03")
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
            app.cleanup()
        except Exception:
            if first_error is None:
                raise
            LOGGER.exception(
                "cleanup failed after event-loop error; preserving original cause"
            )
'''

PATH.write_text(text, encoding="utf-8")

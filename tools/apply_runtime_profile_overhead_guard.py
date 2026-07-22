"""Remove runtime timing overhead when profiling is disabled.

Temporary one-shot helper; deleted before merge.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8", newline="\n")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:90]!r}")
    write(path, content.replace(old, new, 1))


replace_once(
    "retrotui/core/event_loop.py",
    '''    now = time.perf_counter()
    metrics = {
        "enabled": _profile_enabled(),
''',
    '''    enabled = _profile_enabled()
    now = time.perf_counter() if enabled else 0.0
    metrics = {
        "enabled": enabled,
''',
)
replace_once(
    "retrotui/core/event_loop.py",
    '''    cleanup_ok = True

    try:
''',
    '''    cleanup_ok = True
    profiling = bool(metrics.get("enabled"))

    try:
''',
)
replace_once(
    "retrotui/core/event_loop.py",
    '''                phase = "background"
                background_start = time.perf_counter()
                app.poll_background_operation()
                metrics["background_time_s"] += (
                    time.perf_counter() - background_start
                )
''',
    '''                phase = "background"
                if profiling:
                    background_start = time.perf_counter()
                    app.poll_background_operation()
                    metrics["background_time_s"] += (
                        time.perf_counter() - background_start
                    )
                else:
                    app.poll_background_operation()
''',
)
replace_once(
    "retrotui/core/event_loop.py",
    '''                phase = "tick"
                tick_start = time.perf_counter()
                _tick_changed, has_live, has_periodic = _tick_and_probe_windows(app)
                tick_elapsed = time.perf_counter() - tick_start
                metrics["tick_time_s"] += tick_elapsed
                metrics["max_tick_time_s"] = max(
                    float(metrics.get("max_tick_time_s", 0.0)),
                    tick_elapsed,
                )
''',
    '''                phase = "tick"
                if profiling:
                    tick_start = time.perf_counter()
                    _tick_changed, has_live, has_periodic = _tick_and_probe_windows(app)
                    tick_elapsed = time.perf_counter() - tick_start
                    metrics["tick_time_s"] += tick_elapsed
                    metrics["max_tick_time_s"] = max(
                        float(metrics.get("max_tick_time_s", 0.0)),
                        tick_elapsed,
                    )
                else:
                    _tick_changed, has_live, has_periodic = _tick_and_probe_windows(app)
''',
)
replace_once(
    "retrotui/core/event_loop.py",
    '''                if getattr(app, "_dirty", True):
                    draw_start = time.perf_counter()
                    draw_frame(app)
                    draw_elapsed = time.perf_counter() - draw_start
                    metrics["draw_time_s"] += draw_elapsed
                    metrics["max_draw_time_s"] = max(
                        float(metrics.get("max_draw_time_s", 0.0)),
                        draw_elapsed,
                    )
                    metrics["redraws"] += 1
                    app._dirty = False
''',
    '''                if getattr(app, "_dirty", True):
                    if profiling:
                        draw_start = time.perf_counter()
                        draw_frame(app)
                        draw_elapsed = time.perf_counter() - draw_start
                        metrics["draw_time_s"] += draw_elapsed
                        metrics["max_draw_time_s"] = max(
                            float(metrics.get("max_draw_time_s", 0.0)),
                            draw_elapsed,
                        )
                    else:
                        draw_frame(app)
                    metrics["redraws"] += 1
                    app._dirty = False
''',
)
replace_once(
    "retrotui/core/event_loop.py",
    '''                input_start = time.perf_counter()
                key = read_input_key(app.stdscr)
                metrics["input_wait_time_s"] += time.perf_counter() - input_start
''',
    '''                if profiling:
                    input_start = time.perf_counter()
                    key = read_input_key(app.stdscr)
                    metrics["input_wait_time_s"] += (
                        time.perf_counter() - input_start
                    )
                else:
                    key = read_input_key(app.stdscr)
''',
)
replace_once(
    "retrotui/core/event_loop.py",
    '''                phase = "dispatch"
                dispatch_start = time.perf_counter()
                if dispatch_input(app, key):
                    app._dirty = True
                    metrics["dispatched_events"] += 1
                    metrics["input_invalidations"] += 1
                dispatch_elapsed = time.perf_counter() - dispatch_start
                metrics["dispatch_time_s"] += dispatch_elapsed
                metrics["max_dispatch_time_s"] = max(
                    float(metrics.get("max_dispatch_time_s", 0.0)),
                    dispatch_elapsed,
                )
''',
    '''                phase = "dispatch"
                if profiling:
                    dispatch_start = time.perf_counter()
                if dispatch_input(app, key):
                    app._dirty = True
                    metrics["dispatched_events"] += 1
                    metrics["input_invalidations"] += 1
                if profiling:
                    dispatch_elapsed = time.perf_counter() - dispatch_start
                    metrics["dispatch_time_s"] += dispatch_elapsed
                    metrics["max_dispatch_time_s"] = max(
                        float(metrics.get("max_dispatch_time_s", 0.0)),
                        dispatch_elapsed,
                    )
''',
)
replace_once(
    "tests/test_event_loop.py",
    '''    def test_runtime_metrics_use_default_for_invalid_profile_interval(self):
''',
    '''    def test_disabled_profiler_avoids_startup_clock_sampling(self):
        app = self._make_app()
        with (
            mock.patch.dict(self.event_loop.os.environ, {}, clear=True),
            mock.patch.object(self.event_loop.time, "perf_counter") as timer,
        ):
            metrics = self.event_loop._ensure_runtime_metrics(app)

        self.assertFalse(metrics["enabled"])
        timer.assert_not_called()

    def test_disabled_profiler_does_not_time_hot_loop_phases(self):
        app = self._make_app()
        app._runtime_metrics = self.event_loop._ensure_runtime_metrics(app)
        app._runtime_metrics["enabled"] = False

        def _dispatch_once(target, key):
            target.running = False
            return False

        with (
            mock.patch.object(self.event_loop, "draw_frame"),
            mock.patch.object(self.event_loop, "read_input_key", return_value=None),
            mock.patch.object(
                self.event_loop,
                "dispatch_input",
                side_effect=_dispatch_once,
            ),
            mock.patch.object(self.event_loop.time, "perf_counter") as timer,
        ):
            self.event_loop.run_app_loop(app)

        timer.assert_not_called()

    def test_runtime_metrics_use_default_for_invalid_profile_interval(self):
''',
)

print("Applied zero-overhead profiling guard.")

"""Apply the focused runtime performance and profiling hardening cut.

This temporary helper is removed before the final pull request is merged.
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
        raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:80]!r}")
    write(path, content.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Process Manager: avoid work on rate-limited ticks, cache command metadata,
# keep CPU samples identity-scoped, and sort in memory without rescanning /proc.
# ---------------------------------------------------------------------------
replace_once(
    "retrotui/apps/process_manager.py",
    "    REFRESH_INTERVAL_SECONDS = 1.0\n    KEY_F5 = getattr(curses, \"KEY_F5\", -1)\n",
    "    REFRESH_INTERVAL_SECONDS = 1.0\n"
    "    COMMAND_CACHE_TTL_SECONDS = 5.0\n"
    "    KEY_F5 = getattr(curses, \"KEY_F5\", -1)\n",
)
replace_once(
    "retrotui/apps/process_manager.py",
    "        self._prev_total_jiffies = None\n        self._prev_proc_ticks = {}\n\n        self.summary_uptime = \"-\"\n",
    "        self._prev_total_jiffies = None\n"
    "        self._prev_proc_ticks = {}\n"
    "        self._command_cache = {}\n"
    "        self._last_render_signature = None\n\n"
    "        self.summary_uptime = \"-\"\n",
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''    @staticmethod
    def _read_process_start_time_ticks(pid):
        """Return Linux process start ticks, or ``None`` when it is gone."""
''',
    '''    @staticmethod
    def _process_identity(pid, start_time_ticks):
        """Return the stable identity used by samples and metadata caches."""
        return (int(pid), max(0, int(start_time_ticks or 0)))

    def _command_for_process(self, pid, start_time_ticks, sampled_at):
        """Read command metadata at most once per identity/TTL window."""
        identity = self._process_identity(pid, start_time_ticks)
        cached = self._command_cache.get(identity)
        if cached is not None:
            command, expires_at = cached
            if sampled_at < expires_at:
                return command

        command = self._read_command(pid)
        self._command_cache[identity] = (
            command,
            sampled_at + self.COMMAND_CACHE_TTL_SECONDS,
        )
        return command

    def _render_signature(self):
        """Return the lightweight visible-state signature for invalidation."""
        return (
            tuple(
                (
                    row.pid,
                    row.start_time_ticks,
                    row.cpu_percent,
                    row.mem_percent,
                    row.command,
                )
                for row in self.rows
            ),
            self.summary_uptime,
            self.summary_load,
            self.summary_mem,
            self._error_message,
        )

    @staticmethod
    def _read_process_start_time_ticks(pid):
        """Return Linux process start ticks, or ``None`` when it is gone."""
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    "    def _read_process_row(self, pid, total_delta, mem_total_kb):\n"
    "        stat_path = f\"/proc/{pid}/stat\"\n"
    "        statm_path = f\"/proc/{pid}/statm\"\n\n",
    "    def _read_process_row(\n"
    "        self, pid, total_delta, mem_total_kb, *, sampled_at=None\n"
    "    ):\n"
    "        stat_path = f\"/proc/{pid}/stat\"\n"
    "        statm_path = f\"/proc/{pid}/statm\"\n"
    "        if sampled_at is None:\n"
    "            sampled_at = time.monotonic()\n\n",
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''        prev_ticks = self._prev_proc_ticks.get(pid)
        if prev_ticks is None or total_delta <= 0:
            cpu_percent = 0.0
        else:
            proc_delta = max(0, total_ticks - prev_ticks)
            cpu_percent = (proc_delta / max(1, total_delta)) * 100.0 * self._cpu_count

        command = self._read_command(pid)
''',
    '''        identity = self._process_identity(pid, start_time_ticks)
        prev_ticks = self._prev_proc_ticks.get(identity)
        if prev_ticks is None:
            # Compatibility with tests and callers that seeded the legacy PID key.
            prev_ticks = self._prev_proc_ticks.get(pid)
        if prev_ticks is None or total_delta <= 0:
            cpu_percent = 0.0
        else:
            proc_delta = max(0, total_ticks - prev_ticks)
            cpu_percent = (proc_delta / max(1, total_delta)) * 100.0 * self._cpu_count

        command = self._command_for_process(pid, start_time_ticks, sampled_at)
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''        now = time.monotonic()
        if not force and (now - self._last_refresh) < self.REFRESH_INTERVAL_SECONDS:
            return
        self._last_refresh = now
''',
    '''        now = time.monotonic()
        if not force and (now - self._last_refresh) < self.REFRESH_INTERVAL_SECONDS:
            return False
        self._last_refresh = now
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''        rows = []
        new_ticks = {}
        self._error_message = None
''',
    '''        rows = []
        new_ticks = {}
        live_identities = set()
        self._error_message = None
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''        for name in proc_dirs:
            pid = int(name)
            row = self._read_process_row(pid, total_delta, mem_total_kb)
            if row is None:
                continue
            rows.append(row)
            new_ticks[pid] = row.total_ticks
''',
    '''        for name in proc_dirs:
            pid = int(name)
            row = self._read_process_row(
                pid,
                total_delta,
                mem_total_kb,
                sampled_at=now,
            )
            if row is None:
                continue
            identity = self._process_identity(row.pid, row.start_time_ticks)
            rows.append(row)
            new_ticks[identity] = row.total_ticks
            live_identities.add(identity)
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''        self._prev_total_jiffies = total_jiffies
        self._prev_proc_ticks = new_ticks

        if self.rows:
''',
    '''        self._prev_total_jiffies = total_jiffies
        self._prev_proc_ticks = new_ticks
        self._command_cache = {
            identity: cached
            for identity, cached in self._command_cache.items()
            if identity in live_identities
        }

        if self.rows:
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''        self.summary_uptime = self._format_uptime(self._read_uptime_seconds())
        self.summary_load = self._read_load_average()
        self.summary_mem = f"{used_kb // 1024}MB/{mem_total_kb // 1024}MB"

    def _selected_row(self):
''',
    '''        self.summary_uptime = self._format_uptime(self._read_uptime_seconds())
        self.summary_load = self._read_load_average()
        self.summary_mem = f"{used_kb // 1024}MB/{mem_total_kb // 1024}MB"

        signature = self._render_signature()
        changed = signature != self._last_render_signature
        self._last_render_signature = signature
        return changed

    def _selected_row(self):
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''    def _set_sort(self, key):
        if self.sort_key == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key = key
            self.sort_reverse = key not in ("pid", "cmd")
        self.refresh_processes(force=True)
''',
    '''    def _set_sort(self, key):
        selected = self._selected_row()
        selected_identity = (
            self._process_identity(selected.pid, selected.start_time_ticks)
            if selected is not None
            else None
        )

        if self.sort_key == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key = key
            self.sort_reverse = key not in ("pid", "cmd")

        self._sort_rows()
        if selected_identity is not None:
            for index, row in enumerate(self.rows):
                if self._process_identity(row.pid, row.start_time_ticks) == selected_identity:
                    self.selected_index = index
                    break
        self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))
        self._ensure_selection_visible()
        self._last_render_signature = self._render_signature()
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''    def tick(self):
        """Refresh process table outside the render path."""
        before = (
            tuple(self.rows),
            self.summary_uptime,
            self.summary_load,
            self.summary_mem,
            self._error_message,
        )
        self.refresh_processes(force=False)
        after = (
            tuple(self.rows),
            self.summary_uptime,
            self.summary_load,
            self.summary_mem,
            self._error_message,
        )
        return after != before
''',
    '''    def tick(self):
        """Refresh process data only when its sampling interval has elapsed."""
        return bool(self.refresh_processes(force=False))
''',
)

# ---------------------------------------------------------------------------
# Event loop: remove a duplicate dead tick helper and make profiling accurately
# distinguish full redraws from partial clock refreshes and invalidation causes.
# ---------------------------------------------------------------------------
replace_once(
    "retrotui/core/event_loop.py",
    '''def _tick_visible_windows(app):
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


''',
    "",
)
replace_once(
    "retrotui/core/event_loop.py",
    '''        "empty_polls": 0,
        "draw_time_s": 0.0,
        "dispatch_time_s": 0.0,
        "input_wait_time_s": 0.0,
''',
    '''        "empty_polls": 0,
        "clock_refreshes": 0,
        "notification_invalidations": 0,
        "tick_invalidations": 0,
        "input_invalidations": 0,
        "background_time_s": 0.0,
        "tick_time_s": 0.0,
        "draw_time_s": 0.0,
        "dispatch_time_s": 0.0,
        "input_wait_time_s": 0.0,
        "max_tick_time_s": 0.0,
        "max_draw_time_s": 0.0,
        "max_dispatch_time_s": 0.0,
''',
)
start = read("retrotui/core/event_loop.py").index("def _emit_runtime_metrics(metrics, final=False):\n")
end = read("retrotui/core/event_loop.py").index("\ndef _refresh_idle_clock(app):\n", start)
content = read("retrotui/core/event_loop.py")
new_emit = '''def _emit_runtime_metrics(metrics, final=False):
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
    redraw_ratio = redraws / max(1, loops)
    LOGGER.debug(
        "profile%s elapsed_s=%.3f loops=%d redraws=%d clock_refreshes=%d "
        "redraw_ratio=%.3f events=%d mouse=%d resize=%d key=%d empty_polls=%d "
        "invalidations_notification=%d invalidations_tick=%d invalidations_input=%d "
        "background_ms=%.2f tick_ms=%.2f draw_ms=%.2f dispatch_ms=%.2f "
        "input_wait_ms=%.2f max_tick_ms=%.2f max_draw_ms=%.2f "
        "max_dispatch_ms=%.2f",
        "_final" if final else "",
        elapsed,
        loops,
        redraws,
        int(metrics.get("clock_refreshes", 0)),
        redraw_ratio,
        events,
        int(metrics.get("mouse_events", 0)),
        int(metrics.get("resize_events", 0)),
        int(metrics.get("key_events", 0)),
        int(metrics.get("empty_polls", 0)),
        int(metrics.get("notification_invalidations", 0)),
        int(metrics.get("tick_invalidations", 0)),
        int(metrics.get("input_invalidations", 0)),
        float(metrics.get("background_time_s", 0.0)) * 1000.0,
        float(metrics.get("tick_time_s", 0.0)) * 1000.0,
        float(metrics.get("draw_time_s", 0.0)) * 1000.0,
        float(metrics.get("dispatch_time_s", 0.0)) * 1000.0,
        float(metrics.get("input_wait_time_s", 0.0)) * 1000.0,
        float(metrics.get("max_tick_time_s", 0.0)) * 1000.0,
        float(metrics.get("max_draw_time_s", 0.0)) * 1000.0,
        float(metrics.get("max_dispatch_time_s", 0.0)) * 1000.0,
    )
'''
write("retrotui/core/event_loop.py", content[:start] + new_emit + content[end:])
replace_once(
    "retrotui/core/event_loop.py",
    '''                phase = "background"
                app.poll_background_operation()

                if _tick_notifications(app):
                    app._dirty = True

                phase = "tick"
                _tick_changed, has_live, has_periodic = _tick_and_probe_windows(app)
                if _tick_changed:
                    app._dirty = True
''',
    '''                phase = "background"
                background_start = time.perf_counter()
                app.poll_background_operation()
                metrics["background_time_s"] += (
                    time.perf_counter() - background_start
                )

                if _tick_notifications(app):
                    metrics["notification_invalidations"] += 1
                    app._dirty = True

                phase = "tick"
                tick_start = time.perf_counter()
                _tick_changed, has_live, has_periodic = _tick_and_probe_windows(app)
                tick_elapsed = time.perf_counter() - tick_start
                metrics["tick_time_s"] += tick_elapsed
                metrics["max_tick_time_s"] = max(
                    float(metrics.get("max_tick_time_s", 0.0)),
                    tick_elapsed,
                )
                if _tick_changed:
                    metrics["tick_invalidations"] += 1
                    app._dirty = True
''',
)
replace_once(
    "retrotui/core/event_loop.py",
    '''                    draw_frame(app)
                    metrics["draw_time_s"] += time.perf_counter() - draw_start
                    metrics["redraws"] += 1
''',
    '''                    draw_frame(app)
                    draw_elapsed = time.perf_counter() - draw_start
                    metrics["draw_time_s"] += draw_elapsed
                    metrics["max_draw_time_s"] = max(
                        float(metrics.get("max_draw_time_s", 0.0)),
                        draw_elapsed,
                    )
                    metrics["redraws"] += 1
''',
)
replace_once(
    "retrotui/core/event_loop.py",
    '''                if key is None and _refresh_idle_clock(app):
                    metrics["redraws"] += 1
''',
    '''                if key is None and _refresh_idle_clock(app):
                    metrics["clock_refreshes"] += 1
''',
)
replace_once(
    "retrotui/core/event_loop.py",
    '''                dispatch_start = time.perf_counter()
                if dispatch_input(app, key):
                    app._dirty = True
                    metrics["dispatched_events"] += 1
                metrics["dispatch_time_s"] += time.perf_counter() - dispatch_start
''',
    '''                dispatch_start = time.perf_counter()
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
)
replace_once(
    "retrotui/core/event_loop.py",
    '''                app.handle_key("\\x03")
                app._dirty = True
                metrics["dispatched_events"] += 1
''',
    '''                app.handle_key("\\x03")
                app._dirty = True
                metrics["dispatched_events"] += 1
                metrics["input_invalidations"] += 1
''',
)

# ---------------------------------------------------------------------------
# Profile parser/extractor: expose the new measurements as stable fields.
# ---------------------------------------------------------------------------
replace_once(
    "retrotui/core/profile_metrics.py",
    '''    input_wait_ms: float | None
    loops: int | None
    redraws: int | None
    events: int | None
''',
    '''    input_wait_ms: float | None
    background_ms: float | None
    tick_ms: float | None
    max_tick_ms: float | None
    max_draw_ms: float | None
    max_dispatch_ms: float | None
    loops: int | None
    redraws: int | None
    clock_refreshes: int | None
    events: int | None
    notification_invalidations: int | None
    tick_invalidations: int | None
    input_invalidations: int | None
''',
)
replace_once(
    "retrotui/core/profile_metrics.py",
    '''            input_wait_ms=None,
            loops=None,
            redraws=None,
            events=None,
''',
    '''            input_wait_ms=None,
            background_ms=None,
            tick_ms=None,
            max_tick_ms=None,
            max_draw_ms=None,
            max_dispatch_ms=None,
            loops=None,
            redraws=None,
            clock_refreshes=None,
            events=None,
            notification_invalidations=None,
            tick_invalidations=None,
            input_invalidations=None,
''',
)
replace_once(
    "retrotui/core/profile_metrics.py",
    '''        input_wait_ms=final_values.get("input_wait_ms"),
        loops=_to_int(final_values.get("loops")),
        redraws=_to_int(final_values.get("redraws")),
        events=_to_int(final_values.get("events")),
''',
    '''        input_wait_ms=final_values.get("input_wait_ms"),
        background_ms=final_values.get("background_ms"),
        tick_ms=final_values.get("tick_ms"),
        max_tick_ms=final_values.get("max_tick_ms"),
        max_draw_ms=final_values.get("max_draw_ms"),
        max_dispatch_ms=final_values.get("max_dispatch_ms"),
        loops=_to_int(final_values.get("loops")),
        redraws=_to_int(final_values.get("redraws")),
        clock_refreshes=_to_int(final_values.get("clock_refreshes")),
        events=_to_int(final_values.get("events")),
        notification_invalidations=_to_int(
            final_values.get("invalidations_notification")
        ),
        tick_invalidations=_to_int(final_values.get("invalidations_tick")),
        input_invalidations=_to_int(final_values.get("invalidations_input")),
''',
)
replace_once(
    "tools/baseline_extract.py",
    '''    print(f"- input_wait_ms: {_format_metric(profile.input_wait_ms)}")
    print()
''',
    '''    print(f"- input_wait_ms: {_format_metric(profile.input_wait_ms)}")
    print(f"- background_ms: {_format_metric(profile.background_ms)}")
    print(f"- tick_ms: {_format_metric(profile.tick_ms)}")
    print(f"- max_tick_ms: {_format_metric(profile.max_tick_ms)}")
    print(f"- max_draw_ms: {_format_metric(profile.max_draw_ms)}")
    print(f"- max_dispatch_ms: {_format_metric(profile.max_dispatch_ms)}")
    print(f"- clock_refreshes: {_format_metric(profile.clock_refreshes)}")
    print(
        "- invalidations: "
        f"notification={_format_metric(profile.notification_invalidations)} "
        f"tick={_format_metric(profile.tick_invalidations)} "
        f"input={_format_metric(profile.input_invalidations)}"
    )
    print()
''',
)

# ---------------------------------------------------------------------------
# Documentation: define the corrected redraw semantics and repeatable measures.
# ---------------------------------------------------------------------------
replace_once(
    "docs/BASELINE_PROFILING.md",
    '''- Event loop redraw behavior (`redraw_ratio`)
- Approximate idle wait time (`input_wait_ms`)
- CPU and RAM from host process monitor
''',
    '''- Full-frame redraw behavior (`redraw_ratio`)
- Partial menu-clock refreshes (`clock_refreshes`)
- Background and window update cost (`background_ms`, `tick_ms`, `max_tick_ms`)
- Render/dispatch worst cases (`max_draw_ms`, `max_dispatch_ms`)
- Redraw causes (`invalidations_notification`, `invalidations_tick`, `invalidations_input`)
- Approximate idle wait time (`input_wait_ms`)
- CPU and RAM from host process monitor
''',
)
replace_once(
    "docs/BASELINE_PROFILING.md",
    '''- `profile_final ... redraw_ratio=...`

Optional extractor (from saved log file):
''',
    '''- `profile_final ... redraw_ratio=... clock_refreshes=... tick_ms=...`

`redraws` and `redraw_ratio` count only complete frames. The menu clock uses a
partial curses refresh and is reported separately as `clock_refreshes`. This
keeps before/after redraw comparisons stable when the clock is visible.

Optional extractor (from saved log file):
''',
)

# ---------------------------------------------------------------------------
# Focused regressions in the owning test modules.
# ---------------------------------------------------------------------------
replace_once(
    "tests/test_process_manager_more.py",
    '''    def test_sorting_and_selection_visibility(self):
''',
    '''    def test_tick_delegates_to_rate_limited_refresh_result(self):
        with mock.patch.object(
            self.win,
            "refresh_processes",
            return_value=False,
        ) as refresh:
            self.assertFalse(self.win.tick())
        refresh.assert_called_once_with(force=False)

    def test_command_cache_is_identity_scoped_and_ttl_bounded(self):
        self.win._command_cache = {}
        with mock.patch.object(
            self.win,
            "_read_command",
            side_effect=["first", "second", "third"],
        ) as read_command:
            self.assertEqual(self.win._command_for_process(7, 100, 1.0), "first")
            self.assertEqual(self.win._command_for_process(7, 100, 2.0), "first")
            self.assertEqual(self.win._command_for_process(7, 100, 7.0), "second")
            self.assertEqual(self.win._command_for_process(7, 101, 7.0), "third")
        self.assertEqual(read_command.call_count, 3)

    def test_sort_avoids_proc_rescan_and_preserves_selected_process(self):
        selected = self.ProcessRow(7, 1.0, 2.0, "selected", 10, 100)
        self.win.rows = [
            self.ProcessRow(9, 3.0, 1.0, "other", 20, 200),
            selected,
        ]
        self.win.selected_index = 1
        with mock.patch.object(self.win, "refresh_processes") as refresh:
            self.win._set_sort("pid")
        refresh.assert_not_called()
        self.assertEqual(self.win._selected_row().pid, selected.pid)
        self.assertEqual(
            self.win._selected_row().start_time_ticks,
            selected.start_time_ticks,
        )

    def test_refresh_rate_limit_returns_false_before_proc_io(self):
        self.win._last_refresh = 10.0
        with (
            mock.patch.object(self.pm_mod.time, "monotonic", return_value=10.5),
            mock.patch.object(self.win, "_read_meminfo") as read_meminfo,
        ):
            self.assertFalse(self.win.refresh_processes(force=False))
        read_meminfo.assert_not_called()

    def test_sorting_and_selection_visibility(self):
''',
)
replace_once(
    "tests/test_event_loop.py",
    '''        self.assertEqual(metrics["report_interval_s"], 5.0)

    def test_emit_runtime_metrics_uses_default_for_invalid_interval(self):
''',
    '''        self.assertEqual(metrics["report_interval_s"], 5.0)
        self.assertIn("clock_refreshes", metrics)
        self.assertIn("tick_time_s", metrics)
        self.assertIn("max_draw_time_s", metrics)

    def test_emit_runtime_metrics_uses_default_for_invalid_interval(self):
''',
)
replace_once(
    "tests/test_event_loop.py",
    '''        self.fake_curses.doupdate.assert_called_once_with()

    def test_run_app_loop_converts_keyboard_interrupt_into_ctrl_c_key(self):
''',
    '''        self.fake_curses.doupdate.assert_called_once_with()
        self.assertEqual(app._runtime_metrics["redraws"], 0)
        self.assertEqual(app._runtime_metrics["clock_refreshes"], 1)

    def test_run_app_loop_converts_keyboard_interrupt_into_ctrl_c_key(self):
''',
)
replace_once(
    "tests/test_profile_metrics.py",
    '''        'ts=... level=DEBUG logger=retrotui.core.event_loop msg="profile_final elapsed_s=8.000 loops=480 redraws=61 redraw_ratio=0.127 events=23 draw_ms=18.50 dispatch_ms=5.10 input_wait_ms=7976.40"',
''',
    '''        'ts=... level=DEBUG logger=retrotui.core.event_loop msg="profile_final elapsed_s=8.000 loops=480 redraws=61 clock_refreshes=8 redraw_ratio=0.127 events=23 invalidations_notification=2 invalidations_tick=19 invalidations_input=23 background_ms=4.50 tick_ms=12.25 draw_ms=18.50 dispatch_ms=5.10 input_wait_ms=7976.40 max_tick_ms=1.20 max_draw_ms=3.40 max_dispatch_ms=0.80"',
''',
)
replace_once(
    "tests/test_profile_metrics.py",
    '''    assert out.input_wait_ms == 7976.4
''',
    '''    assert out.input_wait_ms == 7976.4
    assert out.background_ms == 4.5
    assert out.tick_ms == 12.25
    assert out.max_tick_ms == 1.2
    assert out.max_draw_ms == 3.4
    assert out.max_dispatch_ms == 0.8
    assert out.clock_refreshes == 8
    assert out.notification_invalidations == 2
    assert out.tick_invalidations == 19
    assert out.input_invalidations == 23
''',
)

print("Applied runtime performance hardening.")

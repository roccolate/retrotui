"""Repair compatibility contracts found by the complete suite.

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
    "retrotui/apps/process_manager.py",
    '''        if sampled_at is None:
            sampled_at = time.monotonic()
''',
    '''        if sampled_at is None:
            sampled_at = getattr(self, "_active_sample_time", None)
        if sampled_at is None:
            sampled_at = time.monotonic()
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
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
    '''        self._active_sample_time = now
        try:
            for name in proc_dirs:
                pid = int(name)
                # Preserve the historical three-argument override contract.
                row = self._read_process_row(pid, total_delta, mem_total_kb)
                if row is None:
                    continue
                identity = self._process_identity(row.pid, row.start_time_ticks)
                rows.append(row)
                new_ticks[identity] = row.total_ticks
                live_identities.add(identity)
        finally:
            self._active_sample_time = None
''',
)
replace_once(
    "retrotui/apps/process_manager.py",
    '''    def tick(self):
        """Refresh process data only when its sampling interval has elapsed."""
        return bool(self.refresh_processes(force=False))
''',
    '''    def tick(self):
        """Refresh process data only when its sampling interval has elapsed."""
        changed = self.refresh_processes(force=False)
        if changed is not None:
            return bool(changed)

        # Compatibility for legacy overrides that mutate rows but return None.
        signature = self._render_signature()
        changed = signature != self._last_render_signature
        self._last_render_signature = signature
        return changed
''',
)
replace_once(
    "retrotui/core/profile_metrics.py",
    '''    boot_ms: float | None
    redraw_ratio: float | None
    draw_ms: float | None
    dispatch_ms: float | None
    input_wait_ms: float | None
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
    '''    boot_ms: float | None
    redraw_ratio: float | None
    draw_ms: float | None
    dispatch_ms: float | None
    input_wait_ms: float | None
    loops: int | None
    redraws: int | None
    events: int | None
    background_ms: float | None = None
    tick_ms: float | None = None
    max_tick_ms: float | None = None
    max_draw_ms: float | None = None
    max_dispatch_ms: float | None = None
    clock_refreshes: int | None = None
    notification_invalidations: int | None = None
    tick_invalidations: int | None = None
    input_invalidations: int | None = None
''',
)

print("Applied runtime performance compatibility repair.")

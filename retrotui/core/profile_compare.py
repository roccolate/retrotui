"""Helpers to compare RetroTUI baseline profile snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from .profile_metrics import BaselineProfile


@dataclass(frozen=True)
class BaselineDelta:
    """Difference between two baseline snapshots."""

    boot_ms_delta: float | None
    redraw_ratio_delta: float | None
    draw_ms_delta: float | None
    dispatch_ms_delta: float | None
    input_wait_ms_delta: float | None
    loops_delta: int | None
    redraws_delta: int | None
    events_delta: int | None


def _delta_float(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return after - before


def _delta_int(before: int | None, after: int | None) -> int | None:
    if before is None or after is None:
        return None
    return int(after - before)


def compare_profiles(before: BaselineProfile, after: BaselineProfile) -> BaselineDelta:
    """Compute deltas where both sides have values."""
    return BaselineDelta(
        boot_ms_delta=_delta_float(before.boot_ms, after.boot_ms),
        redraw_ratio_delta=_delta_float(before.redraw_ratio, after.redraw_ratio),
        draw_ms_delta=_delta_float(before.draw_ms, after.draw_ms),
        dispatch_ms_delta=_delta_float(before.dispatch_ms, after.dispatch_ms),
        input_wait_ms_delta=_delta_float(before.input_wait_ms, after.input_wait_ms),
        loops_delta=_delta_int(before.loops, after.loops),
        redraws_delta=_delta_int(before.redraws, after.redraws),
        events_delta=_delta_int(before.events, after.events),
    )

"""Helpers to parse runtime profiling logs into baseline summaries."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


_BOOT_MS_PATTERN = re.compile(r"\bboot_ms=(?P<value>\d+(?:\.\d+)?)\b")
_KV_FLOAT_PATTERN = re.compile(r"\b(?P<key>[a-z_]+)=(?P<value>-?\d+(?:\.\d+)?)\b")


@dataclass(frozen=True)
class BaselineProfile:
    """Parsed metrics from RetroTUI runtime logs."""

    boot_ms: float | None
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


def _to_int(value: float | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _parse_kv_numbers(line: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for match in _KV_FLOAT_PATTERN.finditer(line):
        key = match.group("key")
        raw = match.group("value")
        try:
            values[key] = float(raw)
        except ValueError:
            continue
    return values


def parse_profile_metrics(lines: Iterable[str]) -> BaselineProfile:
    """Extract baseline metrics from RETROTUI_DEBUG/PROFILE logs."""
    boot_ms: float | None = None
    final_values: dict[str, float] = {}

    for raw_line in lines:
        line = str(raw_line)
        if "startup " in line and boot_ms is None:
            boot_match = _BOOT_MS_PATTERN.search(line)
            if boot_match is not None:
                try:
                    boot_ms = float(boot_match.group("value"))
                except ValueError:
                    pass

        if "profile_final " in line:
            final_values = _parse_kv_numbers(line)

    if not final_values:
        return BaselineProfile(
            boot_ms=boot_ms,
            redraw_ratio=None,
            draw_ms=None,
            dispatch_ms=None,
            input_wait_ms=None,
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
        )

    return BaselineProfile(
        boot_ms=boot_ms,
        redraw_ratio=final_values.get("redraw_ratio"),
        draw_ms=final_values.get("draw_ms"),
        dispatch_ms=final_values.get("dispatch_ms"),
        input_wait_ms=final_values.get("input_wait_ms"),
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
    )

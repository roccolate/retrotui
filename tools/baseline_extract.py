"""Extract baseline metrics from a RetroTUI debug/profile log file."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import socket
import sys

from retrotui.core.profile_metrics import parse_profile_metrics


def _format_metric(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract startup/profile_final metrics from a RetroTUI log."
    )
    parser.add_argument(
        "log_file",
        type=Path,
        help="Path to a captured RETROTUI_DEBUG/PROFILE log file.",
    )
    parser.add_argument(
        "--terminal",
        default="unknown",
        help="Terminal/environment label for markdown row (default: unknown).",
    )
    parser.add_argument(
        "--host",
        default=socket.gethostname(),
        help="Host label for markdown row (default: current hostname).",
    )
    parser.add_argument(
        "--date",
        dest="run_date",
        default=date.today().isoformat(),
        help="Run date for markdown row YYYY-MM-DD (default: today).",
    )
    parser.add_argument(
        "--cpu-idle",
        default="n/a",
        help="Optional CPU idle %% value for markdown row.",
    )
    parser.add_argument(
        "--ram-idle",
        default="n/a",
        help="Optional RAM idle MB value for markdown row.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.log_file.exists():
        print(f"log file not found: {args.log_file}", file=sys.stderr)
        return 2

    text = args.log_file.read_text(encoding="utf-8", errors="replace")
    profile = parse_profile_metrics(text.splitlines())

    print("Parsed Metrics")
    print(f"- boot_ms: {_format_metric(profile.boot_ms)}")
    print(f"- redraw_ratio: {_format_metric(profile.redraw_ratio, digits=3)}")
    print(f"- loops: {_format_metric(profile.loops)}")
    print(f"- redraws: {_format_metric(profile.redraws)}")
    print(f"- events: {_format_metric(profile.events)}")
    print(f"- draw_ms: {_format_metric(profile.draw_ms)}")
    print(f"- dispatch_ms: {_format_metric(profile.dispatch_ms)}")
    print(f"- input_wait_ms: {_format_metric(profile.input_wait_ms)}")
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
    print("Markdown Row")
    print(
        f"| {args.run_date} | {args.host} | {args.terminal} | "
        f"{_format_metric(profile.boot_ms)} | "
        f"{_format_metric(profile.redraw_ratio, digits=3)} | "
        f"{args.cpu_idle} | {args.ram_idle} | "
        f"loops={_format_metric(profile.loops)} redraws={_format_metric(profile.redraws)} "
        f"events={_format_metric(profile.events)} |"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

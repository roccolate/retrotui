"""Compare two RetroTUI profile logs and print a markdown-ready delta row."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import socket
import sys

from retrotui.core.profile_compare import compare_profiles
from retrotui.core.profile_metrics import parse_profile_metrics


def _format(value: float | int | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare RetroTUI baseline profile logs (before vs after)."
    )
    parser.add_argument("before_log", type=Path, help="Path to baseline log file.")
    parser.add_argument("after_log", type=Path, help="Path to post-change log file.")
    parser.add_argument("--host", default=socket.gethostname(), help="Host label.")
    parser.add_argument("--terminal", default="unknown", help="Terminal label.")
    parser.add_argument(
        "--run-date",
        default=date.today().isoformat(),
        help="Date label (YYYY-MM-DD).",
    )
    return parser


def _read_profile(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_profile_metrics(text.splitlines())


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.before_log.exists():
        print(f"before log not found: {args.before_log}", file=sys.stderr)
        return 2
    if not args.after_log.exists():
        print(f"after log not found: {args.after_log}", file=sys.stderr)
        return 2

    before = _read_profile(args.before_log)
    after = _read_profile(args.after_log)
    delta = compare_profiles(before, after)

    print("Delta (after - before)")
    print(f"- boot_ms: {_format(delta.boot_ms_delta)}")
    print(f"- redraw_ratio: {_format(delta.redraw_ratio_delta)}")
    print(f"- draw_ms: {_format(delta.draw_ms_delta)}")
    print(f"- dispatch_ms: {_format(delta.dispatch_ms_delta)}")
    print(f"- input_wait_ms: {_format(delta.input_wait_ms_delta)}")
    print(f"- loops: {_format(delta.loops_delta)}")
    print(f"- redraws: {_format(delta.redraws_delta)}")
    print(f"- events: {_format(delta.events_delta)}")
    print()
    print("Markdown Row")
    print(
        f"| {args.run_date} | {args.host} | {args.terminal} | "
        f"{_format(delta.boot_ms_delta)} | {_format(delta.redraw_ratio_delta)} | "
        f"{_format(delta.draw_ms_delta)} | {_format(delta.dispatch_ms_delta)} | "
        f"{_format(delta.input_wait_ms_delta)} | {_format(delta.loops_delta)} | "
        f"{_format(delta.redraws_delta)} | {_format(delta.events_delta)} |"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

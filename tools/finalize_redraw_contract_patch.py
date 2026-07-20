#!/usr/bin/env python3
"""Remove the last legacy periodic-timeout fallback after the main patch."""
from pathlib import Path

path = Path("retrotui/core/event_loop.py")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
markers = [
    index
    for index, line in enumerate(lines)
    if '"input_timeout_animated_ms"' in line
]
if len(markers) != 1:
    raise SystemExit(f"expected one legacy timeout marker, found {len(markers)}")

marker = markers[0]
start = marker - 2
end = marker + 3
if start < 0 or end > len(lines):
    raise SystemExit("legacy timeout block is incomplete")
if "getattr(" not in lines[start] or ")," not in lines[end - 1]:
    raise SystemExit("legacy timeout block shape changed")

indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
lines[start:end] = [f"{indent}TERMINAL_ANIMATED_INPUT_TIMEOUT_MS,\n"]
path.write_text("".join(lines), encoding="utf-8")

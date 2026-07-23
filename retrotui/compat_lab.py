"""Guided real-terminal compatibility lab for RetroTUI."""

from __future__ import annotations

import curses
import json
import locale
import os
import platform
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from wcwidth import wcswidth

_STATUSES = ("pass", "warn", "fail", "skip")


@dataclass
class CompatibilityCheck:
    """One automated or guided compatibility result."""

    check_id: str
    title: str
    status: str
    details: str = ""
    notes: str = ""
    kind: str = "guided"

    def __post_init__(self):
        if self.status not in _STATUSES:
            raise ValueError(f"unsupported compatibility status: {self.status!r}")


@dataclass
class CompatibilityReport:
    """Portable JSON/Markdown report emitted by the lab."""

    label: str
    generated_at: str
    environment: dict[str, object]
    checks: list[CompatibilityCheck] = field(default_factory=list)
    schema_version: int = 1

    def summary(self):
        totals = {status: 0 for status in _STATUSES}
        for check in self.checks:
            totals[check.status] += 1
        totals["total"] = len(self.checks)
        return totals

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "label": self.label,
            "generated_at": self.generated_at,
            "environment": dict(self.environment),
            "summary": self.summary(),
            "checks": [asdict(check) for check in self.checks],
        }

    def to_markdown(self):
        totals = self.summary()
        lines = [
            "# RetroTUI Compatibility Report",
            "",
            f"- **Label:** {self.label}",
            f"- **Generated:** {self.generated_at}",
            f"- **Result:** {totals['pass']} pass, {totals['warn']} warn, "
            f"{totals['fail']} fail, {totals['skip']} skip",
            "",
            "## Environment",
            "",
        ]
        lines.extend(
            f"- **{key}:** `{self.environment[key]}`"
            for key in sorted(self.environment)
        )
        lines.extend(["", "## Checks", ""])
        for check in self.checks:
            lines.extend([f"### [{check.status.upper()}] {check.title}", ""])
            if check.details:
                lines.extend([check.details, ""])
            if check.notes:
                lines.extend([f"**Notes:** {check.notes}", ""])
        return "\n".join(lines).rstrip() + "\n"


def _isatty(stream):
    try:
        return bool(stream.isatty())
    except (AttributeError, OSError, ValueError):
        return False


def collect_environment():
    """Collect host and terminal metadata before curses starts."""
    size = shutil.get_terminal_size(fallback=(0, 0))
    data = {
        "platform": platform.system() or sys.platform,
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "sys_platform": sys.platform,
        "os_name": os.name,
        "preferred_encoding": locale.getpreferredencoding(False),
        "stdout_encoding": getattr(sys.stdout, "encoding", None) or "unknown",
        "stdin_tty": _isatty(sys.stdin),
        "stdout_tty": _isatty(sys.stdout),
        "terminal_columns": int(size.columns),
        "terminal_lines": int(size.lines),
    }
    for name in (
        "TERM",
        "COLORTERM",
        "TERM_PROGRAM",
        "TERM_PROGRAM_VERSION",
        "WT_SESSION",
        "TMUX",
        "STY",
        "SSH_TTY",
        "SHELL",
        "COMSPEC",
    ):
        if os.environ.get(name):
            data[name.lower()] = os.environ[name]
    return data


def automated_checks(environment):
    """Return deterministic preflight checks, useful even without a TTY."""
    encoding = (
        f"{environment.get('stdout_encoding', '')} "
        f"{environment.get('preferred_encoding', '')}"
    )
    stdin_tty = bool(environment.get("stdin_tty"))
    stdout_tty = bool(environment.get("stdout_tty"))
    cols = int(environment.get("terminal_columns") or 0)
    rows = int(environment.get("terminal_lines") or 0)
    identity = (
        environment.get("term")
        or environment.get("term_program")
        or environment.get("wt_session")
    )
    width_ok = wcswidth("界") == 2 and wcswidth("e\u0301") == 1
    return [
        CompatibilityCheck(
            "encoding.utf8",
            "UTF-8 output encoding",
            "pass" if "utf" in encoding.lower() else "warn",
            encoding,
            kind="automated",
        ),
        CompatibilityCheck(
            "host.tty",
            "Interactive TTY",
            "pass" if stdin_tty and stdout_tty else "warn",
            f"stdin={stdin_tty}; stdout={stdout_tty}",
            kind="automated",
        ),
        CompatibilityCheck(
            "host.size",
            "Minimum 80x24 viewport",
            "pass" if cols >= 80 and rows >= 24 else "warn",
            f"reported_size={cols}x{rows}",
            kind="automated",
        ),
        CompatibilityCheck(
            "host.identity",
            "Terminal identity available",
            "pass" if identity else "warn",
            f"identity={identity or 'unknown'}",
            kind="automated",
        ),
        CompatibilityCheck(
            "unicode.width_model",
            "Unicode column-width model",
            "pass" if width_ok else "fail",
            f"CJK={wcswidth('界')}; combining={wcswidth('é')}",
            kind="automated",
        ),
    ]


def _slug(value):
    return (
        re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip())
        .strip("-.")[:80]
        or "terminal"
    )


def resolve_report_paths(output_path=None, *, label, stamp):
    """Resolve paired JSON and Markdown paths."""
    if output_path is None:
        stem = (
            Path.home()
            / ".config"
            / "retrotui"
            / "compatibility"
            / f"{stamp}-{_slug(label)}"
        )
    else:
        candidate = Path(output_path).expanduser()
        if candidate.suffix.lower() in {".json", ".md"}:
            stem = candidate.with_suffix("")
        else:
            stem = candidate / f"{stamp}-{_slug(label)}"
    return stem.with_suffix(".json"), stem.with_suffix(".md")


def write_report(report, output_path=None):
    """Persist both report formats through RetroTUI's atomic writer."""
    from .utils import atomic_write_text

    stamp = datetime.fromisoformat(report.generated_at).strftime("%Y%m%d-%H%M%S")
    json_path, markdown_path = resolve_report_paths(
        output_path,
        label=report.label,
        stamp=stamp,
    )
    atomic_write_text(
        json_path,
        json.dumps(
            report.to_dict(),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
    )
    atomic_write_text(markdown_path, report.to_markdown())
    return json_path, markdown_path


def _safe_add(stdscr, y, x, text, attr=0):
    try:
        height, width = stdscr.getmaxyx()
        if 0 <= y < height and 0 <= x < width:
            stdscr.addnstr(y, x, str(text), max(0, width - x - 1), attr)
    except curses.error:
        pass


_CASES = (
    (
        "visual.colors",
        "Colors and text attributes",
        ("Confirm colors are distinct and bold/underline/reverse are visible.",),
    ),
    (
        "visual.unicode",
        "Unicode, CJK, emoji and combining text",
        ("Check joined borders, wide-glyph alignment and one-cell combining text.",),
    ),
    (
        "input.keyboard",
        "Keyboard translation",
        ("Press arrows, Home/End, Insert/Delete, Page keys and function keys.",),
    ),
    (
        "input.mouse",
        "Mouse input",
        ("Click, double-click, drag and use the wheel inside the terminal.",),
    ),
    (
        "host.resize",
        "Live terminal resize",
        ("Resize smaller and larger; the page should redraw without corruption.",),
    ),
)


class CompatibilityLabUI:
    """Small curses wizard that records human-observed behavior."""

    def __init__(self, stdscr, report):
        self.stdscr = stdscr
        self.report = report
        self.initial_size = stdscr.getmaxyx()
        self.resize_observed = False
        self.last_event = "none"

    def initialize(self):
        self.stdscr.keypad(True)
        for name, args in (
            ("curs_set", (0,)),
            ("start_color", ()),
            ("use_default_colors", ()),
        ):
            call = getattr(curses, name, None)
            if not callable(call):
                continue
            try:
                call(*args)
            except curses.error:
                pass

        mousemask = getattr(curses, "mousemask", None)
        try:
            if callable(mousemask):
                available, _old = mousemask(
                    getattr(curses, "ALL_MOUSE_EVENTS", 0)
                    | getattr(curses, "REPORT_MOUSE_POSITION", 0)
                )
            else:
                available = 0
        except curses.error:
            available = 0

        has_colors = getattr(curses, "has_colors", None)
        try:
            colors_enabled = bool(has_colors()) if callable(has_colors) else False
        except curses.error:
            colors_enabled = False

        self.report.environment.update(
            {
                "curses_colors": int(getattr(curses, "COLORS", 0) or 0),
                "curses_color_pairs": int(
                    getattr(curses, "COLOR_PAIRS", 0) or 0
                ),
                "curses_has_colors": colors_enabled,
                "curses_mouse_enabled": bool(available),
            }
        )

    def draw_samples(self, check_id, row):
        if check_id == "visual.colors":
            attrs = (
                ("normal", 0),
                ("bold", curses.A_BOLD),
                ("underline", curses.A_UNDERLINE),
                ("reverse", curses.A_REVERSE),
            )
            for offset, (label, attr) in enumerate(attrs):
                _safe_add(self.stdscr, row + offset, 2, f" {label} ", attr)

            color_count = min(8, int(getattr(curses, "COLORS", 0) or 0))
            for color in range(color_count):
                pair_id = color + 1
                try:
                    curses.init_pair(pair_id, color, -1)
                    attr = curses.color_pair(pair_id)
                except curses.error:
                    attr = 0
                _safe_add(
                    self.stdscr,
                    row + 5 + color // 4,
                    2 + (color % 4) * 14,
                    f" color {color} ",
                    attr,
                )
        elif check_id == "visual.unicode":
            samples = (
                "╔═╗ ┌─┐ ├┼┤",
                "界面 日本語",
                "😀 🚀 🧪",
                "A界B  A😀B  AéB",
                "12345678901234567890",
            )
            for offset, line in enumerate(samples):
                _safe_add(self.stdscr, row + offset, 2, line)
        elif check_id == "input.mouse":
            _safe_add(
                self.stdscr,
                row,
                2,
                "+-------------- mouse target --------------+",
            )
            for offset in range(1, 5):
                _safe_add(
                    self.stdscr,
                    row + offset,
                    2,
                    "|                                          |",
                )
            _safe_add(
                self.stdscr,
                row + 5,
                2,
                "+------------------------------------------+",
            )

    def prompt_note(self):
        height, width = self.stdscr.getmaxyx()
        try:
            curses.echo()
            curses.curs_set(1)
            _safe_add(self.stdscr, height - 2, 0, "Note: ")
            raw = self.stdscr.getstr(
                height - 2,
                6,
                max(1, width - 8),
            )
            return raw.decode("utf-8", errors="replace").strip()
        except (curses.error, OSError):
            return ""
        finally:
            try:
                curses.noecho()
                curses.curs_set(0)
            except curses.error:
                pass

    def record_event(self, key):
        if key == getattr(curses, "KEY_MOUSE", -1):
            try:
                _id, x, y, _z, state = curses.getmouse()
                self.last_event = f"mouse x={x} y={y} state={state}"
            except curses.error:
                self.last_event = "mouse error"
        elif key == getattr(curses, "KEY_RESIZE", -1):
            self.resize_observed = True
            self.last_event = "resize"
        else:
            self.last_event = (
                repr(key) if isinstance(key, str) else f"keycode {key}"
            )

    def run(self):
        self.initialize()
        for index, (check_id, title, instructions) in enumerate(_CASES):
            note = ""
            while True:
                self.stdscr.erase()
                height, width = self.stdscr.getmaxyx()
                if (height, width) != self.initial_size:
                    self.resize_observed = True
                _safe_add(
                    self.stdscr,
                    0,
                    0,
                    f"RetroTUI Compatibility Lab [{index + 1}/{len(_CASES)}]",
                    curses.A_BOLD,
                )
                _safe_add(self.stdscr, 2, 2, title, curses.A_BOLD)
                row = 4
                for line in instructions:
                    _safe_add(self.stdscr, row, 2, line)
                    row += 1
                self.draw_samples(check_id, row + 1)
                _safe_add(
                    self.stdscr,
                    height - 3,
                    0,
                    f"size={width}x{height} last={self.last_event} "
                    f"note={note or '-'}",
                )
                _safe_add(
                    self.stdscr,
                    height - 1,
                    0,
                    "P pass | W warn | F fail | S skip | N note | Q abort",
                    curses.A_REVERSE,
                )
                self.stdscr.refresh()
                try:
                    key = self.stdscr.get_wch()
                except curses.error:
                    continue
                self.record_event(key)
                if not isinstance(key, str):
                    continue
                action = key.lower()
                if action == "n":
                    note = self.prompt_note()
                    continue
                if action == "q":
                    self.report.checks.append(
                        CompatibilityCheck(
                            check_id,
                            title,
                            "skip",
                            "Lab aborted before classification.",
                            note,
                        )
                    )
                    return
                status = {
                    "p": "pass",
                    "w": "warn",
                    "f": "fail",
                    "s": "skip",
                }.get(action)
                if status:
                    details = f"last_event={self.last_event}"
                    if check_id == "host.resize":
                        details += f"; resize_observed={self.resize_observed}"
                    self.report.checks.append(
                        CompatibilityCheck(
                            check_id,
                            title,
                            status,
                            details,
                            note,
                        )
                    )
                    break


def build_report(label=None):
    environment = collect_environment()
    identity = (
        environment.get("term_program")
        or environment.get("term")
        or environment.get("wt_session")
        or "unknown-terminal"
    )
    report = CompatibilityReport(
        label=str(
            label
            or f"{environment.get('platform', sys.platform)}-{identity}"
        ),
        generated_at=datetime.now()
        .astimezone()
        .replace(microsecond=0)
        .isoformat(),
        environment=environment,
    )
    report.checks.extend(automated_checks(environment))
    return report


def run_compatibility_lab(*, output_path=None, label=None, interactive=True):
    """Run the lab, save reports and return nonzero only for failed checks."""
    report = build_report(label)
    if interactive:
        try:
            curses.wrapper(
                lambda stdscr: CompatibilityLabUI(stdscr, report).run()
            )
        except (curses.error, OSError, RuntimeError) as exc:
            report.checks.append(
                CompatibilityCheck(
                    "lab.runtime",
                    "Compatibility Lab curses runtime",
                    "fail",
                    f"{type(exc).__name__}: {exc}",
                    kind="automated",
                )
            )
    else:
        report.checks.append(
            CompatibilityCheck(
                "lab.guided",
                "Guided visual and input checks",
                "skip",
                "Skipped by --compat-auto.",
            )
        )
    json_path, markdown_path = write_report(report, output_path)
    totals = report.summary()
    print(f"Compatibility JSON: {json_path}")
    print(f"Compatibility Markdown: {markdown_path}")
    print(
        f"Result: {totals['pass']} pass, {totals['warn']} warn, "
        f"{totals['fail']} fail, {totals['skip']} skip"
    )
    return 1 if totals["fail"] else 0

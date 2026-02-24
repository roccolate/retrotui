"""QA Runner plugin for RetroTUI."""

from __future__ import annotations

import subprocess
import sys
import time

from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    """Run repository QA/test commands and show output."""

    MAX_LINES = 1200
    _KEY_UP = 259
    _KEY_DOWN = 258
    _KEY_PPAGE = 339
    _KEY_NPAGE = 338

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._output_lines = []
        self._scroll = 0
        self._status = "Ready"

    def _set_output(self, text):
        lines = text.splitlines() if text else []
        if len(lines) > self.MAX_LINES:
            lines = lines[-self.MAX_LINES :]
        self._output_lines = lines
        self._scroll = max(0, len(self._output_lines) - 1)

    def _run_command(self, cmd):
        started = time.perf_counter()
        self._status = "Running: " + " ".join(cmd)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
            elapsed = time.perf_counter() - started
            output = ((proc.stdout or "") + ("\n" if proc.stdout and proc.stderr else "") + (proc.stderr or "")).strip()
            self._set_output(output)
            self._status = f"Done (rc={proc.returncode}, {elapsed:.1f}s)"
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._set_output(str(exc))
            self._status = "Failed to run command"

    def _normalize_key(self, key):
        if isinstance(key, int):
            return key
        if isinstance(key, str) and len(key) == 1:
            return ord(key)
        return None

    def handle_key(self, key):
        key_code = self._normalize_key(key)
        if key_code is None:
            return None

        if key_code in (ord("r"), ord("R")):
            self._run_command([sys.executable, "tools/qa.py"])
            return None
        if key_code in (ord("u"), ord("U")):
            self._run_command([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
            return None
        if key_code in (ord("c"), ord("C")):
            self._output_lines = []
            self._scroll = 0
            self._status = "Output cleared"
            return None

        if key_code == self._KEY_UP:
            self._scroll = max(0, self._scroll - 1)
            return None
        if key_code == self._KEY_DOWN:
            self._scroll = min(max(0, len(self._output_lines) - 1), self._scroll + 1)
            return None
        if key_code == self._KEY_PPAGE:
            self._scroll = max(0, self._scroll - 10)
            return None
        if key_code == self._KEY_NPAGE:
            self._scroll = min(max(0, len(self._output_lines) - 1), self._scroll + 10)
            return None
        return None

    def draw_content(self, stdscr, x, y, w, h):
        body_attr = theme_attr("window_body")
        header_attr = theme_attr("menubar")
        status_attr = theme_attr("status")

        safe_addstr(stdscr, y, x, (" QA Runner [R]=qa.py [U]=unittest [C]=clear ".ljust(w))[:w], header_attr)
        safe_addstr(stdscr, y + 1, x, (f" Status: {self._status} ".ljust(w))[:w], status_attr)

        content_y = y + 2
        content_h = max(0, h - 2)
        if content_h <= 0:
            return

        if not self._output_lines:
            safe_addstr(stdscr, content_y, x, "No output yet. Press R or U.".ljust(w)[:w], body_attr)
            return

        start = max(0, self._scroll - content_h + 1)
        visible = self._output_lines[start : start + content_h]
        for i in range(content_h):
            text = visible[i] if i < len(visible) else ""
            safe_addstr(stdscr, content_y + i, x, text.ljust(w)[:w], body_attr)

#!/usr/bin/env python3
"""Apply the focused hidden-terminal service tick patch."""
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, found {count}: {old!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "retrotui/core/event_loop.py",
    '''def _has_live_terminals(app):
    """Return True if any window has an active PTY session producing output."""
    for w in app.windows:
        if not getattr(w, "visible", True):
            continue
        session = getattr(w, '_session', None)
        if session is not None and getattr(session, 'running', False):
            return True
    return False
''',
    '''def _has_live_terminals(app):
    """Return True if a visible or service-ticked window has a live PTY."""
    for w in app.windows:
        visible = getattr(w, "visible", True)
        if not visible and not getattr(w, "tick_when_hidden", False):
            continue
        session = getattr(w, '_session', None)
        if session is not None and getattr(session, 'running', False):
            return True
    return False
''',
)

replace_once(
    "retrotui/core/event_loop.py",
    '''    for w in app.windows:
        if not getattr(w, "visible", True):
            continue
        tick = getattr(w, "tick", None)
        if callable(tick):
            try:
                changed = bool(tick()) or changed
            except _INPUT_TIMEOUT_APPLY_ERRORS:
                LOGGER.debug("window tick failed", exc_info=True)
        # Probe for live terminals / animated windows while we
        # already have the attribute lookup cached.
        if not has_live:
            session = getattr(w, "_session", None)
            if session is not None and getattr(session, "running", False):
                has_live = True
        if not has_animated and getattr(w, "_animated", False):
            has_animated = True
        if has_live and has_animated:
            # Both flags can short-circuit; no need to keep walking.
            # Continue to run remaining ticks (they may flip
            # ``changed`` even if the live/animated result is final).
            pass
''',
    '''    for w in app.windows:
        visible = getattr(w, "visible", True)
        tick_when_hidden = bool(getattr(w, "tick_when_hidden", False))
        if not visible and not tick_when_hidden:
            continue

        tick = getattr(w, "tick", None)
        if callable(tick):
            try:
                tick_changed = bool(tick())
                # Hidden service ticks advance background state but do not
                # dirty the visual frame until the window becomes visible.
                if visible:
                    changed = tick_changed or changed
            except _INPUT_TIMEOUT_APPLY_ERRORS:
                LOGGER.debug("window tick failed", exc_info=True)

        # A service-ticked hidden terminal still needs the low-latency input
        # timeout so its PTY cannot fill while minimized.
        if not has_live:
            session = getattr(w, "_session", None)
            if session is not None and getattr(session, "running", False):
                has_live = True
        if visible and not has_animated and getattr(w, "_animated", False):
            has_animated = True
''',
)

replace_once(
    "retrotui/core/event_loop.py",
    '''    for w in app.windows:
        if not getattr(w, "visible", True):
            continue
        tick = getattr(w, "tick", None)
        if not callable(tick):
            continue
        try:
            changed = bool(tick()) or changed
        except _INPUT_TIMEOUT_APPLY_ERRORS:
            LOGGER.debug("window tick failed", exc_info=True)
''',
    '''    for w in app.windows:
        visible = getattr(w, "visible", True)
        if not visible and not getattr(w, "tick_when_hidden", False):
            continue
        tick = getattr(w, "tick", None)
        if not callable(tick):
            continue
        try:
            tick_changed = bool(tick())
            if visible:
                changed = tick_changed or changed
        except _INPUT_TIMEOUT_APPLY_ERRORS:
            LOGGER.debug("window tick failed", exc_info=True)
''',
)

replace_once(
    "retrotui/core/event_loop.py",
    '''                if has_live or has_animated:
                    app._dirty = True
''',
    '''                # PTY output dirties the frame through ``tick_changed``.
                # Merely being alive is a polling concern, not a redraw reason.
                if has_animated:
                    app._dirty = True
''',
)

replace_once(
    "retrotui/apps/terminal.py",
    '''class TerminalWindow(SelectableTextMixin, Window):
    """PTY-backed terminal window with ANSI color support and scrollback."""

    DEFAULT_SCROLLBACK = 2000
    MAX_OUTPUT_PER_FRAME = 8192  # Throttle: max bytes processed per render tick.
''',
    '''class TerminalWindow(SelectableTextMixin, Window):
    """PTY-backed terminal window with ANSI color support and scrollback."""

    # PTY sessions are services: minimizing the window must not suspend reads.
    tick_when_hidden = True
    DEFAULT_SCROLLBACK = 2000
    MAX_OUTPUT_PER_FRAME = 8192  # Compatibility name: max chars processed per service tick.
''',
)

replace_once(
    "retrotui/apps/terminal.py",
    '''    def tick(self):
        """Poll PTY state outside the render path."""
        before = len(self._pending_output)
        self._ensure_session()
        text_cols, text_rows = self._text_area_size()
        if self._session is not None:
            try:
                size = (text_cols, text_rows)
                if size != self._last_pty_size:
                    self._session.resize(text_cols, text_rows)
                    self._last_pty_size = size
                chunk = self._session.read()
                if chunk:
                    self._pending_output += chunk
                self._session.poll_exit()
            except (OSError, RuntimeError) as exc:
                self._set_session_error(exc)
        if self._session_error and not self._reported_session_error:
            self._pending_output += self._session_error + '\\n'
            self._reported_session_error = True
        return len(self._pending_output) != before
''',
    '''    def _drain_pending_output(self):
        """Process one bounded output chunk without using curses APIs."""
        if not self._pending_output:
            return False
        to_process = self._pending_output[:self.MAX_OUTPUT_PER_FRAME]
        self._pending_output = self._pending_output[self.MAX_OUTPUT_PER_FRAME:]
        self._consume_output(to_process)
        return True

    def tick(self):
        """Poll and consume PTY output outside the render path."""
        changed = False
        self._ensure_session()
        text_cols, text_rows = self._text_area_size()
        if self._session is not None:
            try:
                size = (text_cols, text_rows)
                if size != self._last_pty_size:
                    self._session.resize(text_cols, text_rows)
                    self._last_pty_size = size
                chunk = self._session.read()
                if chunk:
                    self._pending_output += chunk
                    changed = True
                self._session.poll_exit()
            except (OSError, RuntimeError) as exc:
                self._set_session_error(exc)
        if self._session_error and not self._reported_session_error:
            self._pending_output += self._session_error + '\\n'
            self._reported_session_error = True
            changed = True
        return self._drain_pending_output() or changed
''',
)

replace_once(
    "retrotui/apps/terminal.py",
    '''        # Throttle: process at most MAX_OUTPUT_PER_FRAME per render tick.
        if self._pending_output:
            to_process = self._pending_output[:self.MAX_OUTPUT_PER_FRAME]
            self._pending_output = self._pending_output[self.MAX_OUTPUT_PER_FRAME:]
            self._consume_output(to_process)

''',
    '''        # PTY output is consumed by ``tick`` so minimized windows continue
        # draining without entering the curses render path.

''',
)

replace_once(
    "tests/test_terminal_component.py",
    '''    def test_tick_reports_session_read_error_once(self):
        win = self._make_window()
        fake_session = _FakeSession()
        fake_session.read = mock.Mock(side_effect=OSError("pty read failed"))
        win._session = fake_session

        self.assertTrue(win.tick())
        self.assertEqual(win._pending_output, "pty read failed\\n")

        self.assertFalse(win.tick())
        self.assertEqual(win._pending_output, "pty read failed\\n")
''',
    '''    def test_tick_reports_session_read_error_once(self):
        win = self._make_window()
        fake_session = _FakeSession()
        fake_session.read = mock.Mock(side_effect=OSError("pty read failed"))
        win._session = fake_session

        self.assertTrue(win.tick())
        self.assertEqual(win._pending_output, "")
        self.assertTrue(any("pty read failed" in line for line in self._get_scroll_text(win)))

        self.assertFalse(win.tick())
        self.assertEqual(win._pending_output, "")

    def test_hidden_tick_drains_pty_without_draw(self):
        win = self._make_window()
        win.visible = False
        fake_session = _FakeSession()
        fake_session.read_chunks = ["hidden output\\n"]
        win._session = fake_session

        self.assertTrue(win.tick())

        self.assertEqual(win._pending_output, "")
        self.assertTrue(any("hidden output" in line for line in self._get_scroll_text(win)))
        self.assertTrue(win.tick_when_hidden)
''',
)

print("terminal background tick patch applied")

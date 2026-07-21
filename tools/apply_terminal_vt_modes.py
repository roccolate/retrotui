#!/usr/bin/env python3
"""Apply the focused terminal VT-mode hardening slice.

This script is intentionally assertion-heavy so the automation fails instead
of producing a partial patch when the source layout changes.
"""

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_ansi() -> None:
    path = Path("retrotui/core/ansi.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "class AnsiStateMachine:\n",
        '''class CsiParams(list):
    """CSI parameters carrying an optional private marker.

    This remains list-compatible for existing consumers while preserving
    prefixes such as ``?`` that are required to distinguish DEC private modes.
    """

    __slots__ = ("private",)

    def __init__(self, values=(), *, private=""):
        super().__init__(values)
        self.private = private


class AnsiStateMachine:
''',
        "insert CsiParams",
    )
    text = replace_once(
        text,
        "        self.current_param_str = ''\n        self.attr = 0\n",
        "        self.current_param_str = ''\n        self.private_marker = ''\n        self.attr = 0\n",
        "initialize private marker",
    )
    text = replace_once(
        text,
        "                    self.params = []\n                    self.current_param_str = ''\n",
        "                    self.params = []\n                    self.current_param_str = ''\n                    self.private_marker = ''\n",
        "reset private marker",
    )
    text = replace_once(
        text,
        "            elif self.state == 'CSI':\n                if ch.isdigit():\n",
        '''            elif self.state == 'CSI':
                if (
                    ch in "?><!"
                    and not self.params
                    and not self.current_param_str
                    and not self.private_marker
                ):
                    self.private_marker = ch
                elif ch.isdigit():
''',
        "capture private marker",
    )
    text = replace_once(
        text,
        "                    if ch == 'm':\n                        self._handle_sgr(self.params)\n                    else:\n",
        "                    if ch == 'm' and not self.private_marker:\n                        self._handle_sgr(self.params)\n                    else:\n",
        "guard SGR private sequence",
    )
    text = replace_once(
        text,
        "                        yield ('CSI', ch, list(self.params))\n\n                    self.state = 'TEXT'\n",
        "                        yield ('CSI', ch, CsiParams(self.params, private=self.private_marker))\n\n                    self.state = 'TEXT'\n                    self.private_marker = ''\n",
        "emit private CSI params",
    )
    path.write_text(text, encoding="utf-8")


def patch_terminal() -> None:
    path = Path("retrotui/apps/terminal.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from ..core.terminal_session import TerminalScreen, TerminalScreenBuffer, TerminalSession\n",
        "from ..core.terminal_session import TerminalScreen, TerminalScreenBuffer, TerminalSession\nfrom ..core.terminal_modes import DEFAULT_TERMINAL_CAPABILITIES, TerminalModes\n",
        "import terminal modes",
    )
    text = replace_once(
        text,
        "        self.ansi = AnsiStateMachine()\n\n",
        "        self.ansi = AnsiStateMachine()\n        self.capabilities = DEFAULT_TERMINAL_CAPABILITIES\n        self.modes = TerminalModes()\n\n",
        "initialize terminal mode state",
    )

    old_modes = '''        if final == 'h':
            mode = _num(0, 0)
            if mode in (1049, 1047, 47):
                self._alt_screen = True
            elif mode in _MOUSE_REPORT_MODES:
                self._mouse_modes.add(mode)
            return
        if final == 'l':
            mode = _num(0, 0)
            if mode in (1049, 1047, 47):
                self._alt_screen = False
            elif mode in _MOUSE_REPORT_MODES:
                self._mouse_modes.discard(mode)
            return
'''
    new_modes = '''        private = getattr(params, "private", "")
        if final in ('h', 'l'):
            enabled = final == 'h'
            # Empty marker remains accepted for direct legacy callers/tests;
            # parser-originated DEC modes carry the authoritative ``?`` marker.
            if private not in ('', '?'):
                return
            mode_values = list(params) or [0]
            for mode in mode_values:
                if mode in (1049, 1047, 47):
                    self._alt_screen = enabled
                elif mode in _MOUSE_REPORT_MODES:
                    if enabled:
                        self._mouse_modes.add(mode)
                    else:
                        self._mouse_modes.discard(mode)
                else:
                    self.modes.set_private_mode(mode, enabled)
            return
'''
    text = replace_once(text, old_modes, new_modes, "apply DEC private modes")

    text = replace_once(
        text,
        "        if not self.active or self.scrollback_offset != 0:\n            return\n",
        "        if not self.active or self.scrollback_offset != 0 or not self.modes.cursor_visible:\n            return\n",
        "respect cursor visibility",
    )

    old_special = '''        special = {
            getattr(curses, 'KEY_UP', None): '\\x1b[A',
            getattr(curses, 'KEY_DOWN', None): '\\x1b[B',
            getattr(curses, 'KEY_RIGHT', None): '\\x1b[C',
            getattr(curses, 'KEY_LEFT', None): '\\x1b[D',
            getattr(curses, 'KEY_HOME', None): '\\x1b[H',
            getattr(curses, 'KEY_END', None): '\\x1b[F',
'''
    new_special = '''        if self.modes.application_cursor_keys:
            cursor_keys = {
                getattr(curses, 'KEY_UP', None): '\\x1bOA',
                getattr(curses, 'KEY_DOWN', None): '\\x1bOB',
                getattr(curses, 'KEY_RIGHT', None): '\\x1bOC',
                getattr(curses, 'KEY_LEFT', None): '\\x1bOD',
                getattr(curses, 'KEY_HOME', None): '\\x1bOH',
                getattr(curses, 'KEY_END', None): '\\x1bOF',
            }
        else:
            cursor_keys = {
                getattr(curses, 'KEY_UP', None): '\\x1b[A',
                getattr(curses, 'KEY_DOWN', None): '\\x1b[B',
                getattr(curses, 'KEY_RIGHT', None): '\\x1b[C',
                getattr(curses, 'KEY_LEFT', None): '\\x1b[D',
                getattr(curses, 'KEY_HOME', None): '\\x1b[H',
                getattr(curses, 'KEY_END', None): '\\x1b[F',
            }
        special = {
            **cursor_keys,
'''
    text = replace_once(text, old_special, new_special, "application cursor keys")

    paste_anchor = '''    def accept_dropped_path(self, path):
        """Accept file drop payload by inserting a shell-safe path token."""
'''
    paste_methods = '''    @staticmethod
    def _sanitize_bracketed_paste(text):
        """Prevent pasted data from terminating bracketed-paste framing early."""
        return str(text).replace('\\x1b[201~', '\\x1b[201;~')

    def _paste_payload(self, text):
        """Forward clipboard text using bracketed paste when requested."""
        if text is None or text == '':
            return
        payload = str(text)
        if self.modes.bracketed_paste:
            payload = (
                '\\x1b[200~'
                + self._sanitize_bracketed_paste(payload)
                + '\\x1b[201~'
            )
        self._forward_payload(payload)

    def _paste_clipboard(self):
        self._paste_payload(paste_text())

'''
    text = replace_once(text, paste_anchor, paste_methods + paste_anchor, "add bracketed paste helpers")
    text = replace_once(
        text,
        "        if key_code == 22:\n            self._forward_payload(paste_text())\n            return None\n",
        "        if key_code == 22:\n            self._paste_clipboard()\n            return None\n",
        "route Ctrl+V through paste helper",
    )
    text = replace_once(
        text,
        "        items.append({'label': 'Paste', 'action': lambda: self._forward_payload(paste_text())})\n",
        "        items.append({'label': 'Paste', 'action': self._paste_clipboard})\n",
        "route context paste through helper",
    )
    text = replace_once(
        text,
        "        self.ansi = AnsiStateMachine()\n        self._scroll_lines = []\n",
        "        self.ansi = AnsiStateMachine()\n        self.modes.reset()\n        self._scroll_lines = []\n",
        "reset modes with session",
    )
    path.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = Path("tests/test_terminal_component.py")
    text = path.read_text(encoding="utf-8")
    marker = '\n\nif __name__ == "__main__":\n'
    tests = r'''
    def test_dec_private_modes_update_cursor_keys_paste_and_cursor_visibility(self):
        win = self._make_window()

        win._consume_output("\x1b[?25l\x1b[?1h\x1b[?2004h")

        self.assertFalse(win.modes.cursor_visible)
        self.assertTrue(win.modes.application_cursor_keys)
        self.assertTrue(win.modes.bracketed_paste)
        self.assertEqual(
            win._key_to_input(self.curses.KEY_UP, self.curses.KEY_UP),
            "\x1bOA",
        )

        win._consume_output("\x1b[?25;1;2004l")
        self.assertTrue(win.modes.cursor_visible)
        self.assertFalse(win.modes.application_cursor_keys)
        self.assertFalse(win.modes.bracketed_paste)
        self.assertEqual(
            win._key_to_input(self.curses.KEY_UP, self.curses.KEY_UP),
            "\x1b[A",
        )

    def test_bracketed_paste_frames_and_sanitizes_clipboard_payload(self):
        win = self._make_window()
        win.window_menu = types.SimpleNamespace(active=False)
        win._session = _FakeSession()
        win.modes.bracketed_paste = True

        with mock.patch.object(
            self.terminal_mod,
            "paste_text",
            return_value="one\n\x1b[201~two",
        ):
            self.assertIsNone(win.handle_key(22))

        self.assertEqual(
            win._session.writes[-1],
            "\x1b[200~one\n\x1b[201;~two\x1b[201~",
        )

    def test_hidden_dec_cursor_suppresses_cursor_overlay(self):
        win = self._make_window()
        win.active = True
        win.modes.cursor_visible = False
        win._line_cells = [("X", 0)]

        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win._draw_live_cursor(None, 4, 5, 10, 3, 0, 3, 0)

        safe_addstr.assert_not_called()

    def test_restart_session_resets_dec_modes(self):
        win = self._make_window()
        win.modes.cursor_visible = False
        win.modes.application_cursor_keys = True
        win.modes.bracketed_paste = True

        self.assertTrue(win.restart_session())

        self.assertTrue(win.modes.cursor_visible)
        self.assertFalse(win.modes.application_cursor_keys)
        self.assertFalse(win.modes.bracketed_paste)
'''
    if marker not in text:
        raise RuntimeError("test insertion marker missing")
    text = text.replace(marker, "\n" + tests + marker, 1)
    path.write_text(text, encoding="utf-8")


def patch_architecture() -> None:
    path = Path("ARCHITECTURE.md")
    text = path.read_text(encoding="utf-8")
    anchor = "### Scrollback\n"
    section = '''### Terminal capabilities and DEC modes

`core/terminal_modes.py` declares the conservative capability contract and
holds mutable per-session DEC mode state. `AnsiStateMachine` preserves CSI
private markers through a list-compatible `CsiParams` object so `?25`, `?1`,
`?7` and `?2004` cannot be confused with ordinary CSI parameters.

`TerminalWindow` owns the side effects:

- `?25h` / `?25l` controls cursor visibility;
- `?1h` / `?1l` selects application or normal cursor-key encoding;
- `?2004h` / `?2004l` enables bracketed paste framing;
- `?7h` / `?7l` records autowrap mode for the upcoming cell-engine slice;
- alternate-screen and mouse modes remain owned by the same window authority.

Bracketed paste sanitizes an embedded end marker before framing the payload, so
clipboard content cannot terminate paste mode early.

'''
    if section in text:
        raise RuntimeError("architecture section already present")
    text = replace_once(text, anchor, section + anchor, "document terminal modes")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_ansi()
    patch_terminal()
    patch_tests()
    patch_architecture()
    print("terminal VT mode hardening applied")


if __name__ == "__main__":
    main()

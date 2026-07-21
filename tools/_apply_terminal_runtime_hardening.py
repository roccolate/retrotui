#!/usr/bin/env python3
"""Apply the focused terminal/runtime hardening cut exactly once."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8", newline="\n")


def _replace_once(path: str, old: str, new: str) -> None:
    text = _read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one exact match, found {count}")
    _write(path, text.replace(old, new, 1))


def _regex_replace_once(path: str, pattern: str, replacement: str) -> None:
    text = _read(path)
    updated, count = re.subn(
        pattern,
        lambda _match: replacement,
        text,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, found {count}")
    _write(path, updated)


def _insert_before_once(path: str, marker: str, block: str) -> None:
    text = _read(path)
    if block.strip() in text:
        raise RuntimeError(f"{path}: block already present")
    count = text.count(marker)
    if count != 1:
        raise RuntimeError(f"{path}: expected one insertion marker, found {count}")
    _write(path, text.replace(marker, block + marker, 1))


def harden_ansi_parser() -> None:
    path = "retrotui/core/ansi.py"
    _replace_once(
        path,
        "        self.state = 'TEXT' # TEXT, ESC, CSI, OSC\n",
        "        self.state = 'TEXT' # TEXT, ESC, CSI, OSC, OSC_ESC, CHARSET\n",
    )

    _regex_replace_once(
        path,
        r"            elif self\.state == 'ESC':\n"
        r"                if getattr\(self, '_osc_in_esc', False\):.*?"
        r"                if ch == '\[':\n",
        "            elif self.state == 'ESC':\n"
        "                if ch == '[':\n",
    )

    _regex_replace_once(
        path,
        r"            elif self\.state == 'OSC':\n.*?"
        r"            elif self\.state == 'CHARSET':\n",
        "            elif self.state == 'OSC':\n"
        "                if ch == '\\x07':\n"
        "                    self.state = 'TEXT'\n"
        "                elif ch == '\\x1b':\n"
        "                    # ST is the two-byte sequence ESC + backslash.\n"
        "                    self.state = 'OSC_ESC'\n"
        "\n"
        "            elif self.state == 'OSC_ESC':\n"
        "                if ch == '\\\\' or ch == '\\x07':\n"
        "                    self.state = 'TEXT'\n"
        "                elif ch != '\\x1b':\n"
        "                    # A non-terminating ESC is consumed and OSC continues.\n"
        "                    self.state = 'OSC'\n"
        "\n"
        "            elif self.state == 'CHARSET':\n",
    )


def isolate_window_close_hooks() -> None:
    path = "retrotui/core/window_manager.py"
    _replace_once(
        path,
        "                except _WINDOW_CLOSE_HOOK_ERRORS:\n"
        "                    LOGGER.debug('Window close request failed for %r', win, exc_info=True)\n",
        "                except Exception:  # Window/plugin boundary: isolate extension code.\n"
        "                    LOGGER.debug('Window close request failed for %r', win, exc_info=True)\n",
    )
    _replace_once(
        path,
        "            except _WINDOW_CLOSE_HOOK_ERRORS:\n"
        "                LOGGER.debug('Window close hook failed for %r', win, exc_info=True)\n",
        "            except Exception:  # Window/plugin boundary: isolate extension code.\n"
        "                LOGGER.debug('Window close hook failed for %r', win, exc_info=True)\n",
    )


def optimize_terminal_scrollback_probe() -> None:
    path = "retrotui/apps/terminal.py"
    _replace_once(
        path,
        "        prev_total = len(self._all_lines())\n"
        "        prev_offset = self.scrollback_offset\n",
        "        prev_offset = self.scrollback_offset\n"
        "        prev_total = self._all_lines_count() if prev_offset > 0 else 0\n",
    )


def add_regressions() -> None:
    _insert_before_once(
        "tests/test_ansi_basic.py",
        "\n\nif __name__ == '__main__':",
        r'''

    def test_osc_backslashes_remain_payload_until_bel_or_st(self):
        state = AnsiStateMachine()
        events = list(state.parse_chunk("\x1b]0;C:\\Users\\rocco\x07X"))
        self.assertEqual(
            [data for kind, data, _attr in events if kind == "TEXT"],
            ["X"],
        )

        split = AnsiStateMachine()
        self.assertEqual(list(split.parse_chunk("\x1b]0;title\x1b")), [])
        self.assertEqual(split.state, "OSC_ESC")
        self.assertEqual(list(split.parse_chunk("\\")), [])
        self.assertEqual(split.state, "TEXT")
        self.assertEqual(list(split.parse_chunk("Y")), [("TEXT", "Y", 0)])
''',
    )

    _insert_before_once(
        "tests/test_window_manager.py",
        "\n\nif __name__ == \"__main__\":",
        r'''

    def test_custom_request_close_exception_is_isolated(self):
        class PluginCloseError(Exception):
            pass

        wm = WindowManager(None)
        win = make_win("plugin")
        win.request_close = lambda: (_ for _ in ()).throw(PluginCloseError("boom"))
        wm.windows = [win]

        self.assertFalse(wm.close_window(win))
        self.assertIn(win, wm.windows)
        self.assertFalse(getattr(win, "closed", False))

    def test_custom_close_exception_is_isolated(self):
        class PluginCloseError(Exception):
            pass

        wm = WindowManager(None)
        win = make_win("plugin")
        win.close = lambda: (_ for _ in ()).throw(PluginCloseError("boom"))
        wm.windows = [win]

        self.assertFalse(wm.close_window(win))
        self.assertIn(win, wm.windows)
''',
    )

    _insert_before_once(
        "tests/test_terminal_component.py",
        "\n\nif __name__ == \"__main__\":",
        r'''

    def test_consume_output_at_tail_does_not_materialize_all_lines(self):
        win = self._make_window()
        win.scrollback_offset = 0

        with mock.patch.object(
            win,
            "_all_lines",
            side_effect=AssertionError("tail output must not rebuild scrollback"),
        ):
            win._consume_output("X")

        self.assertEqual(self._get_text(win), "X")
''',
    )


def verify_source_shape() -> None:
    ansi = _read("retrotui/core/ansi.py")
    assert "_osc_in_esc" not in ansi
    assert "elif self.state == 'OSC_ESC':" in ansi
    assert "if ch == '\\\\' or ch == '\\x07':" in ansi

    manager = _read("retrotui/core/window_manager.py")
    assert manager.count("Window/plugin boundary: isolate extension code.") == 2

    terminal = _read("retrotui/apps/terminal.py")
    assert "prev_total = len(self._all_lines())" not in terminal
    assert "prev_total = self._all_lines_count() if prev_offset > 0 else 0" in terminal


if __name__ == "__main__":
    harden_ansi_parser()
    isolate_window_close_hooks()
    optimize_terminal_scrollback_probe()
    add_regressions()
    verify_source_shape()
    print("Applied terminal/runtime hardening cut.")

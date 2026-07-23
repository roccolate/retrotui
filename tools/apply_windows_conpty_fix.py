"""Apply the verified pywinpty read adapter, tests, and restore CI."""

from pathlib import Path


def replace_once(path, old, new):
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "retrotui/core/terminal_session.py",
    '''        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._pending_write = bytearray()
''',
    '''        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._pending_windows_output = bytearray()
        self._pending_write = bytearray()
''',
)

replace_once(
    "retrotui/core/terminal_session.py",
    '''    def _read_windows(self, max_bytes=4096):
        """Read available output from Windows ConPTY."""
        try:
            data = self._win_pty.read(max_bytes, blocking=False)
        except Exception:
            data = None
        if not data:
            return ""
        if isinstance(data, bytes):
            return self._decoder.decode(data)
        return data
''',
    '''    def _read_windows(self, max_bytes=4096):
        """Read Windows ConPTY output without dropping data over the tick budget."""
        max_bytes = max(1, int(max_bytes))
        if not self._pending_windows_output:
            try:
                try:
                    data = self._win_pty.read(blocking=False)
                except TypeError:
                    data = self._win_pty.read(False)
            except Exception:
                data = None

            if data:
                if isinstance(data, bytes):
                    self._pending_windows_output.extend(data)
                else:
                    self._pending_windows_output.extend(
                        str(data).encode("utf-8", errors="replace")
                    )

        if not self._pending_windows_output:
            return ""

        chunk = bytes(self._pending_windows_output[:max_bytes])
        del self._pending_windows_output[:max_bytes]
        return self._decoder.decode(chunk)
''',
)

replace_once(
    "retrotui/core/terminal_session.py",
    '''            self._win_pty = None
            self._pending_write.clear()
            self.running = False
''',
    '''            self._win_pty = None
            self._pending_windows_output.clear()
            self._pending_write.clear()
            self.running = False
''',
)

replace_once(
    "retrotui/core/terminal_session.py",
    '''        self._pending_write.clear()
        # Keep the logical liveness state honest when the child could not be
''',
    '''        self._pending_windows_output.clear()
        self._pending_write.clear()
        # Keep the logical liveness state honest when the child could not be
''',
)

replace_once(
    "tests/test_terminal_session.py",
    '''        result = session.read()
        self.assertEqual(result, "hello")

    def test_read_windows_empty(self):
''',
    '''        result = session.read()
        self.assertEqual(result, "hello")
        session._win_pty.read.assert_called_once_with(blocking=False)

    def test_read_windows_retains_overflow_for_next_tick(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.read.return_value = "abcdef"
        session.running = True

        self.assertEqual(session.read(max_bytes=3, max_total_bytes=3), "abc")
        self.assertEqual(session.read(max_bytes=3, max_total_bytes=3), "def")
        session._win_pty.read.assert_called_once_with(blocking=False)

    def test_read_windows_supports_positional_legacy_flag(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.read.side_effect = [TypeError("keyword"), b"ok"]
        session.running = True

        self.assertEqual(session.read(), "ok")
        self.assertEqual(
            session._win_pty.read.call_args_list,
            [mock.call(blocking=False), mock.call(False)],
        )

    def test_read_windows_empty(self):
''',
)

replace_once(
    "tests/test_terminal_session.py",
    '''        session._win_pty = backend
        session.running = True

        self.assertTrue(session.close())
''',
    '''        session._win_pty = backend
        session._pending_windows_output.extend(b"pending")
        session.running = True

        self.assertTrue(session.close())
''',
)

replace_once(
    "tests/test_terminal_session.py",
    '''        self.assertIsNone(session._win_pty)
        self.assertFalse(session.running)

    def test_send_signal_windows_interrupt(self):
''',
    '''        self.assertIsNone(session._win_pty)
        self.assertEqual(session._pending_windows_output, bytearray())
        self.assertFalse(session.running)

    def test_send_signal_windows_interrupt(self):
''',
)

workflow = Path(".github/workflows/ci.yml")
text = workflow.read_text(encoding="utf-8")
write_permissions = "permissions:\n  contents: write\n"
if text.count(write_permissions) != 1:
    raise RuntimeError("workflow: expected write permissions exactly once")
text = text.replace(write_permissions, "permissions:\n  contents: read\n", 1)
start_marker = "  apply-windows-terminal-fix:\n"
end_marker = "  quality:\n"
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("workflow: migration job boundaries not found")
workflow.write_text(text[:start] + text[end:], encoding="utf-8")

print("Windows ConPTY compatibility fix applied")

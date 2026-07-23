"""Apply the verified pywinpty text-write adapter and focused tests."""

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
    '''    def _write_windows(self, data):
        """Write one queued chunk to Windows ConPTY."""
        payload = data.encode("utf-8", errors="replace") if isinstance(data, str) else bytes(data)
        try:
            result = self._win_pty.write(payload)
        except OSError:
            self._pending_write.clear()
            self.running = False
            return 0
        if isinstance(result, int):
            return max(0, min(result, len(payload)))
        return len(payload)
''',
    '''    def _write_windows(self, data):
        """Write a UTF-8-safe text chunk through the pywinpty string API."""
        payload = data.encode("utf-8", errors="replace") if isinstance(data, str) else bytes(data)
        if not payload:
            return 0

        consumed = len(payload)
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            if exc.reason == "unexpected end of data" and exc.end == len(payload):
                consumed = exc.start
                if consumed <= 0:
                    return 0
                text = payload[:consumed].decode("utf-8", errors="replace")
            else:
                text = payload.decode("utf-8", errors="replace")

        try:
            result = self._win_pty.write(text)
        except OSError:
            self._pending_write.clear()
            self.running = False
            return 0
        if not isinstance(result, int):
            return consumed

        written = max(0, int(result))
        if written >= len(text):
            return consumed
        return len(text[:written].encode("utf-8"))
''',
)

replace_once(
    "retrotui/core/terminal_session.py",
    "                self._win_pty.write(b'\\x03')\n",
    "                self._win_pty.write('\\x03')\n",
)

replace_once(
    "tests/test_terminal_session.py",
    '''        count = session.write("hello")
        self.assertEqual(count, 5)
        session._win_pty.write.assert_called_once_with(b"hello")

    def test_write_windows_oserror_marks_not_running(self):
''',
    '''        count = session.write("hello")
        self.assertEqual(count, 5)
        session._win_pty.write.assert_called_once_with("hello")

    def test_write_windows_unicode_uses_text_and_byte_count(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session._win_pty.write.return_value = 1
        session.running = True

        count = session.write("é")

        self.assertEqual(count, len("é".encode("utf-8")))
        session._win_pty.write.assert_called_once_with("é")
        self.assertEqual(session.pending_write_bytes, 0)

    def test_write_windows_waits_for_complete_utf8_character(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session.running = True
        session._pending_write.extend("é".encode("utf-8"))

        self.assertEqual(session.flush_pending_writes(max_total_bytes=1), 0)
        session._win_pty.write.assert_not_called()
        self.assertEqual(session.pending_write_bytes, 2)

        self.assertEqual(session.flush_pending_writes(max_total_bytes=2), 2)
        session._win_pty.write.assert_called_once_with("é")
        self.assertEqual(session.pending_write_bytes, 0)

    def test_write_windows_oserror_marks_not_running(self):
''',
)

replace_once(
    "tests/test_terminal_session.py",
    "        session._win_pty.write.assert_called_once_with(b'\\x03')\n",
    "        session._win_pty.write.assert_called_once_with('\\x03')\n",
)

print("Windows ConPTY text-write compatibility fix applied")

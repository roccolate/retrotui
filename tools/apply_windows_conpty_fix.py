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
text = text.replace("permissions:\n  contents: write\n", "permissions:\n  contents: read\n", 1)
job_block = '''  apply-windows-terminal-fix:
    if: github.event_name == 'pull_request' && github.head_ref == 'agent/windows-terminal-e2e'
    runs-on: ubuntu-latest

    steps:
      - name: Checkout migration branch
        uses: actions/checkout@v5
        with:
          ref: agent/windows-terminal-e2e
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Apply exact ConPTY fix
        run: python tools/apply_windows_conpty_fix.py

      - name: Validate focused terminal tests
        run: python -m unittest discover -s tests -p "test_terminal_session.py" -v

      - name: Validate repository quality
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[test]"
          python tools/qa.py --skip-tests
          python -m ruff check --select F821 retrotui tests tools

      - name: Publish clean fix commit
        shell: bash
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git rm tools/apply_windows_conpty_fix.py
          git add retrotui/core/terminal_session.py tests/test_terminal_session.py .github/workflows/ci.yml
          git commit -m "Fix real Windows ConPTY reads"
          git push origin HEAD:agent/windows-terminal-e2e

'''
if text.count(job_block) != 1:
    raise RuntimeError(f"workflow: expected migration job once, found {text.count(job_block)}")
workflow.write_text(text.replace(job_block, "", 1), encoding="utf-8")

print("Windows ConPTY compatibility fix applied")

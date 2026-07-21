"""Update the legacy Windows close test to the verified close contract."""

from pathlib import Path


path = Path("tests/test_terminal_session.py")
text = path.read_text(encoding="utf-8")
old = '''    def test_close_windows(self):
        session = self.mod.TerminalSession()
        session._win_pty = mock.MagicMock()
        session.running = True

        session.close()
        self.assertIsNone(session._win_pty)
        self.assertFalse(session.running)
'''
new = '''    def test_close_windows(self):
        session = self.mod.TerminalSession()
        backend = mock.MagicMock()
        backend.isalive.return_value = False
        session._win_pty = backend
        session.running = True

        self.assertTrue(session.close())
        backend.close.assert_called_once_with(force=True)
        backend.isalive.assert_called_once_with()
        self.assertIsNone(session._win_pty)
        self.assertFalse(session.running)
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one legacy Windows close test, found {text.count(old)}")
path.write_text(text.replace(old, new), encoding="utf-8")

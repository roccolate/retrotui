"""Real Windows ConPTY smoke test for the embedded terminal backend."""

from __future__ import annotations

import os
import sys
import time
import unittest
import uuid

from retrotui.core.terminal_session import TerminalSession


@unittest.skipUnless(sys.platform == "win32", "requires a real Windows host")
@unittest.skipUnless(
    os.environ.get("RETROTUI_WINDOWS_E2E") == "1",
    "set RETROTUI_WINDOWS_E2E=1 to run the real ConPTY smoke test",
)
class WindowsTerminalE2ETests(unittest.TestCase):
    """Exercise cmd.exe through the same pywinpty backend used by RetroTUI."""

    def setUp(self):
        self.session = None

    def tearDown(self):
        session = self.session
        if session is None or session._win_pty is None:
            return
        try:
            session.close()
        except Exception:
            backend = session._win_pty
            close_method = getattr(backend, "close", None)
            if callable(close_method):
                try:
                    close_method(force=True)
                except Exception:
                    pass

    def _read_until(self, marker, timeout=15.0):
        deadline = time.monotonic() + timeout
        chunks = []
        while time.monotonic() < deadline:
            chunk = self.session.read(max_bytes=4096, max_total_bytes=4096)
            if chunk:
                chunks.append(chunk)
                output = "".join(chunks)
                if marker in output:
                    return output
            if not self.session.running:
                break
            time.sleep(0.05)

        output = "".join(chunks)
        self.fail(
            f"cmd.exe did not emit {marker!r} before timeout; "
            f"captured output: {output!r}"
        )

    def test_cmd_round_trip_resize_and_clean_close(self):
        token = uuid.uuid4().hex
        env_name = "RETROTUI_WINDOWS_E2E_TOKEN"
        first_marker = f"RETROTUI_E2E_{token}"
        resized_marker = f"RETROTUI_RESIZED_{token}"

        self.session = TerminalSession(
            cwd=os.getcwd(),
            env={env_name: token},
            cols=80,
            rows=24,
        )
        self.assertTrue(TerminalSession.is_supported())

        self.session.start()
        self.assertTrue(self.session.running)
        self.assertIsNotNone(self.session._win_pty)

        first_command = f"echo RETROTUI_E2E_%{env_name}%\r\n"
        self.assertEqual(self.session.write(first_command), len(first_command))
        self._read_until(first_marker)

        self.session.resize(100, 35)
        self.assertEqual((self.session.cols, self.session.rows), (100, 35))

        resized_command = f"echo RETROTUI_RESIZED_%{env_name}%\r\n"
        self.assertEqual(self.session.write(resized_command), len(resized_command))
        self._read_until(resized_marker)

        self.assertTrue(
            self.session.close(),
            "Windows ConPTY child did not stop cleanly",
        )
        self.assertFalse(self.session.running)
        self.assertIsNone(self.session._win_pty)


if __name__ == "__main__":
    unittest.main()

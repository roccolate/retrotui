#!/usr/bin/env python3
"""Apply one focused, regression-tested hardening batch to bundled apps."""

from pathlib import Path


def replace_exact(path: str, old: str, new: str, count: int = 1) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    found = text.count(old)
    if found < count:
        raise RuntimeError(
            f"expected at least {count} occurrence(s) in {path}, found {found}: {old[:100]!r}"
        )
    file_path.write_text(text.replace(old, new, count), encoding="utf-8")


def insert_before_final_main(path: str, block: str) -> None:
    marker = '\n\nif __name__ == "__main__":\n'
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if marker not in text:
        raise RuntimeError(f"final unittest marker not found in {path}")
    file_path.write_text(text.replace(marker, block + marker, 1), encoding="utf-8")


def main() -> None:
    # Settings must preserve the base Window lifecycle contract.
    replace_exact(
        "retrotui/apps/settings.py",
        '''    def close(self):
        """Revert preview state when window closes without save/cancel."""
        if not self._finalized:
            self._revert_runtime()
        self._finalized = True
''',
        '''    def close(self):
        """Revert preview state and release resources owned by the window."""
        if not self._finalized:
            self._revert_runtime()
        self._finalized = True
        return super().close()
''',
    )

    # Clipboard polling must really consult the system backend, but only at a
    # bounded cadence. Closing must also release the base worker scope.
    replace_exact(
        "retrotui/apps/clipboard_viewer.py",
        "import curses\nfrom typing import List\n",
        "import curses\nimport time\nfrom typing import List\n",
    )
    replace_exact(
        "retrotui/apps/clipboard_viewer.py",
        "class ClipboardViewerWindow(Window):\n    def __init__(self, x, y, w, h, history_size=10):\n",
        "class ClipboardViewerWindow(Window):\n    wants_periodic_tick = True\n    POLL_INTERVAL_SECONDS = 0.5\n\n    def __init__(self, x, y, w, h, history_size=10):\n",
    )
    replace_exact(
        "retrotui/apps/clipboard_viewer.py",
        "        self._unsub_clipboard = None\n        self._refresh_from_clipboard()\n",
        "        self._unsub_clipboard = None\n        self._last_poll = 0.0\n        self._refresh_from_clipboard()\n",
    )
    replace_exact(
        "retrotui/apps/clipboard_viewer.py",
        '''    def _refresh_from_clipboard(self):
        text = paste_text(sync_system=False)
''',
        '''    def _refresh_from_clipboard(self, *, sync_system=False):
        text = paste_text(sync_system=sync_system)
''',
    )
    replace_exact(
        "retrotui/apps/clipboard_viewer.py",
        '''    def close(self):
        """Unsubscribe from the event bus on close."""
        if self._unsub_clipboard:
            self._unsub_clipboard()
            self._unsub_clipboard = None
''',
        '''    def close(self):
        """Unsubscribe from events and release resources owned by the window."""
        if self._unsub_clipboard:
            self._unsub_clipboard()
            self._unsub_clipboard = None
        return super().close()
''',
    )
    replace_exact(
        "retrotui/apps/clipboard_viewer.py",
        '''    def tick(self):
        """Poll system clipboard as a fallback outside the render path.

        The event bus only fires for internal copies; external clipboard
        changes (other apps) need polling.
        """
        before = self.history[:1] if self.history else None
        self._refresh_from_clipboard()
        after = self.history[:1] if self.history else None
        return before != after
''',
        '''    def tick(self):
        """Poll the system clipboard at a bounded fallback cadence."""
        now = time.monotonic()
        if (now - self._last_poll) < self.POLL_INTERVAL_SECONDS:
            return False
        self._last_poll = now
        before = self.history[:1] if self.history else None
        self._refresh_from_clipboard(sync_system=True)
        after = self.history[:1] if self.history else None
        return before != after
''',
    )

    # Tail mode needs to advertise its periodic scheduling requirement.
    replace_exact(
        "retrotui/apps/logviewer.py",
        "    _log_colors_ready = False\n\n    def __init__(self, x, y, w, h, filepath=None):\n",
        '''    _log_colors_ready = False

    @property
    def wants_periodic_tick(self):
        """Request periodic scheduling only while actively following a file."""
        return bool(self.filepath and self.follow_mode and not self.freeze_scroll)

    def __init__(self, x, y, w, h, filepath=None):
''',
    )

    # Preserve the completed SSID independently from transient connection state.
    replace_exact(
        "retrotui/apps/wifi_manager.py",
        "        self._connect_in_progress = False\n        self._connect_result = None\n",
        "        self._connect_in_progress = False\n        self._connect_result = None\n        self._connect_result_ssid = None\n",
    )
    replace_exact(
        "retrotui/apps/wifi_manager.py",
        '''            with self._connect_lock:
                self._connect_in_progress = False
                self._connect_result = None
                self._connecting_ssid = None
            return
''',
        '''            with self._connect_lock:
                self._connect_in_progress = False
                self._connect_result = None
                self._connect_result_ssid = None
                self._connecting_ssid = None
            return
''',
    )
    replace_exact(
        "retrotui/apps/wifi_manager.py",
        '''        with self._connect_lock:
            self._connect_in_progress = False
            self._connect_result = (success, error_message)
            self._connecting_ssid = None
''',
        '''        with self._connect_lock:
            connected_ssid = self._connecting_ssid
            self._connect_in_progress = False
            self._connect_result = (success, error_message)
            self._connect_result_ssid = connected_ssid
            self._connecting_ssid = None
''',
    )
    replace_exact(
        "retrotui/apps/wifi_manager.py",
        '''        with self._connect_lock:
            self._connect_in_progress = False
            self._connect_result = None
            self._connecting_ssid = None
        self._dialog = None
''',
        '''        with self._connect_lock:
            self._connect_in_progress = False
            self._connect_result = None
            self._connect_result_ssid = None
            self._connecting_ssid = None
        self._dialog = None
''',
    )
    replace_exact(
        "retrotui/apps/wifi_manager.py",
        '''        with self._connect_lock:
            result = self._connect_result
            if result is not None:
                self._connect_result = None
                success, error_message = result
                if success:
                    # Use the stored SSID (captured at connect time) so
                    # the message doesn't depend on the prefix of the
                    # previous status string.
                    ssid = self._connecting_ssid or self._status_msg
                    self._status_msg = f"Connected to {ssid}."
                else:
                    self._status_msg = "Connection failed."
                if not success and error_message:
                    self._status_msg = f"Connection failed: {error_message[:60]}"
                changed = True
''',
        '''        with self._connect_lock:
            result = self._connect_result
            if result is not None:
                result_ssid = self._connect_result_ssid
                self._connect_result = None
                self._connect_result_ssid = None
                success, error_message = result
                if success:
                    self._status_msg = (
                        f"Connected to {result_ssid}." if result_ssid else "Connected."
                    )
                else:
                    self._status_msg = "Connection failed."
                if not success and error_message:
                    self._status_msg = f"Connection failed: {error_message[:60]}"
                changed = True
''',
    )

    # RetroNet must never retry with certificate verification disabled and must
    # place a hard upper bound on response memory use.
    replace_exact(
        "retrotui/apps/retronet.py",
        "_BTN_RE = re.compile(r'\\[BT\\](.*?)\\[/BT\\]')\n\n_URL_SANITIZE_ERRORS = (\n",
        '''_BTN_RE = re.compile(r'\\[BT\\](.*?)\\[/BT\\]')


class _ResponseTooLargeError(Exception):
    """Raised when a network response exceeds the configured limit."""


_URL_SANITIZE_ERRORS = (
''',
    )
    replace_exact(
        "retrotui/apps/retronet.py",
        "    ConnectionError,\n)\n",
        "    ConnectionError,\n    _ResponseTooLargeError,\n)\n",
    )
    replace_exact(
        "retrotui/apps/retronet.py",
        "_MAX_HISTORY = 200\n",
        "_MAX_HISTORY = 200\nMAX_RESPONSE_BYTES = 2 * 1024 * 1024\n",
    )
    replace_exact(
        "retrotui/apps/retronet.py",
        '''            context = ssl.create_default_context()
            ssl_warning = False

            req = urllib.request.Request(url, headers=headers)
            try:
                response = urllib.request.urlopen(req, timeout=10, context=context)
            except ssl.SSLError as ssl_exc:
                # The first TLS error falls back to an unverified context.
                # That's a meaningful security downgrade (phishing / MITM
                # exposure) and the user deserves to know that *every
                # future request in this session* will share the relaxed
                # trust — so surface a strong warning instead of the
                # previous single-line banner.
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                response = urllib.request.urlopen(req, timeout=10, context=context)
                ssl_warning = (
                    f"[SSL: certificate verification failed ({ssl_exc.reason or ssl_exc}). "
                    f"Subsequent requests in this session are also unverified.]"
                )
''',
        '''            context = ssl.create_default_context()
            req = urllib.request.Request(url, headers=headers)
            response = urllib.request.urlopen(req, timeout=10, context=context)
''',
    )
    replace_exact(
        "retrotui/apps/retronet.py",
        '''                charset = response.info().get_content_charset() or 'utf-8'
                raw_html = response.read().decode(charset, errors='ignore')
''',
        '''                charset = response.info().get_content_charset() or 'utf-8'
                raw_bytes = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw_bytes) > MAX_RESPONSE_BYTES:
                    raise _ResponseTooLargeError(
                        f"Response exceeds {MAX_RESPONSE_BYTES // (1024 * 1024)} MiB limit."
                    )
                raw_html = raw_bytes.decode(charset, errors='ignore')
''',
    )
    replace_exact(
        "retrotui/apps/retronet.py",
        '''            if ssl_warning:
                parsed.insert(0, RichLine("[SSL: certificate verification failed — showing unverified content]", self.attr_error))
            if cancel_event.is_set():
''',
        '''            if cancel_event.is_set():
''',
    )

    # Regression tests.
    insert_before_final_main(
        "tests/test_settings_component.py",
        '''
    def test_close_chains_base_window_cleanup(self):
        win = self._make_window()
        with mock.patch.object(self.settings_mod.Window, "close", return_value=True) as base_close:
            self.assertTrue(win.close())
        base_close.assert_called_once_with()
''',
    )
    insert_before_final_main(
        "tests/test_clipboard_viewer.py",
        '''
    def test_tick_syncs_system_clipboard_at_bounded_cadence(self):
        win = self.mod.ClipboardViewerWindow(0, 0, 40, 12)
        win.history = []
        win._last_poll = 0.0
        with mock.patch.object(self.mod.time, "monotonic", side_effect=[10.0, 10.1]), mock.patch.object(
            self.mod, "paste_text", return_value="external"
        ) as paste_text:
            self.assertTrue(win.tick())
            self.assertFalse(win.tick())
        paste_text.assert_called_once_with(sync_system=True)

    def test_close_chains_base_window_cleanup(self):
        win = self.mod.ClipboardViewerWindow(0, 0, 40, 12)
        with mock.patch.object(self.mod.Window, "close", return_value=True) as base_close:
            self.assertTrue(win.close())
        base_close.assert_called_once_with()
''',
    )
    insert_before_final_main(
        "tests/test_logviewer_component.py",
        '''
    def test_periodic_tick_contract_tracks_follow_state(self):
        win = self._make_window()
        self.assertFalse(win.wants_periodic_tick)
        win.filepath = "/tmp/demo.log"
        self.assertTrue(win.wants_periodic_tick)
        win.freeze_scroll = True
        self.assertFalse(win.wants_periodic_tick)
        win.freeze_scroll = False
        win.follow_mode = False
        self.assertFalse(win.wants_periodic_tick)
''',
    )
    insert_before_final_main(
        "tests/test_wifi_manager.py",
        '''
    def test_tick_reports_the_completed_connection_ssid(self):
        with mock.patch.object(self.mod.shutil, "which", return_value=None):
            win = self.mod.WifiManagerWindow(0, 0, 60, 20)
        win._connect_in_progress = True
        win._connecting_ssid = "Cafe Network"
        with mock.patch.object(win, "refresh"):
            win._finish_connect(True, "")
        self.assertIsNone(win._connecting_ssid)
        self.assertTrue(win.tick())
        self.assertEqual(win._status_msg, "Connected to Cafe Network.")
''',
    )
    replace_exact(
        "tests/test_retronet.py",
        "import sys\n",
        "import sys\nimport ssl\n",
    )
    replace_exact(
        "tests/test_retronet.py",
        "from retrotui.apps.retronet import RetroNetWindow, RichLine, InteractiveSpan\n",
        "from retrotui.apps.retronet import RetroNetWindow, RichLine, InteractiveSpan, MAX_RESPONSE_BYTES\n",
    )
    insert_before_final_main(
        "tests/test_retronet.py",
        '''
    @mock.patch('urllib.request.urlopen')
    def test_fetch_thread_does_not_retry_invalid_tls(self, mock_urlopen):
        mock_urlopen.side_effect = ssl.SSLError("certificate verify failed")
        self.win._fetch_thread("https://invalid.example", self.win.active_tab_idx)
        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertFalse(self.win.is_loading)
        self.assertTrue(any("certificate verify failed" in line.text for line in self.win.content))

    @mock.patch('urllib.request.urlopen')
    def test_fetch_thread_rejects_oversized_response(self, mock_urlopen):
        mock_response = mock.MagicMock()
        mock_response.read.return_value = b"x" * (MAX_RESPONSE_BYTES + 1)
        mock_response.info().get_content_charset.return_value = 'utf-8'
        mock_urlopen.return_value = mock_response
        self.win._fetch_thread("https://large.example", self.win.active_tab_idx)
        mock_response.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)
        self.assertFalse(self.win.is_loading)
        self.assertTrue(any("exceeds" in line.text for line in self.win.content))
''',
    )


if __name__ == "__main__":
    main()

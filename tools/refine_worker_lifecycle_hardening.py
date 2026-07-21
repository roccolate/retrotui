#!/usr/bin/env python3
"""Refine the generated worker lifecycle batch against legacy contracts."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"expected refinement block not found in {relative_path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_app_cleanup_legacy_fallback() -> None:
    replace_once(
        "retrotui/core/app.py",
        '''            file_ops = getattr(self, "_file_ops", None)
            if file_ops is not None:
                stopped = file_ops.shutdown(
                    timeout=self.BACKGROUND_OPERATION_JOIN_TIMEOUT
                )
                if not stopped:
                    success = False
                    LOGGER.warning(
                        "File operation worker did not stop within %.1fs during shutdown.",
                        self.BACKGROUND_OPERATION_JOIN_TIMEOUT,
                    )

            for win in list(self.windows):
''',
        '''            file_ops = getattr(self, "_file_ops", None)
            if file_ops is not None:
                stopped = file_ops.shutdown(
                    timeout=self.BACKGROUND_OPERATION_JOIN_TIMEOUT
                )
                if not stopped:
                    success = False
                    LOGGER.warning(
                        "File operation worker did not stop within %.1fs during shutdown.",
                        self.BACKGROUND_OPERATION_JOIN_TIMEOUT,
                    )
            else:
                # Compatibility for partially constructed app instances and
                # pre-WorkerScope background-operation state.
                op_state = getattr(self, "_background_operation", None)
                thread = op_state.get("thread") if isinstance(op_state, dict) else None
                if thread is not None and thread.is_alive():
                    thread.join(timeout=self.BACKGROUND_OPERATION_JOIN_TIMEOUT)
                    if thread.is_alive():
                        success = False
                        LOGGER.warning(
                            "Legacy background operation did not finish within %.1fs during shutdown.",
                            self.BACKGROUND_OPERATION_JOIN_TIMEOUT,
                        )

            for win in list(self.windows):
''',
    )


def patch_wifi_legacy_calls() -> None:
    replace_once(
        "retrotui/apps/wifi_manager.py",
        '''    def _scan_worker(self, cancel_event):
        new_networks = []
''',
        '''    def _scan_worker(self, cancel_event=None):
        # Preserve direct helper calls used by integrations/tests while the
        # runtime path receives the owner scope's cancellation event.
        if cancel_event is None:
            cancel_event = threading.Event()
        new_networks = []
''',
    )
    replace_once(
        "retrotui/apps/wifi_manager.py",
        '''    def _connect_worker(self, cancel_event, ssid, password):
        if cancel_event.is_set():
''',
        '''    def _connect_worker(self, cancel_event, ssid=None, password=None):
        # Legacy direct call: _connect_worker(ssid, password).
        if not callable(getattr(cancel_event, "is_set", None)):
            password = ssid
            ssid = cancel_event
            cancel_event = threading.Event()
        if cancel_event.is_set():
''',
    )


def patch_retronet_legacy_calls() -> None:
    replace_once(
        "retrotui/apps/retronet.py",
        '''    def _fetch_thread(self, cancel_event, url, tab_id, generation):
        if cancel_event.is_set():
            return
        try:
''',
        '''    def _fetch_thread(self, cancel_event, url=None, tab_id=None, generation=None):
        # Legacy direct call: _fetch_thread(url, tab_index). Resolve that
        # index once to the stable request identity used by the runtime path.
        if not callable(getattr(cancel_event, "is_set", None)):
            legacy_url = cancel_event
            legacy_tab_idx = url
            cancel_event = threading.Event()
            url = legacy_url
            with self._lock:
                try:
                    tab = self.tabs[int(legacy_tab_idx)]
                except (IndexError, TypeError, ValueError):
                    return
                tab_id = tab.tab_id
                generation = tab.load_generation
        if cancel_event.is_set():
            return
        try:
''',
    )


def patch_worker_tests() -> None:
    path = ROOT / "tests/test_worker_lifecycle.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "from retrotui.core.file_operations import FileOperationManager\n",
        "",
    )
    text = text.replace(
        '''        preview = FileManagerWindow.__new__(FileManagerWindow)
        Window.__init__(preview, "files", 0, 0, 20, 8)
        preview._preview_lock = threading.Lock()
''',
        '''        preview = FileManagerWindow.__new__(FileManagerWindow)
        preview._worker_scope = WorkerScope("file-preview-test")
        preview._preview_lock = threading.Lock()
''',
    )
    text = text.replace(
        '''        manager = FileOperationManager(app)
        release = threading.Event()
''',
        '''        from retrotui.core.file_operations import FileOperationManager

        manager = FileOperationManager(app)
        release = threading.Event()
''',
        1,
    )
    text = text.replace(
        '''        manager = FileOperationManager(app)
        self.assertTrue(manager.shutdown(timeout=0.0))
''',
        '''        from retrotui.core.file_operations import FileOperationManager

        manager = FileOperationManager(app)
        self.assertTrue(manager.shutdown(timeout=0.0))
''',
        1,
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_app_cleanup_legacy_fallback()
    patch_wifi_legacy_calls()
    patch_retronet_legacy_calls()
    patch_worker_tests()


if __name__ == "__main__":
    main()

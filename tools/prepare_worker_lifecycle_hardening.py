#!/usr/bin/env python3
"""Apply the worker ownership and shutdown hardening batch.

The file is temporary. A validation workflow packages the resulting tree, and
this applicator is removed from the final commit.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"expected block not found in {relative_path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_before(relative_path: str, marker: str, content: str) -> None:
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")
    if content in text:
        return
    if marker not in text:
        raise RuntimeError(f"insertion marker not found in {relative_path}")
    path.write_text(text.replace(marker, content + marker, 1), encoding="utf-8")


def write(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_worker_scope() -> None:
    write(
        "retrotui/core/worker_scope.py",
        '''"""Owned background worker lifecycle primitives.

A ``WorkerScope`` gives one component explicit ownership of every thread it
starts. Shutdown closes the scope, signals cooperative cancellation, prevents
new workers, and performs a bounded join. Workers that cannot be interrupted
must still consult ``cancel_event`` before publishing results back to their
owner.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any


LOGGER = logging.getLogger(__name__)


class WorkerScope:
    """Track worker threads owned by one runtime component."""

    def __init__(self, name: str, *, join_timeout: float = 0.25):
        self.name = str(name or "worker-scope")
        self.join_timeout = max(0.0, float(join_timeout))
        self._lock = threading.RLock()
        self._cancel_event = threading.Event()
        self._threads: set[threading.Thread] = set()
        self._closed = False

    @property
    def cancel_event(self) -> threading.Event:
        return self._cancel_event

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(thread.is_alive() for thread in self._threads)

    def start(
        self,
        target: Callable[..., Any],
        *args: Any,
        name: str | None = None,
        daemon: bool = True,
        **kwargs: Any,
    ) -> threading.Thread | None:
        """Start and track a worker, passing ``cancel_event`` first."""
        if not callable(target):
            raise TypeError("worker target must be callable")

        with self._lock:
            if self._closed:
                return None

            def _runner() -> None:
                current = threading.current_thread()
                try:
                    target(self._cancel_event, *args, **kwargs)
                except Exception:  # Worker boundary: isolate and retain diagnostics.
                    LOGGER.exception("Unhandled worker failure in scope %s", self.name)
                finally:
                    with self._lock:
                        self._threads.discard(current)

            thread = threading.Thread(
                target=_runner,
                name=name or f"retrotui-{self.name}",
                daemon=daemon,
            )
            self._threads.add(thread)
            try:
                thread.start()
            except Exception:
                self._threads.discard(thread)
                raise
            return thread

    def cancel(self) -> None:
        """Close the scope and signal cooperative cancellation once."""
        with self._lock:
            self._closed = True
            self._cancel_event.set()

    def join(self, timeout: float | None = None) -> tuple[threading.Thread, ...]:
        """Join owned workers within one shared deadline; return survivors."""
        wait_for = self.join_timeout if timeout is None else max(0.0, float(timeout))
        deadline = time.monotonic() + wait_for
        current = threading.current_thread()
        with self._lock:
            threads = tuple(self._threads)

        for thread in threads:
            if thread is current or not thread.is_alive():
                continue
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0.0:
                break
            thread.join(timeout=remaining)

        with self._lock:
            return tuple(
                thread
                for thread in self._threads
                if thread is not current and thread.is_alive()
            )

    def shutdown(
        self,
        timeout: float | None = None,
        *,
        require_stopped: bool = False,
    ) -> bool:
        """Cancel and bounded-join workers.

        ``require_stopped=False`` is appropriate for read-only window workers:
        the owner is logically closed immediately and late results are rejected.
        Global side-effecting operations use ``require_stopped=True`` so the app
        can report an incomplete physical shutdown.
        """
        self.cancel()
        survivors = self.join(timeout=timeout)
        if survivors:
            LOGGER.warning(
                "Worker scope %s still has %d live thread(s) after shutdown: %s",
                self.name,
                len(survivors),
                ", ".join(thread.name for thread in survivors),
            )
        return not survivors if require_stopped else True
''',
    )


def patch_window_base() -> None:
    replace_once(
        "retrotui/ui/window.py",
        "from ..utils import safe_addstr, draw_box, theme_attr\nfrom .menu import WindowMenu\n",
        "from ..utils import safe_addstr, draw_box, theme_attr\nfrom ..core.worker_scope import WorkerScope\nfrom .menu import WindowMenu\n",
    )
    replace_once(
        "retrotui/ui/window.py",
        "    CLOSE_BTN_OFFSET = 4\n",
        "    CLOSE_BTN_OFFSET = 4\n    WORKER_JOIN_TIMEOUT = 0.25\n",
    )
    replace_once(
        "retrotui/ui/window.py",
        "        self.id = Window._next_id\n        Window._next_id += 1\n        self.title = title\n",
        "        self.id = Window._next_id\n        Window._next_id += 1\n        self._worker_scope = WorkerScope(\n            f\"{self.__class__.__name__}:{self.id}\",\n            join_timeout=self.WORKER_JOIN_TIMEOUT,\n        )\n        self.title = title\n",
    )
    insert_before(
        "retrotui/ui/window.py",
        "    def close_button_pos(self):\n",
        '''    def _start_worker(self, target, *args, name=None, daemon=True, **kwargs):
        """Start a worker owned by this window.

        The target receives the window cancellation event as its first argument.
        """
        scope = getattr(self, "_worker_scope", None)
        if scope is None:
            scope = WorkerScope(
                f"{self.__class__.__name__}:{getattr(self, 'id', 'detached')}",
                join_timeout=self.WORKER_JOIN_TIMEOUT,
            )
            self._worker_scope = scope
        return scope.start(
            target,
            *args,
            name=name,
            daemon=daemon,
            **kwargs,
        )

    def worker_cancelled(self):
        """Return whether this window has entered logical shutdown."""
        scope = getattr(self, "_worker_scope", None)
        return bool(scope is not None and scope.cancel_event.is_set())

    def close(self):
        """Cancel all workers owned by this window.

        Window workers are required to reject late results after cancellation,
        so a blocked read-only worker does not keep the UI window registered.
        """
        scope = getattr(self, "_worker_scope", None)
        if scope is None:
            return True
        scope.shutdown(timeout=self.WORKER_JOIN_TIMEOUT, require_stopped=False)
        return True

''',
    )


def patch_app_cleanup() -> None:
    replace_once(
        "retrotui/core/app.py",
        "        self._shutdown_signal = None\n",
        "        self._shutdown_signal = None\n        self._cleanup_started = False\n        self._cleanup_complete = False\n",
    )
    replace_once(
        "retrotui/core/app.py",
        '''    def cleanup(self):
        """Restore terminal state."""
        self._restore_runtime_signal_handlers()
        op_state = getattr(self, '_background_operation', None)
        if op_state:
            thread = op_state.get('thread')
            if thread and thread.is_alive():
                thread.join(timeout=self.BACKGROUND_OPERATION_JOIN_TIMEOUT)
                if thread.is_alive():
                    LOGGER.warning(
                        'Background operation did not finish within %.1fs during shutdown.',
                        self.BACKGROUND_OPERATION_JOIN_TIMEOUT,
                    )
        for win in list(self.windows):
            self.window_mgr.close_window(win, force=True)
        if hasattr(self, '_notifications'):
            self._notifications.cleanup()
        if hasattr(self, '_event_bus'):
            self._event_bus.clear()
        disable_mouse_support()
''',
        '''    def cleanup(self):
        """Run one idempotent, ordered shutdown pass.

        Returns True when every side-effecting global worker and window cleanup
        hook confirmed completion. Terminal restoration still runs on failures.
        """
        if getattr(self, "_cleanup_complete", False):
            return True
        if getattr(self, "_cleanup_started", False):
            LOGGER.warning("Ignoring re-entrant RetroTUI cleanup request.")
            return False

        self._cleanup_started = True
        self.running = False
        success = True
        try:
            self._restore_runtime_signal_handlers()

            file_ops = getattr(self, "_file_ops", None)
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
                if not self.window_mgr.close_window(win, force=True):
                    success = False
                    LOGGER.warning("Window cleanup was not verified for %r", win)

            self.dialog = None
            self.context_menu = None
            if hasattr(self, "_notifications"):
                self._notifications.cleanup()
            if hasattr(self, "_event_bus"):
                self._event_bus.clear()
        finally:
            disable_mouse_support()
            self._cleanup_complete = True
            self._cleanup_started = False
        return success
''',
    )


def patch_file_operations() -> None:
    replace_once(
        "retrotui/core/file_operations.py",
        "from .dialog_workflow import DialogWorkflowId, bind_dialog\n",
        "from .dialog_workflow import DialogWorkflowId, bind_dialog\nfrom .worker_scope import WorkerScope\n",
    )
    replace_once(
        "retrotui/core/file_operations.py",
        '''        self._app = app
        # Initialise the state slot on the app if it is not already present.
        if not hasattr(self._app, '_background_operation'):
            self._app._background_operation = None
''',
        '''        self._app = app
        self._shutting_down = False
        self._worker_scope = WorkerScope(
            "file-operations",
            join_timeout=self.BACKGROUND_OPERATION_JOIN_TIMEOUT,
        )
        # Initialise the state slot on the app if it is not already present.
        if not hasattr(self._app, '_background_operation'):
            self._app._background_operation = None
''',
    )
    replace_once(
        "retrotui/core/file_operations.py",
        '''    def _start_background_operation(self, *, title, message, worker, source_win):
        """Run blocking filesystem operation in a worker thread and show progress."""
        state = getattr(self._app, '_background_operation', None)
        if state:
            return ActionResult(ActionType.ERROR, 'Another operation is already running.')
''',
        '''    def _start_background_operation(self, *, title, message, worker, source_win):
        """Run blocking filesystem operation in an owned worker scope."""
        if self._shutting_down or self._worker_scope.closed:
            return ActionResult(ActionType.ERROR, 'Application is shutting down.')
        state = getattr(self._app, '_background_operation', None)
        if state:
            return ActionResult(ActionType.ERROR, 'Another operation is already running.')
''',
    )
    replace_once(
        "retrotui/core/file_operations.py",
        '''        def _runner():
            try:
                result = worker()
            except _BACKGROUND_WORKER_ERRORS as exc:  # pragma: no cover - defensive worker path
                result = ActionResult(ActionType.ERROR, str(exc))
            # Publish the result together with the ``done`` flag under a
            # single lock so the main loop never observes a partial state.
            with op_lock:
                op_state['worker_result'] = result
                op_state['done'] = True

        thread = threading.Thread(target=_runner, name='retrotui-file-op', daemon=True)
        op_state['thread'] = thread
        op_state['lock'] = op_lock
        op_state['dialog_title'] = title
        self._app._background_operation = op_state
        self._app.dialog = progress_dialog
        thread.start()
''',
        '''        def _runner(cancel_event):
            if cancel_event.is_set():
                result = ActionResult(ActionType.ERROR, 'Operation cancelled during shutdown.')
            else:
                try:
                    result = worker()
                except _BACKGROUND_WORKER_ERRORS as exc:  # pragma: no cover - defensive worker path
                    result = ActionResult(ActionType.ERROR, str(exc))
            # Publish the result together with the ``done`` flag under a
            # single lock so the main loop never observes a partial state.
            with op_lock:
                op_state['worker_result'] = result
                op_state['done'] = True

        op_state['lock'] = op_lock
        op_state['dialog_title'] = title
        op_state['cancel_event'] = self._worker_scope.cancel_event
        self._app._background_operation = op_state
        self._app.dialog = progress_dialog
        thread = self._worker_scope.start(_runner, name='retrotui-file-op')
        if thread is None:
            self._app._background_operation = None
            if self._app.dialog is progress_dialog:
                self._app.dialog = None
            return ActionResult(ActionType.ERROR, 'Application is shutting down.')
        op_state['thread'] = thread
''',
    )
    replace_once(
        "retrotui/core/file_operations.py",
        '''    def has_background_operation(self):
        """Return whether a background file operation is currently running."""
        return bool(getattr(self._app, '_background_operation', None))
''',
        '''    def has_background_operation(self):
        """Return whether a background file operation is currently running."""
        return bool(
            not self._shutting_down
            and getattr(self._app, '_background_operation', None)
        )

    def shutdown(self, timeout=None):
        """Stop accepting work and detach completion from the UI.

        Filesystem primitives are not always interruptible. The bounded join
        result tells the application whether physical completion was verified,
        while clearing app state guarantees a late worker cannot dispatch into
        a torn-down UI.
        """
        self._shutting_down = True
        stopped = self._worker_scope.shutdown(
            timeout=timeout,
            require_stopped=True,
        )
        state = getattr(self._app, '_background_operation', None)
        if state:
            dialog = state.get('dialog')
            if getattr(self._app, 'dialog', None) is dialog:
                self._app.dialog = None
            self._app._background_operation = None
        return stopped
''',
    )
    replace_once(
        "retrotui/core/file_operations.py",
        '''        state = getattr(self._app, '_background_operation', None)
        if not state:
            return
''',
        '''        state = getattr(self._app, '_background_operation', None)
        if not state or self._shutting_down:
            return
''',
    )
    # threading remains used for the result lock.


def patch_image_viewer() -> None:
    replace_once(
        "retrotui/apps/image_viewer.py",
        '''                thread = threading.Thread(
                    target=self._render_worker,
                    args=(cols, rows, cache_key, self._cancel_event),
                    daemon=True,
                )
                self._render_thread = thread
                thread.start()
''',
        '''                thread = self._start_worker(
                    self._render_worker,
                    cols,
                    rows,
                    cache_key,
                    self._cancel_event,
                    name='retrotui-image-render',
                )
                self._render_thread = thread
                if thread is None:
                    self._render_pending = False
''',
    )
    replace_once(
        "retrotui/apps/image_viewer.py",
        '''    def _render_worker(self, cols, rows, cache_key, cancel_event):
        # If a newer render was scheduled before we even started, bail.
        if cancel_event.is_set():
            return
''',
        '''    def _render_worker(self, owner_cancel_event, cols, rows, cache_key, cancel_event):
        # If the window closed or a newer render superseded us, bail.
        if owner_cancel_event.is_set() or cancel_event.is_set():
            return
''',
    )
    replace_once(
        "retrotui/apps/image_viewer.py",
        '''        if cancel_event.is_set():
            return
        with self._render_lock:
            if self._render_request != cache_key:
                return
        self._render_cache = {"key": cache_key, "lines": list(lines)}

    def tick(self):
''',
        '''        if owner_cancel_event.is_set() or cancel_event.is_set():
            return
        with self._render_lock:
            if self._render_request != cache_key:
                return
            self._render_cache = {"key": cache_key, "lines": list(lines)}

    def close(self):
        """Cancel render ownership and reject late cache publication."""
        self._cancel_event.set()
        with self._render_lock:
            self._render_request = None
            self._render_pending = False
        return super().close()

    def tick(self):
''',
    )


def patch_filemanager_preview() -> None:
    replace_once(
        "retrotui/apps/filemanager/window.py",
        '''        def _worker():
            try:
                lines = get_preview_lines(entry, max_lines, max_cols)
            except Exception:  # pragma: no cover - defensive worker isolation
                lines = ['[preview failed]']
            with self._preview_lock:
                self._preview_pending.discard(cache_key)
                if self._preview_cache.get('key') == cache_key:
                    self._preview_cache = {'key': cache_key, 'lines': lines}
                    self._preview_redraw_pending = True

        thread = threading.Thread(target=_worker, name='retrotui-preview', daemon=True)
        thread.start()
        return loading
''',
        '''        def _worker(cancel_event):
            if cancel_event.is_set():
                return
            try:
                lines = get_preview_lines(entry, max_lines, max_cols)
            except Exception:  # pragma: no cover - defensive worker isolation
                lines = ['[preview failed]']
            with self._preview_lock:
                self._preview_pending.discard(cache_key)
                if cancel_event.is_set():
                    return
                if self._preview_cache.get('key') == cache_key:
                    self._preview_cache = {'key': cache_key, 'lines': lines}
                    self._preview_redraw_pending = True

        thread = self._start_worker(
            _worker,
            name='retrotui-preview',
        )
        if thread is None:
            with self._preview_lock:
                self._preview_pending.discard(cache_key)
        return loading
''',
    )
    insert_before(
        "retrotui/apps/filemanager/window.py",
        "    def tick(self):\n",
        '''    def close(self):
        """Cancel preview ownership and discard pending cache publication."""
        with self._preview_lock:
            self._preview_pending.clear()
            self._preview_cache = {'key': None, 'lines': []}
            self._preview_redraw_pending = False
        return super().close()

''',
    )


def patch_wifi_manager() -> None:
    replace_once(
        "retrotui/apps/wifi_manager.py",
        '''        # Daemon thread; we don't need a reference (the in-progress
        # flag above already serialises scans). Storing the previous
        # thread reference only to overwrite it was leaking the live
        # thread (it kept running NMCLI subprocesses until timeout).
        threading.Thread(target=self._scan_worker, daemon=True).start()
''',
        '''        thread = self._start_worker(
            self._scan_worker,
            name='retrotui-wifi-scan',
        )
        if thread is None:
            with self._scan_lock:
                self._scan_in_progress = False
            self._status_msg = "Scan cancelled."
''',
    )
    replace_once(
        "retrotui/apps/wifi_manager.py",
        "    def _scan_worker(self):\n        new_networks = []\n",
        "    def _scan_worker(self, cancel_event):\n        new_networks = []\n",
    )
    replace_once(
        "retrotui/apps/wifi_manager.py",
        '''            subprocess.run(
                [self.nmcli, "dev", "wifi", "rescan"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=NMCLI_SCAN_TIMEOUT,
            )
            result = subprocess.run(
''',
        '''            if cancel_event.is_set():
                return
            subprocess.run(
                [self.nmcli, "dev", "wifi", "rescan"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=NMCLI_SCAN_TIMEOUT,
            )
            if cancel_event.is_set():
                return
            result = subprocess.run(
''',
    )
    replace_once(
        "retrotui/apps/wifi_manager.py",
        '''        with self._scan_lock:
            self._scan_in_progress = False
            if error_message is not None:
''',
        '''        with self._scan_lock:
            self._scan_in_progress = False
            if cancel_event.is_set():
                self._scan_result_ready = False
                return
            if error_message is not None:
''',
    )
    replace_once(
        "retrotui/apps/wifi_manager.py",
        '''        # See note on ``self._scan_thread`` in ``refresh`` — we don't
        # keep a reference to the live thread; the ``_connect_in_progress``
        # flag above serialises concurrent connect calls.
        threading.Thread(
            target=self._connect_worker,
            args=(ssid, password),
            daemon=True,
        ).start()
''',
        '''        thread = self._start_worker(
            self._connect_worker,
            ssid,
            password,
            name='retrotui-wifi-connect',
        )
        if thread is None:
            with self._connect_lock:
                self._connect_in_progress = False
                self._connect_result = None
            self._connecting_ssid = None
            self._status_msg = "Connection cancelled."
''',
    )
    replace_once(
        "retrotui/apps/wifi_manager.py",
        "    def _finish_connect(self, success, error_message):\n        with self._connect_lock:\n",
        '''    def _finish_connect(self, success, error_message, cancel_event=None):
        if cancel_event is not None and cancel_event.is_set():
            with self._connect_lock:
                self._connect_in_progress = False
                self._connect_result = None
                self._connecting_ssid = None
            return
        with self._connect_lock:
''',
    )
    replace_once(
        "retrotui/apps/wifi_manager.py",
        "    def _connect_worker(self, ssid, password):\n        cmd = [self.nmcli, \"dev\", \"wifi\", \"connect\", ssid]\n",
        '''    def _connect_worker(self, cancel_event, ssid, password):
        if cancel_event.is_set():
            self._finish_connect(False, "Connection cancelled.", cancel_event)
            return
        cmd = [self.nmcli, "dev", "wifi", "connect", ssid]
''',
    )
    # Route every worker completion through the cancellation-aware helper.
    path = ROOT / "retrotui/apps/wifi_manager.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace("self._finish_connect(success, error_message)\n", "self._finish_connect(success, error_message, cancel_event)\n")
    text = text.replace("self._finish_connect(False, \"Connection timed out.\")\n", "self._finish_connect(False, \"Connection timed out.\", cancel_event)\n")
    text = text.replace(
        '''                self._finish_connect(
                    False,
                    f"Could not run nmcli --ask: {exc}. "
                    "Password was not sent insecurely; please report the error.",
                )
''',
        '''                self._finish_connect(
                    False,
                    f"Could not run nmcli --ask: {exc}. "
                    "Password was not sent insecurely; please report the error.",
                    cancel_event,
                )
''',
    )
    path.write_text(text, encoding="utf-8")
    insert_before(
        "retrotui/apps/wifi_manager.py",
        "    def tick(self):\n",
        '''    def close(self):
        """Cancel scan/connect ownership and clear pending UI state."""
        result = super().close()
        with self._scan_lock:
            self._scan_in_progress = False
            self._scan_result_ready = False
            self._scan_error = None
        with self._connect_lock:
            self._connect_in_progress = False
            self._connect_result = None
            self._connecting_ssid = None
        self._dialog = None
        return result

''',
    )


def patch_retronet() -> None:
    replace_once(
        "retrotui/apps/retronet.py",
        "    raw_html: str = \"\"\n",
        "    raw_html: str = \"\"\n    tab_id: int = 0\n    load_generation: int = 0\n",
    )
    replace_once(
        "retrotui/apps/retronet.py",
        '''        self.tabs: List[_TabState] = []
        self.active_tab_idx = 0
''',
        '''        self.tabs: List[_TabState] = []
        self.active_tab_idx = 0
        self._next_tab_id = 1
''',
    )
    replace_once(
        "retrotui/apps/retronet.py",
        '''        with self._lock:
            tab = _TabState(url=url)
            self.tabs.append(tab)
''',
        '''        with self._lock:
            tab_id = int(getattr(self, '_next_tab_id', 1))
            self._next_tab_id = tab_id + 1
            tab = _TabState(url=url, tab_id=tab_id)
            self.tabs.append(tab)
''',
    )
    insert_before(
        "retrotui/apps/retronet.py",
        "    def _new_tab(self, url=\"\", *, activate=True, _push_history=True) -> int:\n",
        '''    def _tab_index_by_id_locked(self, tab_id):
        for index, tab in enumerate(self.tabs):
            if tab.tab_id == tab_id:
                return index
        return None

    def _tab_request_is_current_locked(self, tab_id, generation):
        index = self._tab_index_by_id_locked(tab_id)
        if index is None:
            return None
        tab = self.tabs[index]
        if tab.load_generation != generation:
            return None
        return index

''',
    )
    replace_once(
        "retrotui/apps/retronet.py",
        '''            tab.url = clean_url
            tab.content = [RichLine("Loading...", self.attr_title)]
            tab.is_loading = True
            tab.scroll_y = 0
            tab.search_query = ""
            tab.search_matches = []
            tab.search_idx = -1
        self._refresh_window_title()

        thread = threading.Thread(
            target=self._fetch_thread, args=(sanitized_url, tab_idx), daemon=True
        )
        thread.start()
''',
        '''            tab.url = clean_url
            tab.content = [RichLine("Loading...", self.attr_title)]
            tab.is_loading = True
            tab.scroll_y = 0
            tab.search_query = ""
            tab.search_matches = []
            tab.search_idx = -1
            tab.load_generation += 1
            tab_id = tab.tab_id
            generation = tab.load_generation
        self._refresh_window_title()

        thread = self._start_worker(
            self._fetch_thread,
            sanitized_url,
            tab_id,
            generation,
            name=f'retrotui-fetch-{tab_id}',
        )
        if thread is None:
            with self._lock:
                current_idx = self._tab_request_is_current_locked(tab_id, generation)
                if current_idx is not None:
                    self.tabs[current_idx].is_loading = False
''',
    )
    replace_once(
        "retrotui/apps/retronet.py",
        "    def _fetch_thread(self, url, tab_idx):\n        try:\n",
        '''    def _fetch_thread(self, cancel_event, url, tab_id, generation):
        if cancel_event.is_set():
            return
        try:
''',
    )
    replace_once(
        "retrotui/apps/retronet.py",
        '''            with self._lock:
                if tab_idx < len(self.tabs):
                    self.tabs[tab_idx].raw_html = raw_html
            parsed = self._parse_html(raw_html, tab_idx=tab_idx)
''',
        '''            if cancel_event.is_set():
                return
            with self._lock:
                current_idx = self._tab_request_is_current_locked(tab_id, generation)
                if current_idx is None:
                    return
                self.tabs[current_idx].raw_html = raw_html
            parsed = self._parse_html(
                raw_html,
                tab_id=tab_id,
                generation=generation,
            )
''',
    )
    replace_once(
        "retrotui/apps/retronet.py",
        '''            with self._lock:
                if tab_idx < len(self.tabs):
                    self.tabs[tab_idx].content = parsed
                    self.tabs[tab_idx].is_loading = False
                    if tab_idx == self.active_tab_idx:
                        self._refresh_window_title()
''',
        '''            if cancel_event.is_set():
                return
            with self._lock:
                current_idx = self._tab_request_is_current_locked(tab_id, generation)
                if current_idx is None:
                    return
                self.tabs[current_idx].content = parsed
                self.tabs[current_idx].is_loading = False
                if current_idx == self.active_tab_idx:
                    self._refresh_window_title()
''',
    )
    replace_once(
        "retrotui/apps/retronet.py",
        '''            with self._lock:
                if tab_idx < len(self.tabs):
                    self.tabs[tab_idx].content = [
                        RichLine(f"Error loading {url}:", self.attr_error),
                        RichLine(msg, self.attr_dim)
                    ]
                    self.tabs[tab_idx].is_loading = False
''',
        '''            with self._lock:
                current_idx = self._tab_request_is_current_locked(tab_id, generation)
                if current_idx is not None and not cancel_event.is_set():
                    self.tabs[current_idx].content = [
                        RichLine(f"Error loading {url}:", self.attr_error),
                        RichLine(msg, self.attr_dim)
                    ]
                    self.tabs[current_idx].is_loading = False
''',
    )
    replace_once(
        "retrotui/apps/retronet.py",
        '''            with self._lock:
                if tab_idx < len(self.tabs):
                    self.tabs[tab_idx].is_loading = False
''',
        '''            with self._lock:
                current_idx = self._tab_request_is_current_locked(tab_id, generation)
                if current_idx is not None and not cancel_event.is_set():
                    self.tabs[current_idx].is_loading = False
''',
    )
    replace_once(
        "retrotui/apps/retronet.py",
        "    def _parse_html(self, raw_html, tab_idx=None):\n",
        "    def _parse_html(self, raw_html, tab_idx=None, tab_id=None, generation=None):\n",
    )
    replace_once(
        "retrotui/apps/retronet.py",
        '''                target_idx = tab_idx if tab_idx is not None else self.active_tab_idx
                if 0 <= target_idx < len(self.tabs):
                    self.tabs[target_idx].title = title
                if tab_idx is None or tab_idx == self.active_tab_idx:
                    self._refresh_window_title()
''',
        '''                if tab_id is not None:
                    target_idx = self._tab_request_is_current_locked(tab_id, generation)
                else:
                    target_idx = tab_idx if tab_idx is not None else self.active_tab_idx
                if target_idx is not None and 0 <= target_idx < len(self.tabs):
                    self.tabs[target_idx].title = title
                    if target_idx == self.active_tab_idx:
                        self._refresh_window_title()
''',
    )
    insert_before(
        "retrotui/apps/retronet.py",
        "    # ------------------------------------------------------------------\n    # HTML parsing\n",
        '''    def close(self):
        """Cancel fetch ownership and invalidate every in-flight navigation."""
        result = super().close()
        with self._lock:
            for tab in self.tabs:
                tab.load_generation += 1
                tab.is_loading = False
        return result

''',
    )


def patch_terminal_super_close() -> None:
    replace_once(
        "retrotui/apps/terminal.py",
        '''            self._session = None
        self._pending_output = ''
        self._last_pty_size = None
        return True
''',
        '''            self._session = None
        if super().close() is False:
            return False
        self._pending_output = ''
        self._last_pty_size = None
        return True
''',
    )


def write_tests() -> None:
    write(
        "tests/test_worker_lifecycle.py",
        '''import threading
import time
import types
import unittest
from unittest import mock

from retrotui.apps.filemanager.window import FileManagerWindow
from retrotui.apps.image_viewer import ImageViewerWindow
from retrotui.apps.retronet import RetroNetWindow, _TabState
from retrotui.apps.wifi_manager import WifiManagerWindow
from retrotui.core.actions import ActionResult, ActionType
from retrotui.core.file_operations import FileOperationManager
from retrotui.core.worker_scope import WorkerScope
from retrotui.ui.window import Window


class WorkerScopeTests(unittest.TestCase):
    def test_shutdown_signals_and_joins_cooperative_worker(self):
        scope = WorkerScope("test", join_timeout=0.5)
        started = threading.Event()
        stopped = threading.Event()

        def worker(cancel_event):
            started.set()
            cancel_event.wait(1.0)
            stopped.set()

        thread = scope.start(worker, name="test-worker")
        self.assertIsNotNone(thread)
        self.assertTrue(started.wait(0.5))
        self.assertTrue(scope.shutdown(require_stopped=True))
        self.assertTrue(stopped.is_set())
        self.assertEqual(scope.active_count, 0)

    def test_closed_scope_rejects_new_workers(self):
        scope = WorkerScope("closed")
        scope.cancel()
        self.assertIsNone(scope.start(lambda _cancel: None))

    def test_bounded_shutdown_can_report_uninterruptible_worker(self):
        scope = WorkerScope("blocked", join_timeout=0.01)
        release = threading.Event()
        scope.start(lambda _cancel: release.wait(1.0), name="blocked-worker")
        try:
            self.assertFalse(scope.shutdown(require_stopped=True))
        finally:
            release.set()
            scope.join(timeout=0.5)


class WindowWorkerOwnershipTests(unittest.TestCase):
    def test_window_close_cancels_owned_worker(self):
        window = Window("test", 0, 0, 20, 8)
        observed = threading.Event()

        def worker(cancel_event):
            cancel_event.wait(1.0)
            observed.set()

        window._start_worker(worker, name="window-worker")
        self.assertTrue(window.close())
        self.assertTrue(observed.wait(0.5))
        self.assertTrue(window.worker_cancelled())

    def test_retronet_request_identity_survives_tab_index_reuse(self):
        window = RetroNetWindow.__new__(RetroNetWindow)
        Window.__init__(window, "RetroNet", 0, 0, 40, 12)
        window._lock = threading.Lock()
        window.tabs = [
            _TabState(tab_id=10, load_generation=2),
            _TabState(tab_id=11, load_generation=1),
        ]
        window.active_tab_idx = 0

        with window._lock:
            self.assertEqual(window._tab_request_is_current_locked(10, 2), 0)
            self.assertIsNone(window._tab_request_is_current_locked(10, 1))
            del window.tabs[0]
            window.tabs.insert(0, _TabState(tab_id=12, load_generation=2))
            self.assertIsNone(window._tab_request_is_current_locked(10, 2))

    def test_component_close_methods_cancel_scope_and_clear_pending_state(self):
        image = ImageViewerWindow.__new__(ImageViewerWindow)
        Window.__init__(image, "image", 0, 0, 20, 8)
        image._cancel_event = threading.Event()
        image._render_lock = threading.Lock()
        image._render_request = (1,)
        image._render_pending = True
        self.assertTrue(image.close())
        self.assertTrue(image._cancel_event.is_set())
        self.assertIsNone(image._render_request)

        preview = FileManagerWindow.__new__(FileManagerWindow)
        Window.__init__(preview, "files", 0, 0, 20, 8)
        preview._preview_lock = threading.Lock()
        preview._preview_pending = {("key",)}
        preview._preview_cache = {"key": ("key",), "lines": ["old"]}
        preview._preview_redraw_pending = True
        self.assertTrue(preview.close())
        self.assertFalse(preview._preview_pending)
        self.assertIsNone(preview._preview_cache["key"])

        wifi = WifiManagerWindow.__new__(WifiManagerWindow)
        Window.__init__(wifi, "wifi", 0, 0, 50, 15)
        wifi._scan_lock = threading.Lock()
        wifi._connect_lock = threading.Lock()
        wifi._scan_in_progress = True
        wifi._scan_result_ready = True
        wifi._scan_error = "error"
        wifi._connect_in_progress = True
        wifi._connect_result = (True, "")
        wifi._connecting_ssid = "network"
        wifi._dialog = object()
        self.assertTrue(wifi.close())
        self.assertFalse(wifi._scan_in_progress)
        self.assertFalse(wifi._connect_in_progress)
        self.assertIsNone(wifi._dialog)


class FileOperationShutdownTests(unittest.TestCase):
    def test_shutdown_suppresses_late_ui_dispatch(self):
        app = types.SimpleNamespace(
            _background_operation=None,
            dialog=None,
            _event_bus=None,
            _dirty=False,
            _dispatch_window_result=mock.Mock(),
        )
        manager = FileOperationManager(app)
        release = threading.Event()

        def worker():
            release.wait(1.0)
            return ActionResult(ActionType.REFRESH, "done")

        self.assertIsNone(
            manager._start_background_operation(
                title="Copying",
                message="Please wait",
                worker=worker,
                source_win=object(),
            )
        )
        self.assertFalse(manager.shutdown(timeout=0.01))
        self.assertIsNone(app._background_operation)
        release.set()
        manager._worker_scope.join(timeout=0.5)
        manager.poll_background_operation()
        app._dispatch_window_result.assert_not_called()

    def test_shutdown_rejects_new_file_operations(self):
        app = types.SimpleNamespace(
            _background_operation=None,
            dialog=None,
            _event_bus=None,
        )
        manager = FileOperationManager(app)
        self.assertTrue(manager.shutdown(timeout=0.0))
        result = manager._start_background_operation(
            title="Copying",
            message="Please wait",
            worker=lambda: None,
            source_win=None,
        )
        self.assertEqual(result.type, ActionType.ERROR)
        self.assertIn("shutting down", result.payload.lower())


if __name__ == "__main__":
    unittest.main()
''',
    )


def main() -> None:
    write_worker_scope()
    patch_window_base()
    patch_app_cleanup()
    patch_file_operations()
    patch_image_viewer()
    patch_filemanager_preview()
    patch_wifi_manager()
    patch_retronet()
    patch_terminal_super_close()
    write_tests()


if __name__ == "__main__":
    main()

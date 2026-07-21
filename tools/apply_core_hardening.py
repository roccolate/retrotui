#!/usr/bin/env python3
"""Apply the first RetroTUI core-hardening batch.

This script is intentionally idempotent and is removed after the validated
patch commit is produced on the hardening branch.
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


def write(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def patch_key_router() -> None:
    replace_once(
        "retrotui/core/key_router.py",
        "import curses\n\nfrom ..utils import normalize_key_code\n",
        "import curses\nimport logging\n\nfrom ..utils import normalize_key_code\n",
    )
    replace_once(
        "retrotui/core/key_router.py",
        "from .actions import AppAction\n\n\n",
        "from .actions import AppAction\n\n\nLOGGER = logging.getLogger(__name__)\n\n\n",
    )


def patch_window_manager() -> None:
    replace_once(
        "retrotui/core/window_manager.py",
        '''        closer = getattr(win, 'close', None)\n        if callable(closer):\n            try:\n                closer()\n            except _WINDOW_CLOSE_HOOK_ERRORS:  # pragma: no cover - defensive window cleanup path\n                LOGGER.debug('Window close hook failed for %r', win, exc_info=True)\n        if win in self.windows:\n            self.windows.remove(win)\n''',
        '''        closer = getattr(win, 'close', None)\n        if callable(closer):\n            try:\n                close_result = closer()\n            except _WINDOW_CLOSE_HOOK_ERRORS:\n                LOGGER.warning('Window close hook failed for %r', win, exc_info=True)\n                return False\n            if close_result is False:\n                LOGGER.warning('Window close was not verified for %r; keeping it registered', win)\n                return False\n        if win in self.windows:\n            self.windows.remove(win)\n''',
    )
    replace_once(
        "retrotui/core/window_manager.py",
        '''    def get_active_window(self):\n        """Return the active window, if any.\n\n        Returns the cached ``_active_window`` pointer; falls back to a\n        linear scan only when the pointer is out of sync (e.g. a test\n        that poked ``active`` or ``windows`` directly).\n        """\n        cached = self._active_window\n        # Reject the cache if the window is no longer in the list, or\n        # its ``active`` flag was cleared externally.\n        if (\n            cached is not None\n            and getattr(cached, "active", False)\n            and cached in self.windows\n        ):\n            return cached\n        self._active_window = None\n        for w in self.windows:\n            if getattr(w, "active", False):\n                self._active_window = w\n                return w\n        return None\n''',
        '''    def get_active_window(self):\n        """Return a visible active window, repairing stale focus if needed.\n\n        A component isolated after repeated draw failures may remain in the\n        window list. It must not keep keyboard focus after becoming invisible.\n        """\n        cached = self._active_window\n        if (\n            cached is not None\n            and getattr(cached, "active", False)\n            and getattr(cached, "visible", True)\n            and cached in self.windows\n        ):\n            return cached\n\n        if cached is not None and not getattr(cached, "visible", True):\n            cached.active = False\n        self._active_window = None\n\n        for window in self.windows:\n            if not getattr(window, "active", False):\n                continue\n            if getattr(window, "visible", True):\n                self._active_window = window\n                return window\n            window.active = False\n\n        return self._activate_last_visible_window()\n''',
    )


def patch_terminal_window() -> None:
    replace_once(
        "retrotui/apps/terminal.py",
        '''    def restart_session(self):\n        """Reset scrollback state and start a fresh shell session lazily."""\n        self.close()\n        self._session_error = None\n''',
        '''    def restart_session(self):\n        """Reset scrollback state and start a fresh shell session lazily."""\n        if self.close() is False:\n            return False\n        self._session_error = None\n''',
    )
    replace_once(
        "retrotui/apps/terminal.py",
        '''        self._mouse_modes = set()\n        self.scrollback_offset = 0\n\n    def close(self):\n        """Release PTY resources when terminal window is closed."""\n        self._pending_output = ''\n        self._last_pty_size = None\n        if self._session is not None:\n            self._session.close()\n            self._session = None\n''',
        '''        self._mouse_modes = set()\n        self.scrollback_offset = 0\n        return True\n\n    def close(self):\n        """Release PTY resources only after the child is verified stopped."""\n        session = self._session\n        if session is not None:\n            if session.close() is False:\n                self._set_session_error(\n                    RuntimeError("Terminal child is still alive; close was cancelled.")\n                )\n                return False\n            self._session = None\n        self._pending_output = ''\n        self._last_pty_size = None\n        return True\n''',
    )


def patch_packaging() -> None:
    replace_once(
        "pyproject.toml",
        '''test = [\n    "pytest",\n]\n''',
        '''test = [\n    "pytest",\n    "ruff",\n]\n''',
    )


def write_contract_tests() -> None:
    write(
        "tests/test_core_hardening_contracts.py",
        '''import types\nimport unittest\nfrom unittest import mock\n\nfrom retrotui.apps.terminal import TerminalWindow\nfrom retrotui.core import key_router\nfrom retrotui.core.window_manager import WindowManager\n\n\nclass CoreHardeningContractTests(unittest.TestCase):\n    def test_cleanup_false_keeps_window_registered(self):\n        app = types.SimpleNamespace(event_bus=None, _active_window_menu_owner=None)\n        manager = WindowManager(app)\n        window = types.SimpleNamespace(\n            id="terminal",\n            title="Terminal",\n            active=True,\n            visible=True,\n            always_on_top=False,\n            close=mock.Mock(return_value=False),\n        )\n        manager.windows = [window]\n        manager._active_window = window\n\n        self.assertFalse(manager.close_window(window))\n        self.assertEqual(manager.windows, [window])\n        self.assertIs(manager.get_active_window(), window)\n\n    def test_hidden_active_window_yields_focus_to_visible_window(self):\n        app = types.SimpleNamespace(event_bus=None)\n        manager = WindowManager(app)\n        visible = types.SimpleNamespace(active=False, visible=True)\n        hidden = types.SimpleNamespace(active=True, visible=False)\n        manager.windows = [visible, hidden]\n        manager._active_window = hidden\n\n        self.assertIs(manager.get_active_window(), visible)\n        self.assertFalse(hidden.active)\n        self.assertTrue(visible.active)\n\n    def test_terminal_close_failure_preserves_session(self):\n        terminal = TerminalWindow.__new__(TerminalWindow)\n        session = types.SimpleNamespace(close=mock.Mock(return_value=False))\n        terminal._session = session\n        terminal._session_error = None\n        terminal._reported_session_error = False\n        terminal._pending_output = "pending"\n        terminal._last_pty_size = (80, 24)\n\n        self.assertFalse(terminal.close())\n        self.assertIs(terminal._session, session)\n        self.assertEqual(terminal._pending_output, "pending")\n        self.assertIn("still alive", terminal._session_error)\n\n    def test_terminal_close_success_releases_session(self):\n        terminal = TerminalWindow.__new__(TerminalWindow)\n        session = types.SimpleNamespace(close=mock.Mock(return_value=True))\n        terminal._session = session\n        terminal._session_error = None\n        terminal._reported_session_error = False\n        terminal._pending_output = "pending"\n        terminal._last_pty_size = (80, 24)\n\n        self.assertTrue(terminal.close())\n        self.assertIsNone(terminal._session)\n        self.assertEqual(terminal._pending_output, "")\n        self.assertIsNone(terminal._last_pty_size)\n\n    def test_focus_reorder_failure_is_logged_without_secondary_name_error(self):\n        current = types.SimpleNamespace(active=True, visible=True, always_on_top=False)\n        target = types.SimpleNamespace(active=False, visible=True, always_on_top=False)\n        app = types.SimpleNamespace(\n            windows=[current, target],\n            window_mgr=types.SimpleNamespace(\n                set_active_window=mock.Mock(side_effect=ValueError("bad z-order"))\n            ),\n        )\n\n        key_router.cycle_focus(app)\n\n        self.assertTrue(target.active)\n        app.window_mgr.set_active_window.assert_called_once_with(target)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''',
    )


def write_workflows() -> None:
    write(
        ".github/workflows/ci.yml",
        '''name: CI\n\non:\n  push:\n  pull_request:\n\npermissions:\n  contents: read\n\nenv:\n  MODULE_COVERAGE_FAIL_UNDER: "75.0"\n\njobs:\n  quality:\n    runs-on: ${{ matrix.os }}\n    strategy:\n      fail-fast: false\n      matrix:\n        os: [ubuntu-latest, windows-latest]\n        python-version: ["3.10", "3.12", "3.14"]\n\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v5\n\n      - name: Setup Python\n        uses: actions/setup-python@v6\n        with:\n          python-version: ${{ matrix.python-version }}\n\n      - name: Install package and test dependencies\n        run: |\n          python -m pip install --upgrade pip\n          python -m pip install -e ".[test]"\n\n      - name: Run repository quality checks\n        run: python tools/qa.py --skip-tests\n\n      - name: Reject undefined Python names\n        run: python -m ruff check --select F821 retrotui tests tools\n\n      - name: Run unittest suite\n        run: python -m unittest discover -s tests -v\n\n      - name: Run pytest suite\n        if: ${{ !cancelled() }}\n        run: python -m pytest tests -q\n\n      - name: Enforce module coverage floor\n        if: ${{ !cancelled() }}\n        run: >-\n          python tools/report_module_coverage.py\n          --quiet-tests\n          --top 20\n          --fail-under "${{ env.MODULE_COVERAGE_FAIL_UNDER }}"\n''',
    )
    write(
        ".github/workflows/release.yml",
        '''name: Release\n\non:\n  push:\n    tags:\n      - "v*.*.*"\n  workflow_dispatch:\n    inputs:\n      tag:\n        description: "Existing tag to release (vX.Y.Z)"\n        required: true\n        type: string\n\npermissions:\n  contents: write\n\nenv:\n  MODULE_COVERAGE_FAIL_UNDER: "75.0"\n\njobs:\n  release:\n    runs-on: ubuntu-latest\n    env:\n      RELEASE_TAG: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.tag || github.ref_name }}\n\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v5\n        with:\n          fetch-depth: 0\n          ref: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.tag || github.ref }}\n\n      - name: Setup Python\n        uses: actions/setup-python@v6\n        with:\n          python-version: "3.12"\n\n      - name: Install package and test dependencies\n        run: |\n          python -m pip install --upgrade pip\n          python -m pip install -e ".[test]"\n\n      - name: Run release quality gate\n        run: |\n          python tools/qa.py --skip-tests\n          python -m ruff check --select F821 retrotui tests tools\n          python -m unittest discover -s tests -v\n          python -m pytest tests -q\n          python tools/report_module_coverage.py --quiet-tests --top 20 --fail-under "${{ env.MODULE_COVERAGE_FAIL_UNDER }}"\n\n      - name: Validate release tag\n        run: python tools/check_release_tag.py --tag "${{ env.RELEASE_TAG }}"\n\n      - name: Build distributions\n        run: |\n          python -m pip install build\n          python -m build\n\n      - name: Smoke-test built wheel\n        run: |\n          python -m venv .release-smoke\n          .release-smoke/bin/python -m pip install --upgrade pip\n          .release-smoke/bin/python -m pip install dist/*.whl\n          .release-smoke/bin/python -c "import retrotui; print(retrotui.__version__)"\n\n      - name: Upload release artifacts\n        uses: actions/upload-artifact@v5\n        with:\n          name: dist-${{ env.RELEASE_TAG }}\n          path: dist/*\n\n      - name: Publish GitHub release\n        uses: softprops/action-gh-release@v2\n        with:\n          tag_name: ${{ env.RELEASE_TAG }}\n          name: RetroTUI ${{ env.RELEASE_TAG }}\n          generate_release_notes: true\n          files: dist/*\n''',
    )


def main() -> None:
    patch_key_router()
    patch_window_manager()
    patch_terminal_window()
    patch_packaging()
    write_contract_tests()
    write_workflows()


if __name__ == "__main__":
    main()

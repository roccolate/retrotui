import curses
import unittest

from retrotui.core.actions import AppAction
from retrotui.core import key_router


class _FakeMenu:
    def __init__(self):
        self.active = False
        self.selected_menu = 0
        self.selected_item = 0
        self.handled = []

    def handle_key(self, key_code):
        self.handled.append(key_code)
        return None


class _FakeContextMenu:
    active = False

    def is_open(self):
        return self.active

    def hide(self):
        self.active = False


class _FakeTerminal:
    def __init__(self):
        self.window_menu = _FakeMenu()
        self.forwarded = []
        self.handle_key_calls = []
        self.copy_calls = 0
        self.interrupt_calls = 0
        self.terminate_calls = 0
        self.restart_calls = 0
        self.active = True
        self.visible = True

    def _key_to_input(self, key, key_code):
        mapping = {
            getattr(curses, "KEY_F6", 270): "<F6>",
            getattr(curses, "KEY_F7", 271): "<F7>",
            getattr(curses, "KEY_F8", 272): "<F8>",
            getattr(curses, "KEY_F10", 274): "<F10>",
            getattr(curses, "KEY_F12", 276): "<F12>",
        }
        if key_code in mapping:
            return mapping[key_code]
        if key_code == 9:
            return "\t"
        if key_code == 17:
            return "\x11"
        if isinstance(key, str) and len(key) == 1:
            return key
        return None

    def _forward_payload(self, payload):
        self.forwarded.append(payload)

    def handle_key(self, key):
        self.handle_key_calls.append(key)

    def _copy_selection(self):
        self.copy_calls += 1

    def _send_interrupt(self):
        self.interrupt_calls += 1

    def _send_terminate(self):
        self.terminate_calls += 1

    def restart_session(self):
        self.restart_calls += 1


class _FakeWindow:
    def __init__(self):
        self.window_menu = None
        self.active = True
        self.visible = True
        self.keys = []

    def handle_key(self, key):
        self.keys.append(key)
        return None


class _FakeApp:
    def __init__(self, window):
        self.window = window
        self.windows = [window]
        self.menu = _FakeMenu()
        self.context_menu = _FakeContextMenu()
        self._active_window_menu_owner = None
        self.actions = []
        self.focus_cycles = []
        self.dispatched = []

    def get_active_window(self):
        return self.window

    def execute_action(self, action):
        self.actions.append(action)

    def _cycle_focus(self, reverse=False):
        self.focus_cycles.append(reverse)

    def _dispatch_window_result(self, result, window):
        self.dispatched.append((result, window))

    def _handle_dialog_key(self, key):
        return False

    def _handle_menu_hotkeys(self, key_code):
        return key_router.handle_menu_hotkeys(self, key_code)

    def _handle_global_menu_key(self, key_code):
        return key_router.handle_global_menu_key(self, key_code)

    def _handle_active_window_key(self, key):
        return key_router.handle_active_window_key(self, key)


class TerminalInputPolicyTests(unittest.TestCase):
    def setUp(self):
        self.terminal = _FakeTerminal()
        self.app = _FakeApp(self.terminal)
        self.f6 = getattr(curses, "KEY_F6", 270)
        self.f7 = getattr(curses, "KEY_F7", 271)
        self.f8 = getattr(curses, "KEY_F8", 272)
        self.f10 = getattr(curses, "KEY_F10", 274)
        self.f12 = getattr(curses, "KEY_F12", 276)
        self.btab = getattr(curses, "KEY_BTAB", 353)

    def test_terminal_receives_global_and_legacy_function_keys(self):
        for key in (9, 17, self.f6, self.f7, self.f8, self.f10):
            key_router.handle_key_event(self.app, key)

        self.assertEqual(
            self.terminal.forwarded,
            ["\t", "\x11", "<F6>", "<F7>", "<F8>", "<F10>"],
        )
        self.assertEqual(self.app.actions, [])
        self.assertEqual(self.app.focus_cycles, [])
        self.assertFalse(self.terminal.window_menu.active)

    def test_shift_tab_is_forwarded_as_backtab(self):
        key_router.handle_key_event(self.app, self.btab)
        self.assertEqual(self.terminal.forwarded, ["\x1b[Z"])
        self.assertEqual(self.app.focus_cycles, [])

    def test_f12_prefix_runs_host_commands(self):
        key_router.handle_key_event(self.app, self.f12)
        key_router.handle_key_event(self.app, "c")
        self.assertEqual(self.terminal.copy_calls, 1)
        self.assertEqual(self.terminal.forwarded, [])

        key_router.handle_key_event(self.app, self.f12)
        key_router.handle_key_event(self.app, "m")
        self.assertTrue(self.terminal.window_menu.active)
        self.assertIs(self.app._active_window_menu_owner, self.terminal)

        self.terminal.window_menu.active = False
        self.app._active_window_menu_owner = None
        key_router.handle_key_event(self.app, self.f12)
        key_router.handle_key_event(self.app, "x")
        self.assertEqual(self.app.actions[-1], AppAction.CLOSE_WINDOW)

        key_router.handle_key_event(self.app, self.f12)
        key_router.handle_key_event(self.app, "q")
        self.assertEqual(self.app.actions[-1], AppAction.EXIT)

    def test_f12_prefix_controls_session_and_focus(self):
        command_expectations = (
            ("i", "interrupt_calls"),
            ("k", "terminate_calls"),
            ("r", "restart_calls"),
        )
        for command, attr in command_expectations:
            key_router.handle_key_event(self.app, self.f12)
            key_router.handle_key_event(self.app, command)
            self.assertEqual(getattr(self.terminal, attr), 1)

        key_router.handle_key_event(self.app, self.f12)
        key_router.handle_key_event(self.app, 9)
        self.assertEqual(self.app.focus_cycles, [False])

        key_router.handle_key_event(self.app, self.f12)
        key_router.handle_key_event(self.app, "v")
        self.assertEqual(self.terminal.handle_key_calls, [22])

    def test_double_prefix_sends_literal_f12(self):
        key_router.handle_key_event(self.app, self.f12)
        key_router.handle_key_event(self.app, self.f12)
        self.assertEqual(self.terminal.forwarded, ["<F12>"])

    def test_unknown_prefix_command_replays_input(self):
        key_router.handle_key_event(self.app, self.f12)
        key_router.handle_key_event(self.app, "z")
        self.assertEqual(self.terminal.forwarded, ["<F12>", "z"])

    def test_open_menu_keeps_existing_modal_priority(self):
        self.app.menu.active = True
        key_router.handle_key_event(self.app, 17)
        self.assertFalse(self.app.menu.active)
        self.assertEqual(self.terminal.forwarded, [])
        self.assertEqual(self.app.actions, [])

    def test_non_terminal_preserves_global_shortcuts(self):
        window = _FakeWindow()
        app = _FakeApp(window)

        key_router.handle_key_event(app, 17)
        self.assertEqual(app.actions, [AppAction.EXIT])

        key_router.handle_key_event(app, 9)
        self.assertEqual(app.focus_cycles, [False])

        key_router.handle_key_event(app, "x")
        self.assertEqual(window.keys, ["x"])


if __name__ == "__main__":
    unittest.main()

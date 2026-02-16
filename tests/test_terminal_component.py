import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_LEFT = 260
    fake.KEY_RIGHT = 261
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_ENTER = 343
    fake.KEY_HOME = 262
    fake.KEY_END = 360
    fake.KEY_PPAGE = 339
    fake.KEY_NPAGE = 338
    fake.KEY_BACKSPACE = 263
    fake.KEY_DC = 330
    fake.KEY_IC = 331
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.error = Exception
    fake.color_pair = lambda value: value * 10
    return fake


class _FakeSession:
    instances = []
    supported = True
    start_error = None

    def __init__(self, shell=None, cwd=None, env=None, cols=80, rows=24):
        self.shell = shell
        self.cwd = cwd
        self.env = dict(env or {})
        self.cols = cols
        self.rows = rows
        self.running = True
        self.started = False
        self.closed = False
        self.read_chunks = []
        self.writes = []
        self.resize_calls = []
        self.poll_calls = 0
        _FakeSession.instances.append(self)

    @staticmethod
    def is_supported():
        return _FakeSession.supported

    def start(self):
        self.started = True
        if _FakeSession.start_error is not None:
            raise _FakeSession.start_error

    def read(self, max_bytes=4096):  # pylint: disable=unused-argument
        if self.read_chunks:
            return self.read_chunks.pop(0)
        return ""

    def write(self, payload):
        self.writes.append(payload)
        return len(payload)

    def resize(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.resize_calls.append((cols, rows))

    def poll_exit(self):
        self.poll_calls += 1
        return False

    def close(self):
        self.closed = True
        self.running = False


class TerminalComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.actions",
            "retrotui.core.clipboard",
            "retrotui.core.terminal_session",
            "retrotui.apps.terminal",
        ):
            sys.modules.pop(mod_name, None)

        cls.terminal_mod = importlib.import_module("retrotui.apps.terminal")
        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.curses = sys.modules["curses"]

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.utils",
            "retrotui.ui.menu",
            "retrotui.ui.window",
            "retrotui.core.actions",
            "retrotui.core.clipboard",
            "retrotui.core.terminal_session",
            "retrotui.apps.terminal",
        ):
            sys.modules.pop(mod_name, None)

        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def setUp(self):
        _FakeSession.instances = []
        _FakeSession.supported = True
        _FakeSession.start_error = None

    def _make_window(self):
        win = self.terminal_mod.TerminalWindow(2, 3, 40, 12)
        win.body_rect = mock.Mock(return_value=(4, 5, 30, 8))
        return win

    def test_strip_ansi_handles_partial_and_osc_sequences(self):
        win = self._make_window()
        self.assertEqual(win._strip_ansi("A\x1b[31mB"), "AB")
        self.assertEqual(win._ansi_pending, "")
        self.assertEqual(win._strip_ansi("\x1b"), "")
        self.assertEqual(win._ansi_pending, "\x1b")
        win = self._make_window()
        self.assertEqual(win._strip_ansi("C\x1b["), "C")
        self.assertEqual(win._ansi_pending, "\x1b[")
        self.assertEqual(win._strip_ansi("31"), "")
        self.assertEqual(win._strip_ansi("32mD"), "D")
        self.assertEqual(win._strip_ansi("\x1bcK"), "K")
        self.assertEqual(win._strip_ansi("\x1b]0;title\x07X"), "X")
        self.assertEqual(win._strip_ansi("\x1b]2;partial"), "")
        self.assertEqual(win._ansi_pending, "\x1b]2;partial")
        self.assertEqual(win._strip_ansi("\x1b\\Z"), "Z")

    def test_consume_output_applies_controls_and_trim_scrollback(self):
        win = self._make_window()
        win.max_scrollback = 2

        win._consume_output("abc\rZ\nxy\b!\tQ\nL1\nL2\nL3\n")

        self.assertEqual(win._scroll_lines, ["L1", "L2", "L3"][-2:])
        self.assertEqual("".join(win._line_chars), "")
        self.assertEqual(win._cursor_col, 0)

    def test_consume_output_applies_csi_line_edit_sequences(self):
        win = self._make_window()

        # Typical shell behavior for erase: backspace + CSI K.
        win._consume_output("abc\b\x1b[K")
        self.assertEqual("".join(win._line_chars), "ab")
        self.assertEqual(win._cursor_col, 2)

        # Cursor-left rewrite using CSI D.
        win._consume_output("\r1234\x1b[2DXY")
        self.assertEqual("".join(win._line_chars), "12XY")
        self.assertEqual(win._cursor_col, 4)

        # Explicit cursor absolute and erase whole line.
        win._consume_output("\x1b[GQ")
        self.assertEqual("".join(win._line_chars), "Q2XY")
        win._consume_output("\x1b[2K")
        self.assertEqual("".join(win._line_chars), "")
        self.assertEqual(win._cursor_col, 0)

    def test_apply_csi_covers_extra_cursor_and_erase_modes(self):
        win = self._make_window()
        win._line_chars = list("abcd")
        win._cursor_col = 2

        win._apply_csi("1", "K")
        self.assertEqual("".join(win._line_chars), "   d")

        win._cursor_col = 0
        win._apply_csi("", "C")
        self.assertEqual(win._cursor_col, 1)

        win._apply_csi("x", "C")
        self.assertEqual(win._cursor_col, 2)

        win._apply_csi("2", "C")
        self.assertEqual(win._cursor_col, 4)

        win._apply_csi("1;7", "H")
        self.assertEqual(win._cursor_col, 6)

        win._apply_csi("10", "f")
        self.assertEqual(win._cursor_col, 0)

    def test_consume_output_handles_partial_escape_osc_and_two_byte_sequences(self):
        win = self._make_window()

        win._consume_output("A\x1b")
        self.assertEqual("".join(win._line_chars), "A")
        self.assertEqual(win._ansi_pending, "\x1b")

        win._consume_output("[31")
        self.assertEqual(win._ansi_pending, "\x1b[31")

        win._consume_output("mB")
        self.assertEqual("".join(win._line_chars), "AB")
        self.assertEqual(win._ansi_pending, "")

        win._consume_output("\x1b]0;title\x07C")
        self.assertEqual("".join(win._line_chars), "ABC")

        win._consume_output("\x1b]0;x\x1b\\D")
        self.assertEqual("".join(win._line_chars), "ABCD")

        win._consume_output("\x1b]0;partial")
        self.assertEqual(win._ansi_pending, "\x1b]0;partial")
        win._consume_output("\x07E")
        self.assertEqual("".join(win._line_chars), "ABCDE")
        self.assertEqual(win._ansi_pending, "")

        win._consume_output("\x1bcF")
        self.assertEqual("".join(win._line_chars), "ABCDEF")

    def test_ensure_session_supported_and_start_errors(self):
        win = self._make_window()
        with mock.patch.object(self.terminal_mod, "TerminalSession", _FakeSession):
            win._ensure_session()
            self.assertIsNotNone(win._session)
            self.assertTrue(_FakeSession.instances[0].started)
            self.assertEqual((_FakeSession.instances[0].cols, _FakeSession.instances[0].rows), (29, 7))

            win2 = self._make_window()
            _FakeSession.supported = False
            win2._ensure_session()
            self.assertIn("not supported", win2._session_error)

            win3 = self._make_window()
            _FakeSession.supported = True
            _FakeSession.start_error = OSError("boom")
            win3._ensure_session()
            self.assertEqual(win3._session_error, "boom")

    def test_visible_slice_and_fit_line(self):
        win = self._make_window()
        win._scroll_lines = ["a", "b", "c", "d"]
        win._line_chars = list("e")
        win.scrollback_offset = 999

        visible, start, total = win._visible_slice(3)
        self.assertEqual(total, 5)
        self.assertEqual(start, 0)
        self.assertEqual(visible, ["a", "b", "c"])
        self.assertEqual(win._fit_line("xy", 5), "xy   ")
        win._line_chars = []
        win._cursor_col = 3
        win._write_char("Z")
        self.assertEqual("".join(win._line_chars), "   Z")

    def test_draw_renders_output_status_and_scrollbar(self):
        win = self._make_window()
        win.draw_frame = mock.Mock(return_value=0)
        menu = types.SimpleNamespace(draw_dropdown=mock.Mock())
        win.window_menu = menu

        fake_session = _FakeSession(cols=10, rows=5)
        fake_session.read_chunks = ["one\ntwo\nthree\nfour\n"]
        win._session = fake_session
        win.scrollback_offset = 1

        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win.draw(types.SimpleNamespace())

        self.assertTrue(fake_session.resize_calls)
        self.assertGreater(fake_session.poll_calls, 0)
        rendered_texts = [call.args[3] for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("two" in text or "three" in text for text in rendered_texts))
        menu.draw_dropdown.assert_called_once()
        self.assertTrue(any("RUN" in text for text in rendered_texts))

    def test_draw_with_error_and_no_session_populates_buffer_once(self):
        win = self._make_window()
        win.draw_frame = mock.Mock(return_value=0)
        win._session_error = "session failed"
        win.window_menu = None

        with mock.patch.object(self.terminal_mod, "safe_addstr"):
            win.draw(types.SimpleNamespace())
            win.draw(types.SimpleNamespace())

        self.assertTrue(any("session failed" in line for line in win._scroll_lines))

    def test_draw_states_init_and_exit_and_hidden_short_circuit(self):
        win = self._make_window()
        win.draw_frame = mock.Mock(return_value=0)
        win.window_menu = None

        with (
            mock.patch.object(win, "_ensure_session", return_value=None),
            mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr,
        ):
            win.draw(types.SimpleNamespace())
        rendered = [call.args[3] for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("INIT" in text for text in rendered))

        win._session = types.SimpleNamespace(
            running=False,
            resize=mock.Mock(),
            read=mock.Mock(return_value=""),
            poll_exit=mock.Mock(return_value=False),
        )
        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win.draw(types.SimpleNamespace())
        rendered = [call.args[3] for call in safe_addstr.call_args_list if len(call.args) >= 4]
        self.assertTrue(any("EXIT" in text for text in rendered))

        win.visible = False
        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win.draw(types.SimpleNamespace())
        safe_addstr.assert_not_called()

    def test_draw_scrollback_bar_draw_and_noop_paths(self):
        win = self._make_window()
        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win._draw_scrollback_bar(None, x=1, y=2, rows=3, start_idx=4, total_lines=10)
            self.assertEqual(safe_addstr.call_count, 3)

        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win._draw_scrollback_bar(None, x=1, y=2, rows=3, start_idx=0, total_lines=3)
        safe_addstr.assert_not_called()

    def test_draw_live_cursor_visibility_rules(self):
        win = self._make_window()
        win.active = True
        win._line_chars = list("abc")
        win._cursor_col = 1
        win.scrollback_offset = 0

        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win._draw_live_cursor(
                stdscr=None,
                x=4,
                y=5,
                text_cols=29,
                text_rows=7,
                start_idx=0,
                total_lines=1,
                body_attr=10,
            )
        self.assertTrue(
            any(
                len(call.args) >= 5
                and call.args[1] == 5
                and call.args[2] == 5
                and call.args[3] == "b"
                and (call.args[4] & self.curses.A_REVERSE)
                for call in safe_addstr.call_args_list
            )
        )

        win.scrollback_offset = 2
        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win._draw_live_cursor(None, 4, 5, 29, 7, 0, 1, 10)
        safe_addstr.assert_not_called()

        win.scrollback_offset = 0
        win.active = False
        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win._draw_live_cursor(None, 4, 5, 29, 7, 0, 1, 10)
        safe_addstr.assert_not_called()

    def test_draw_live_cursor_clamps_and_skips_outside_view(self):
        win = self._make_window()
        win.active = True
        win.scrollback_offset = 0
        win._line_chars = list("xy")
        win._cursor_col = 500

        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win._draw_live_cursor(None, 4, 5, 3, 2, 0, 1, 7)
        self.assertTrue(
            any(
                len(call.args) >= 5
                and call.args[2] == 6
                and call.args[3] == "_"
                and (call.args[4] & self.curses.A_BOLD)
                for call in safe_addstr.call_args_list
            )
        )

        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win._draw_live_cursor(None, 4, 5, 3, 1, 0, 0, 7)
        safe_addstr.assert_not_called()

        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win._draw_live_cursor(None, 4, 5, 3, 1, 0, 3, 7)
        safe_addstr.assert_not_called()

    def test_draw_live_cursor_uses_underscore_on_blank_cell(self):
        win = self._make_window()
        win.active = True
        win.scrollback_offset = 0
        win._line_chars = list("abc")
        win._cursor_col = 10

        with mock.patch.object(self.terminal_mod, "safe_addstr") as safe_addstr:
            win._draw_live_cursor(None, 4, 5, 12, 3, 0, 1, 9)
        self.assertTrue(
            any(
                len(call.args) >= 5
                and call.args[3] == "_"
                and (call.args[4] & self.curses.A_BOLD)
                for call in safe_addstr.call_args_list
            )
        )

    def test_key_to_input_mapping_covers_special_and_printable(self):
        win = self._make_window()

        self.assertEqual(win._key_to_input(self.curses.KEY_UP, self.curses.KEY_UP), "\x1b[A")
        self.assertEqual(win._key_to_input(self.curses.KEY_DC, self.curses.KEY_DC), "\x1b[3~")
        self.assertEqual(win._key_to_input(10, 10), "\r")
        self.assertEqual(win._key_to_input(127, 127), "\x7f")
        self.assertEqual(win._key_to_input(9, 9), "\t")
        self.assertEqual(win._key_to_input(3, 3), "\x03")
        self.assertEqual(win._key_to_input("\n", 999), "\r")
        self.assertEqual(win._key_to_input("\t", 999), "\t")
        self.assertEqual(win._key_to_input("x", ord("x")), "x")
        self.assertEqual(win._key_to_input(65, 65), "A")
        self.assertIsNone(win._key_to_input("\x00", None))
        self.assertIsNone(win._key_to_input(None, 500))

    def test_execute_menu_action_paths(self):
        win = self._make_window()
        win._scroll_lines = ["line"]
        win._line_chars = list("tail")
        win._cursor_col = 4
        win.scrollback_offset = 9

        self.assertIsNone(win._execute_menu_action(win.MENU_CLEAR))
        self.assertEqual(win._scroll_lines, [])
        self.assertEqual(win._line_chars, [])
        self.assertEqual(win._cursor_col, 0)
        self.assertEqual(win.scrollback_offset, 0)

        win._session = _FakeSession()
        result = win._execute_menu_action(win.MENU_RESTART)
        self.assertIsNone(result)
        self.assertIsNone(win._session)

        close_result = win._execute_menu_action(self.actions_mod.AppAction.CLOSE_WINDOW)
        self.assertEqual(close_result.type, self.actions_mod.ActionType.EXECUTE)
        self.assertEqual(close_result.payload, self.actions_mod.AppAction.CLOSE_WINDOW)
        self.assertIsNone(win._execute_menu_action("unknown"))

    def test_handle_key_menu_and_forwarding_and_write_error(self):
        win = self._make_window()
        win.window_menu = types.SimpleNamespace(active=True, handle_key=mock.Mock(return_value=win.MENU_CLEAR))
        self.assertIsNone(win.handle_key("x"))
        win.window_menu = types.SimpleNamespace(active=True, handle_key=mock.Mock(return_value=None))
        self.assertIsNone(win.handle_key("x"))

        win.window_menu = types.SimpleNamespace(active=False)
        fake_session = _FakeSession()
        win._session = fake_session
        win.scrollback_offset = 4
        self.assertIsNone(win.handle_key(self.curses.KEY_RIGHT))
        self.assertEqual(fake_session.writes[-1], "\x1b[C")
        self.assertEqual(win.scrollback_offset, 0)

        failing_session = types.SimpleNamespace(running=True, write=mock.Mock(side_effect=OSError("ioerr")))
        win._session = failing_session
        win.handle_key("a")
        self.assertEqual(win._session_error, "ioerr")
        self.assertIsNone(win.handle_key(object()))

    def test_handle_key_ctrl_v_pastes_clipboard_into_session(self):
        win = self._make_window()
        win.window_menu = types.SimpleNamespace(active=False)
        fake_session = _FakeSession()
        win._session = fake_session
        win.scrollback_offset = 3
        with mock.patch.object(self.terminal_mod, "paste_text", return_value="echo hi"):
            self.assertIsNone(win.handle_key(22))
        self.assertEqual(fake_session.writes[-1], "echo hi")
        self.assertEqual(win.scrollback_offset, 0)

    def test_handle_key_ctrl_v_noop_when_clipboard_empty(self):
        win = self._make_window()
        win.window_menu = types.SimpleNamespace(active=False)
        fake_session = _FakeSession()
        win._session = fake_session
        with mock.patch.object(self.terminal_mod, "paste_text", return_value=""):
            self.assertIsNone(win.handle_key(22))
        self.assertEqual(fake_session.writes, [])

    def test_forward_payload_ignores_none(self):
        win = self._make_window()
        with mock.patch.object(win, "_ensure_session") as ensure_session:
            win._forward_payload(None)
        ensure_session.assert_not_called()

    def test_handle_key_without_running_session_is_noop(self):
        win = self._make_window()
        win.window_menu = types.SimpleNamespace(active=False)
        win._session = types.SimpleNamespace(running=False, write=mock.Mock())
        self.assertIsNone(win.handle_key("a"))
        win._session.write.assert_not_called()

    def test_handle_click_menu_and_body_paths(self):
        win = self._make_window()
        menu = types.SimpleNamespace(
            active=True,
            on_menu_bar=mock.Mock(return_value=True),
            handle_click=mock.Mock(return_value=self.actions_mod.AppAction.CLOSE_WINDOW),
        )
        win.window_menu = menu
        result = win.handle_click(2, 2)
        self.assertEqual(result.type, self.actions_mod.ActionType.EXECUTE)

        menu.handle_click = mock.Mock(return_value=None)
        self.assertIsNone(win.handle_click(2, 2))

        menu.on_menu_bar = mock.Mock(return_value=False)
        menu.active = False
        menu.handle_click = mock.Mock(return_value=None)
        win.scrollback_offset = 3
        self.assertIsNone(win.handle_click(5, 6))
        self.assertEqual(win.scrollback_offset, 0)
        self.assertIsNone(win.handle_click(999, 999))

    def test_handle_scroll_bounds(self):
        win = self._make_window()
        win._scroll_lines = [f"L{i}" for i in range(12)]
        win._line_chars = []

        win.handle_scroll("up", steps=100)
        self.assertEqual(win.scrollback_offset, win._max_scrollback_offset(7))
        win.handle_scroll("down", steps=3)
        self.assertEqual(win.scrollback_offset, max(0, win._max_scrollback_offset(7) - 3))
        current = win.scrollback_offset
        win.handle_scroll("noop", steps=2)
        self.assertEqual(win.scrollback_offset, current)

    def test_close_and_restart_reset_session_state(self):
        win = self._make_window()
        fake_session = _FakeSession()
        win._session = fake_session
        win._session_error = "old"
        win._ansi_pending = "esc"
        win._scroll_lines = ["x"]
        win._line_chars = list("y")
        win._cursor_col = 1
        win.scrollback_offset = 2

        win.close()
        self.assertTrue(fake_session.closed)
        self.assertIsNone(win._session)

        win._session = _FakeSession()
        win.restart_session()
        self.assertIsNone(win._session)
        self.assertIsNone(win._session_error)
        self.assertEqual(win._ansi_pending, "")
        self.assertEqual(win._scroll_lines, [])
        self.assertEqual(win._line_chars, [])
        self.assertEqual(win._cursor_col, 0)
        self.assertEqual(win.scrollback_offset, 0)


if __name__ == "__main__":
    unittest.main()

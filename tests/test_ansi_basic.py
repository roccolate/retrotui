import unittest
from unittest import mock

from retrotui.core.ansi import AnsiStateMachine
import curses

# Ensure a harmless `has_colors` exists on platforms where curses isn't initialized.
if not hasattr(curses, 'has_colors'):
    curses.has_colors = lambda: False

# Also ensure the imported ansi module's curses has a safe has_colors callable
import retrotui.core.ansi as _ansi_mod
if not hasattr(_ansi_mod.curses, 'has_colors'):
    _ansi_mod.curses.has_colors = lambda: False

# Provide a no-op color_pair when curses isn't initialized; without this the
# fg*bg combo path in _update_attr raises _curses.error under test runners
# that don't call initscr().
if not hasattr(curses, 'color_pair') or curses.color_pair.__class__.__name__ != 'function':
    curses.color_pair = lambda n: int(n)


class AnsiBasicTests(unittest.TestCase):
    def test_parse_text_and_control(self):
        s = AnsiStateMachine()
        out = list(s.parse_chunk('Hello\n'))
        # 'H','e','l','l','o' as TEXT then CONTROL for newline
        self.assertEqual(out[0][0], 'TEXT')
        self.assertEqual(out[-1][0], 'CONTROL')

    def test_sgr_bold_and_reset(self):
        s = AnsiStateMachine()
        seq = '\x1b[1mA\x1b[0mB'
        out = list(s.parse_chunk(seq))
        # Find the 'A' TEXT entry and its attr should include A_BOLD
        text_entries = [t for t in out if t[0] == 'TEXT']
        # Expect 'A' then 'B'
        self.assertEqual(text_entries[0][1], 'A')
        self.assertTrue(text_entries[0][2] & curses.A_BOLD)
        self.assertEqual(text_entries[1][1], 'B')
        # After reset, B should not have bold
        self.assertEqual(text_entries[1][2] & curses.A_BOLD, 0)

    def test_sgr_background_and_default_resets(self):
        s = AnsiStateMachine()
        list(s.parse_chunk('\x1b[31;44mX'))
        self.assertEqual(s.fg, 1)
        self.assertEqual(s.bg, 4)

        list(s.parse_chunk('\x1b[39;49mY'))
        self.assertEqual(s.fg, -1)
        self.assertEqual(s.bg, -1)

    def test_sgr_fg_bg_combined_uses_fgbg_pair(self):
        """When both fg and bg are explicit, the attr must encode both via
        a fg*bg combo pair (not just the fg-only pair). This guards B2."""
        from retrotui.core.ansi import C_ANSI_FGBG_START, C_ANSI_START
        # Real curses encodes pair N in the A_COLOR bits (0xff00 on ncurses).
        # Mock with the same encoding so pair numbers can be read back out.
        _A_COLOR = 0xff00

        def _mock_pair(n):
            return (int(n) << 8) & _A_COLOR

        with mock.patch.object(curses, 'has_colors', return_value=True), \
             mock.patch.object(curses, 'color_pair', side_effect=_mock_pair):
            s = AnsiStateMachine()
            list(s.parse_chunk('\x1b[31;44m'))  # fg=1, bg=4
            events = list(s.parse_chunk('Z'))
            z_entry = next(t for t in events if t[0] == 'TEXT' and t[1] == 'Z')
            pair_num = (z_entry[2] & _A_COLOR) >> 8
            expected_combo_num = C_ANSI_FGBG_START + 1 * 8 + 4  # 70
            fg_only_num = C_ANSI_START + 1  # 51
            self.assertEqual(
                pair_num, expected_combo_num,
                "attr must select fg*bg combo pair (B2)",
            )
            self.assertNotEqual(
                pair_num, fg_only_num,
                "attr must not be the fg-only pair when bg is explicit (B2)",
            )

    def test_csi_dispatch_and_params(self):
        s = AnsiStateMachine()
        # CSI sequence that is not SGR should yield a CSI event
        out = list(s.parse_chunk('\x1b[2J'))
        # should contain ('CSI','J',[2])
        csi = [t for t in out if t[0] == 'CSI']
        self.assertTrue(len(csi) >= 1)
        self.assertEqual(csi[0][1], 'J')
        self.assertEqual(csi[0][2], [2])

    def test_osc_consumed_and_multichunk_csi(self):
        s = AnsiStateMachine()
        # OSC should be consumed without yielding
        out = list(s.parse_chunk('\x1b]0;title\x07'))
        self.assertFalse(any(t[0] == 'OSC' for t in out))

        # Multi-chunk CSI: feed escape then rest
        part1 = '\x1b['
        part2 = '3'
        part3 = '1mX'
        out1 = list(s.parse_chunk(part1))
        self.assertEqual(out1, [])
        out2 = list(s.parse_chunk(part2))
        self.assertEqual(out2, [])
        out3 = list(s.parse_chunk(part3))
        texts = [t for t in out3 if t[0] == 'TEXT']
        self.assertTrue(any(t[1] == 'X' for t in texts))

    def test_single_byte_esc_dispatch_and_multichunk_state(self):
        state = AnsiStateMachine()
        events = list(state.parse_chunk("\x1bD\x1bE\x1bM\x1bH\x1b7\x1b8"))
        self.assertEqual(
            [(kind, data) for kind, data, _ in events],
            [("ESC", value) for value in "DEMH78"],
        )

        split = AnsiStateMachine()
        self.assertEqual(list(split.parse_chunk("\x1b")), [])
        self.assertEqual(list(split.parse_chunk("M")), [("ESC", "M", 0)])

    def test_osc_backslashes_remain_payload_until_bel_or_st(self):
        state = AnsiStateMachine()
        events = list(state.parse_chunk("\x1b]0;C:\\Users\\rocco\x07X"))
        self.assertEqual(
            [data for kind, data, _attr in events if kind == "TEXT"],
            ["X"],
        )

        split = AnsiStateMachine()
        self.assertEqual(list(split.parse_chunk("\x1b]0;title\x1b")), [])
        self.assertEqual(split.state, "OSC_ESC")
        self.assertEqual(list(split.parse_chunk("\\")), [])
        self.assertEqual(split.state, "TEXT")
        self.assertEqual(list(split.parse_chunk("Y")), [("TEXT", "Y", 0)])

        continued = AnsiStateMachine()
        events = list(continued.parse_chunk("\x1b]0;part\x1bXstill\x07Z"))
        self.assertEqual(
            [data for kind, data, _attr in events if kind == "TEXT"],
            ["Z"],
        )
        self.assertEqual(continued.state, "TEXT")


if __name__ == '__main__':
    unittest.main()

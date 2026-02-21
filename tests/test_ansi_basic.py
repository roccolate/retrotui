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


if __name__ == '__main__':
    unittest.main()

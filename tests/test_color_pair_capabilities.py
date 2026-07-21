"""Regression coverage for curses backends with limited COLOR_PAIRS."""

from __future__ import annotations

import types
import unittest

from retrotui.color_pairs import (
    LEGACY_COLOR_PAIR_CAPACITY,
    install_color_pair_negotiation,
)
from retrotui.constants import C_ANSI_FGBG_START, C_ANSI_START
from retrotui.theme import ROLE_TO_PAIR_ID, get_theme


class _FakeCurses(types.SimpleNamespace):
    def __init__(self, color_pairs):
        super().__init__()
        self.COLOR_PAIRS = color_pairs
        self.calls = []
        self.color_calls = []
        self.start_calls = 0
        self.start_color = self._start_color
        self.init_pair = self._init_pair
        self.color_pair = self._color_pair

    def _start_color(self):
        self.start_calls += 1

    def _init_pair(self, pair_id, fg, bg):
        if not 0 < pair_id < self.COLOR_PAIRS:
            raise RuntimeError(f"pair {pair_id} exceeds {self.COLOR_PAIRS}")
        self.calls.append((pair_id, fg, bg))

    def _color_pair(self, pair_id):
        self.color_calls.append(pair_id)
        return pair_id << 8


def _initialize_like_utils(fake, theme_key="win31"):
    """Replay the pair requests made by utils.init_colors()."""
    fake.start_color()
    pair_map = get_theme(theme_key).pairs_base

    for role, pair_id in ROLE_TO_PAIR_ID.items():
        fg, bg = pair_map[role]
        fake.init_pair(pair_id, fg, bg)

    term_bg = pair_map.get("terminal", pair_map["window_body"])[1]
    for fg in range(8):
        fake.init_pair(C_ANSI_START + fg, fg, term_bg)

    for fg in range(8):
        for bg in range(8):
            fake.init_pair(C_ANSI_FGBG_START + fg * 8 + bg, fg, bg)


class ColorPairCapabilityTests(unittest.TestCase):
    def test_limited_backend_never_receives_out_of_range_pair(self):
        fake = _FakeCurses(16)
        negotiator = install_color_pair_negotiation(fake)

        _initialize_like_utils(fake)

        self.assertTrue(fake.calls)
        self.assertTrue(all(0 < pair_id < 16 for pair_id, _fg, _bg in fake.calls))
        self.assertLessEqual(len(negotiator.snapshot()["actual_definitions"]), 15)
        self.assertTrue(negotiator.snapshot()["compact"])

        # Semantic roles are compacted first, so even late roles such as error
        # retain a valid pair when duplicate theme combinations free slots.
        error_pair = negotiator.resolve_pair_id(ROLE_TO_PAIR_ID["error"])
        self.assertGreater(error_pair, 0)
        self.assertLess(error_pair, 16)

        # ANSI combinations that do not fit degrade to another negotiated pair
        # or pair zero, but never leak the legacy ID 121 to the backend.
        last_ansi_pair = negotiator.resolve_pair_id(C_ANSI_FGBG_START + 63)
        self.assertGreaterEqual(last_ansi_pair, 0)
        self.assertLess(last_ansi_pair, 16)
        fake.color_pair(C_ANSI_FGBG_START + 63)
        self.assertLess(fake.color_calls[-1], 16)

    def test_duplicate_theme_combinations_share_one_actual_pair(self):
        fake = _FakeCurses(16)
        negotiator = install_color_pair_negotiation(fake)

        _initialize_like_utils(fake)

        self.assertEqual(
            negotiator.resolve_pair_id(ROLE_TO_PAIR_ID["menubar"]),
            negotiator.resolve_pair_id(ROLE_TO_PAIR_ID["menu_item"]),
        )
        self.assertEqual(
            negotiator.resolve_pair_id(ROLE_TO_PAIR_ID["window_body"]),
            negotiator.resolve_pair_id(ROLE_TO_PAIR_ID["button"]),
        )

    def test_full_backend_preserves_legacy_pair_ids(self):
        fake = _FakeCurses(LEGACY_COLOR_PAIR_CAPACITY)
        negotiator = install_color_pair_negotiation(fake)

        _initialize_like_utils(fake)

        self.assertFalse(negotiator.snapshot()["compact"])
        self.assertEqual(negotiator.resolve_pair_id(C_ANSI_START + 1), C_ANSI_START + 1)
        self.assertEqual(
            negotiator.resolve_pair_id(C_ANSI_FGBG_START + 63),
            C_ANSI_FGBG_START + 63,
        )
        self.assertIn((C_ANSI_FGBG_START + 63, 7, 7), fake.calls)

    def test_pair_zero_is_used_when_backend_has_no_allocatable_pairs(self):
        fake = _FakeCurses(1)
        negotiator = install_color_pair_negotiation(fake)

        _initialize_like_utils(fake)

        self.assertEqual(fake.calls, [])
        self.assertEqual(negotiator.resolve_pair_id(1), 0)
        self.assertEqual(negotiator.resolve_pair_id(121), 0)
        self.assertEqual(fake.color_pair(121), 0)

    def test_first_definition_wins_until_start_color_resets_generation(self):
        fake = _FakeCurses(LEGACY_COLOR_PAIR_CAPACITY)
        negotiator = install_color_pair_negotiation(fake)

        fake.start_color()
        fake.init_pair(60, 1, 2)
        fake.init_pair(60, 3, 4)
        self.assertEqual(fake.calls, [(60, 1, 2)])
        self.assertEqual(negotiator.resolve_pair_id(60), 60)

        fake.start_color()
        fake.init_pair(60, 3, 4)
        self.assertEqual(fake.calls[-1], (60, 3, 4))
        self.assertEqual(fake.start_calls, 2)

    def test_missing_color_pairs_keeps_legacy_test_compatibility(self):
        fake = _FakeCurses(LEGACY_COLOR_PAIR_CAPACITY)
        del fake.COLOR_PAIRS
        negotiator = install_color_pair_negotiation(fake)

        fake.start_color()
        fake.init_pair(121, 7, 7)

        self.assertEqual(negotiator.color_pair_capacity(), LEGACY_COLOR_PAIR_CAPACITY)
        self.assertEqual(negotiator.resolve_pair_id(121), 121)


if __name__ == "__main__":
    unittest.main()

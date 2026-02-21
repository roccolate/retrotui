import unittest
import curses

from retrotui.apps.solitaire import SolitaireWindow
from retrotui.core.actions import ActionType, AppAction


class SolitaireBasicTests(unittest.TestCase):
    def test_rank_suit_and_color_helpers(self):
        w = SolitaireWindow(0, 0, 80, 24)
        self.assertEqual(w._rank_value('A H'.replace(' ', '')), 1)
        self.assertEqual(w._rank_value('10S'), 10)
        self.assertEqual(w._rank_value('JH'), 11)
        self.assertEqual(w._suit('10S'), 'S')
        self.assertTrue(w._is_red('H'))
        self.assertFalse(w._is_red('S'))

    def test_can_move_to_foundation_and_place_sequence(self):
        w = SolitaireWindow(0, 0, 80, 24)
        # empty foundation accepts Ace
        self.assertTrue(w._can_move_to_foundation('AH', []))

        # can place QH on KS (different color and K == Q+1)
        self.assertTrue(w._can_place_sequence_on('KS', 'QH'))
        # placing on None requires King
        self.assertTrue(w._can_place_sequence_on(None, 'KS'))

    def test_auto_move_to_foundation_from_waste_and_column(self):
        w = SolitaireWindow(0, 0, 80, 24)
        # waste move
        w.waste = ['AH']
        moved = w._auto_move_to_foundation()
        self.assertTrue(moved)
        self.assertEqual(len(w.foundations[0]), 1)

        # column move: prepare a column with a face-up Ace
        w = SolitaireWindow(0, 0, 80, 24)
        w.columns[0] = [('AH', True)]
        moved = w._auto_move_to_foundation()
        self.assertTrue(moved)
        self.assertEqual(len(w.foundations[0]), 1)

    def test_execute_action_new_and_key_r(self):
        w = SolitaireWindow(0, 0, 80, 24)
        w.moves = 5
        res = w.execute_action('solitaire_new')
        self.assertIsNotNone(res)
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertEqual(w.moves, 0)

        # handle_key 'r' also triggers new game
        res2 = w.handle_key(ord('r'))
        self.assertIsNotNone(res2)
        self.assertEqual(res2.type, ActionType.REFRESH)

    def test_handle_click_stock_moves_to_waste(self):
        w = SolitaireWindow(0, 0, 80, 24)
        # set predictable stock and place a rect covering (3,3)
        w.stock = ['2H']
        w.card_rects = {('stock', 0, 0): (2, 2, 5, 3)}
        w.handle_click(3, 3)
        self.assertEqual(w.stock, [])
        self.assertEqual(w.waste[-1], '2H')
        self.assertEqual(w.moves, 1)

    def test_check_victory_updates_best_moves(self):
        w = SolitaireWindow(0, 0, 80, 24)
        # Fill foundations to 52 cards
        ranks = ['A'] + [str(i) for i in range(2, 11)] + ['J', 'Q', 'K']
        suits = ('H', 'D', 'C', 'S')
        for i in range(4):
            for r in ranks:
                w.foundations[i].append(r + suits[i])

        w.moves = 5
        w.best_moves = 10
        # stub saving to avoid filesystem writes
        w._save_high_scores = lambda: None
        w._check_victory()
        self.assertTrue(w.victory)
        self.assertEqual(w.best_moves, 5)


if __name__ == '__main__':
    unittest.main()

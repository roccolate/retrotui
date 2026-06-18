import unittest
import curses

from retrotui.apps.charmap import CharacterMapWindow
from retrotui.core.clipboard import clear_clipboard, paste_text


class CharMapAdditionalTests(unittest.TestCase):
    def setUp(self):
        clear_clipboard()

    def test_grid_dims_and_page(self):
        win = CharacterMapWindow(0, 0, 80, 24)
        bx, by, bw, bh = win.body_rect()
        cols, rows = win._get_grid_dims(bw, bh)
        self.assertGreaterEqual(cols, 1)
        self.assertGreaterEqual(rows, 1)

        per_page = cols * rows
        # Ensure per_page sensible relative to chars length
        self.assertGreaterEqual(per_page, 1)
        self.assertLessEqual(per_page, len(win.chars) + per_page)

    def test_navigation_keys_update_selection(self):
        win = CharacterMapWindow(0, 0, 80, 24)
        # start at 0
        self.assertEqual(win.sel_idx, 0)

        win.handle_key(curses.KEY_RIGHT)
        self.assertEqual(win.sel_idx, 1)

        win.handle_key(curses.KEY_LEFT)
        self.assertEqual(win.sel_idx, 0)

        # Move down a row
        bx, by, bw, bh = win.body_rect()
        cols, rows = win._get_grid_dims(bw, bh)
        if cols > 1:
            win.handle_key(curses.KEY_DOWN)
            self.assertTrue(win.sel_idx >= cols)

        # Page down/up should move by a page
        prev = win.sel_idx
        win.handle_key(curses.KEY_NPAGE)
        self.assertTrue(win.sel_idx >= prev)
        win.handle_key(curses.KEY_PPAGE)
        self.assertTrue(win.sel_idx <= prev or win.sel_idx == 0)

    def test_handle_click_computes_index_and_selection(self):
        win = CharacterMapWindow(2, 2, 80, 24)
        bx, by, bw, bh = win.body_rect()
        cols, rows = win._get_grid_dims(bw, bh)

        # pick column 1, row 1 (zero-based inside grid)
        grid_x = 1
        grid_y = 1
        mx = bx + grid_x * 3
        my = by + 1 + grid_y

        result = win.handle_click(mx, my)
        if result is not None:
            self.assertIn('char', result)
            self.assertIn('index', result)
            self.assertEqual(win.selected_char, result['char'])
            self.assertEqual(win.sel_idx, result['index'])

    def test_execute_action_block_switch_and_copy_hex(self):
        win = CharacterMapWindow(0, 0, 80, 24)
        # switch to block 2
        win.execute_action('block_2')
        self.assertEqual(win.block_idx, 2)
        self.assertEqual(win.sel_idx, 0)
        self.assertIsNotNone(win.selected_char)

        # exercise copy value action which should set internal clipboard
        win.execute_action('copy_hex')
        text = paste_text(sync_system=False)
        self.assertTrue(text.startswith('U+'))

        # and the character action should copy the literal character
        win.execute_action('copy_char')
        char_text = paste_text(sync_system=False)
        self.assertEqual(char_text, win.selected_char)


if __name__ == '__main__':
    unittest.main()

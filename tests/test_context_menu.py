import sys
import unittest
from unittest import mock

from _support import make_fake_curses

# ensure a consistent fake curses implementation
_prev = sys.modules.get('curses')
sys.modules['curses'] = make_fake_curses()

from retrotui.ui.context_menu import ContextMenu


class FakeStdScr:
    def __init__(self):
        self.calls = []

    def getmaxyx(self):
        return (24, 80)

    def addnstr(self, y, x, text, max_len, attr=None):
        self.calls.append((y, x, text[:max_len], attr))

    def addstr(self, y, x, text, attr=None):
        self.addnstr(y, x, text, len(text), attr)


class ContextMenuTests(unittest.TestCase):
    def test_draw_and_escape_closes(self):
        std = FakeStdScr()
        items = [('One', 'a1'), ('---', None), ('Two', 'a2')]
        cm = ContextMenu(items)
        cm.open_at(5, 3)

        # patch safe_addstr to route to our fake std
        with mock.patch('retrotui.ui.context_menu.safe_addstr') as fake_sa:
            fake_sa.side_effect = lambda s, y, x, t, a=None: std.addstr(y, x, t, a)
            cm.draw(std)

        # ensure drawing happened
        self.assertTrue(any('One' in c[2] for c in std.calls))

        # escape should close
        res = cm.handle_key(27)
        self.assertIsNone(res)
        self.assertFalse(cm.is_open())

    def test_click_outside_closes(self):
        std = FakeStdScr()
        items = [('Open', 'o'), ('Delete', 'd')]
        cm = ContextMenu(items)
        cm.open_at(2, 2)

        # click outside
        res = cm.handle_click(0, 0)
        self.assertIsNone(res)
        self.assertFalse(cm.is_open())

    def test_click_inside_selects_item(self):
        items = [('A', 'a'), ('B', 'b')]
        cm = ContextMenu(items)
        cm.open_at(10, 5)

        # click on second item (y = open_y + 1 + index)
        res = cm.handle_click(11, 5 + 1 + 1)
        self.assertEqual(res, 'b')


if __name__ == '__main__':
    unittest.main()

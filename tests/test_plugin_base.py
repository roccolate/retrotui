import sys
import types

# minimal fake curses
fake = types.ModuleType("curses")
fake.A_BOLD = 1
fake.A_REVERSE = 2
fake.A_DIM = 4
fake.COLOR_WHITE = 7
fake.COLORS = 16
fake.error = Exception
fake.color_pair = lambda _: 0
fake.can_change_color = lambda: False
fake.start_color = lambda: None
fake.use_default_colors = lambda: None
fake.init_color = lambda *_: None
fake.init_pair = lambda *_: None
sys.modules['curses'] = fake

from retrotui.plugins.base import RetroApp


class DummyApp(RetroApp):
    def __init__(self):
        super().__init__('Dummy', 1, 1, 20, 10)
        self._drawn = False

    def draw_content(self, stdscr, x, y, w, h):
        self._drawn = True


def test_draw_delegates_to_draw_content():
    win = DummyApp()
    # fake curses window object
    class FakeWin:
        def getmaxyx(self):
            return (24, 80)
        def addnstr(self, *a, **k):
            return

    fake = FakeWin()
    win.draw(fake)
    assert getattr(win, '_drawn', False) is True

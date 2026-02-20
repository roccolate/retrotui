import sys
sys.path.insert(0, 'tests')
from _support import make_fake_curses
sys.modules['curses'] = make_fake_curses()
from retrotui.apps.solitaire import SolitaireWindow

win = SolitaireWindow(0, 0, 60, 20)
# mock draw_frame and safe_addstr
win.draw_frame = lambda x: 0
import retrotui.apps.solitaire as sol
sol.safe_addstr = lambda *args: None
win.draw(None)
print("waste rect:", win.card_rects.get(("waste", 0, 0)))
print("col 0 top rect:", win.card_rects.get(("col", 0, 0)))

print("\nTesting test_init_draw_and_click click:")
print("clicking (3, 6)")
win.handle_click(3, 6)
print("selected:", win.selected)

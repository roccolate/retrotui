import curses

from retrotui.ui.context_menu import ContextMenu


def test_context_menu_draw_runs_without_error():
    cm = ContextMenu(theme=None)
    items = [
        {'label': 'One', 'action': 'a'},
        {'separator': True},
        {'label': 'Two', 'action': 'b'},
    ]
    cm.show(1, 1, items)
    cm.selected_index = 0

    class DummyStdScr:
        def getmaxyx(self):
            return (24, 80)

        def addstr(self, *args, **kwargs):
            return None

        def addch(self, *args, **kwargs):
            return None

        def attron(self, *args, **kwargs):
            return None

        def attroff(self, *args, **kwargs):
            return None

    stdscr = DummyStdScr()
    # Should not raise even if curses functions are used internally
    cm.draw(stdscr)

    # Move selection to second item and draw again
    cm.selected_index = 2
    cm.draw(stdscr)

    # Show off-screen negative coords should clamp and not raise
    cm.show(-5, -3, items)
    cm.draw(stdscr)

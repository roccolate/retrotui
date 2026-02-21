import curses

from retrotui.ui.context_menu import ContextMenu


class DummyTheme:
    pass


def make_items():
    return [
        {"label": "Open", "action": "open"},
        {"separator": True},
        {"label": "Close", "action": "close"},
    ]


def test_context_menu_show_hide_and_width():
    cm = ContextMenu(DummyTheme())
    items = make_items()
    cm.show(5, 5, items)
    assert cm.is_open()
    assert cm._width >= 4
    cm.hide()
    assert not cm.is_open()


def test_context_menu_keyboard_navigation_and_select():
    cm = ContextMenu(DummyTheme())
    items = make_items()
    cm.show(0, 0, items)

    # simulate down then enter (should select 'Close')
    cm.handle_input(curses.KEY_DOWN)
    res = cm.handle_input(10)  # Enter
    assert res == "close"
    assert not cm.is_open()


def test_context_menu_clicks_inside_and_outside():
    cm = ContextMenu(DummyTheme())
    items = make_items()
    cm.show(2, 2, items)

    # click inside first item (row 3 accounting for top border)
    res = cm.handle_click(3, 3)
    assert res == "open"

    cm.show(2, 2, items)
    # click outside closes and returns None
    res2 = cm.handle_click(100, 100)
    assert res2 is None
    assert not cm.is_open()

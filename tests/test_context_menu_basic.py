import curses

from retrotui.ui.context_menu import ContextMenu


def test_context_menu_navigation_and_select():
    cm = ContextMenu(theme=None)
    items = [
        {'label': 'One', 'action': 'a'},
        {'separator': True},
        {'label': 'Two', 'action': 'b'},
    ]

    cm.show(5, 5, items)
    assert cm.is_open()
    assert cm._width >= len('One') + 4

    # Move down should skip separator and land on 'Two'
    cm.handle_input(curses.KEY_DOWN)
    assert cm.selected_index == 2

    # Move up should skip separator and return to 'One'
    cm.handle_input(curses.KEY_UP)
    assert cm.selected_index == 0

    # Press enter to select current item
    res = cm.handle_input(10)  # 10 == Enter
    assert res == 'a'
    assert not cm.is_open()


def test_context_menu_clicks():
    cm = ContextMenu(theme=None)
    items = [
        {'label': 'A', 'action': 'act_a'},
        {'label': 'B', 'action': 'act_b'},
    ]
    cm.show(10, 10, items)

    # Click first item
    mx = 11
    my = 11  # y + 1 is first item row
    res = cm.handle_click(mx, my)
    assert res == 'act_a'
    assert not cm.is_open()

    # Clicking outside should close and return None
    cm.show(0, 0, items)
    res2 = cm.handle_click(-1, -1)
    assert res2 is None
    assert not cm.is_open()
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

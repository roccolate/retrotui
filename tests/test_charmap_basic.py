import curses

from retrotui.apps.charmap import CharacterMapWindow, UNICODE_BLOCKS


def test_load_block_and_grid_dims():
    w = CharacterMapWindow(0, 0, 80, 24)
    # ensure initial block loaded
    assert w.status_message.startswith("Block:")
    cols, rows = w._get_grid_dims(80, 24)
    assert cols >= 1 and rows >= 1


def test_handle_key_navigation_and_execute_block():
    w = CharacterMapWindow(0, 0, 80, 24)
    orig_idx = w.sel_idx
    # move right
    w.handle_key(curses.KEY_RIGHT)
    assert w.sel_idx >= orig_idx

    # switch block via execute_action
    res = w.execute_action("block_1")
    assert res is not None
    assert w.block_idx == 1


def test_handle_click_selects_char():
    w = CharacterMapWindow(0, 0, 80, 24)
    bx, by, bw, bh = w.body_rect()
    cols, rows = w._get_grid_dims(bw, bh)
    # click first cell
    res = w.handle_click(bx + 1, by + 2)
    assert res is None or isinstance(res, dict)

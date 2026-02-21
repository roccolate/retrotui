from types import SimpleNamespace

from retrotui.core.window_manager import WindowManager


def make_win(name, visible=True, always_on_top=False):
    w = SimpleNamespace(name=name, visible=visible, active=False, always_on_top=always_on_top)
    def close():
        w.closed = True
    w.close = close
    return w


def test_window_activation_and_layers():
    wm = WindowManager(None)
    w1 = make_win('a')
    w2 = make_win('b', always_on_top=True)
    w3 = make_win('c')
    wm.windows = [w1, w2, w3]

    wm.set_active_window(w1)
    assert w1.active
    # active window moved into correct position preserving always_on_top
    assert wm.get_active_window() is not None

    wm.normalize_window_layers()
    # always_on_top should be at the end
    assert wm.windows[-1].always_on_top

    # close window removes it and activates last visible
    wm.close_window(w1)
    assert all(getattr(x, 'closed', False) or x is not w1 for x in [w1])

def test_spawn_and_offset():
    wm = WindowManager(None)
    w = make_win('x')
    wm._spawn_window(w)
    assert w in wm.windows
    x, y = wm._next_window_offset(1, 2)
    assert isinstance(x, int) and isinstance(y, int)

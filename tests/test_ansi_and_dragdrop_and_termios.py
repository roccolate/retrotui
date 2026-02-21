import curses
from retrotui.core.ansi import AnsiStateMachine
from retrotui.core.drag_drop import DragDropManager
from retrotui.core.win_termios import cfmakeraw
from types import SimpleNamespace


def test_ansi_parse_text_and_sgr():
    asm = AnsiStateMachine()
    outputs = list(asm.parse_chunk('Hello'))
    assert any(item[0] == 'TEXT' and item[1] == 'H' for item in outputs)

    # Bold on and off via SGR
    asm2 = AnsiStateMachine()
    parts = list(asm2.parse_chunk('\x1b[1mA\x1b[22mB'))
    # Should see CONTROL or TEXT events; state machine should not crash
    assert any(p[0] in ('TEXT', 'CONTROL', 'CSI') for p in parts)


def test_drag_drop_basic():
    app = SimpleNamespace()
    win1 = SimpleNamespace()
    called = {}

    def clearer():
        called['cleared'] = True

    win1.clear_pending_drag = clearer
    win1.open_path = lambda p: None
    win1.visible = True
    win1.contains = lambda mx, my: True

    app.windows = [win1]
    dd = DragDropManager(app)

    dd.clear_pending_file_drags()
    assert called.get('cleared')

    assert dd.supports_file_drop_target(win1)
    dd.set_drag_target(win1)
    assert win1.drop_target_highlight is True
    dd.clear_state()
    assert dd.payload is None and dd.target_window is None


def test_cfmakeraw_modifies_attributes():
    attrs = [0, 0, 0, 0xFFFFFFFF]
    out = cfmakeraw(attrs)
    assert out is attrs
    # ensure ECHO/ICANON/ISIG bits cleared
    assert out[3] & (0x00000008 | 0x00000100 | 0x00000080) == 0

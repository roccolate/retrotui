import unittest
from types import SimpleNamespace
from retrotui.core.window_manager import WindowManager


def make_win(name, visible=True, always_on_top=False):
    w = SimpleNamespace(name=name, visible=visible, active=False, always_on_top=always_on_top)
    def close():
        w.closed = True
    w.close = close
    return w


class WindowManagerTests(unittest.TestCase):
    def test_window_activation_and_layers(self):
        wm = WindowManager(None)
        w1 = make_win('a')
        w2 = make_win('b', always_on_top=True)
        w3 = make_win('c')
        wm.windows = [w1, w2, w3]

        wm.set_active_window(w1)
        self.assertTrue(w1.active)
        # active window moved into correct position preserving always_on_top
        self.assertIsNotNone(wm.get_active_window())

        wm.normalize_window_layers()
        # always_on_top should be at the end
        self.assertTrue(wm.windows[-1].always_on_top)

        # close window removes it and activates last visible
        wm.close_window(w1)
        self.assertTrue(all(getattr(x, 'closed', False) or x is not w1 for x in [w1]))

    def test_spawn_and_offset(self):
        wm = WindowManager(None)
        w = make_win('x')
        wm._spawn_window(w)
        self.assertIn(w, wm.windows)
        x, y = wm._next_window_offset(1, 2)
        self.assertIsInstance(x, int)
        self.assertIsInstance(y, int)

    def test_taskbar_buttons_layout_and_cache(self):
        app = SimpleNamespace(stdscr=SimpleNamespace(getmaxyx=lambda: (20, 80)))
        wm = WindowManager(app)
        one = SimpleNamespace(minimized=True, title="One")
        two = SimpleNamespace(minimized=False, title="Two")
        tri = SimpleNamespace(minimized=True, title="Three")
        wm.windows = [one, two, tri]

        first = wm.taskbar_buttons(80)
        second = wm.taskbar_buttons(80)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertEqual(first[0][2], "One")
        self.assertEqual(first[1][2], "Three")
        self.assertEqual(first[0][0], 1)
        self.assertLess(first[0][0], first[0][1])

    def test_handle_taskbar_click_uses_button_ranges(self):
        activated = []
        app = SimpleNamespace(
            stdscr=SimpleNamespace(getmaxyx=lambda: (20, 80)),
            set_active_window=lambda win: activated.append(win),
        )
        wm = WindowManager(app)
        one = SimpleNamespace(minimized=True, title="One", toggle_minimize=lambda: activated.append("toggle_one"))
        two = SimpleNamespace(minimized=True, title="Two", toggle_minimize=lambda: activated.append("toggle_two"))
        wm.windows = [one, two]

        buttons = wm.taskbar_buttons(80)
        self.assertTrue(buttons)
        start_x, end_x, _label, _win = buttons[1]
        mx = (start_x + end_x) // 2

        self.assertTrue(wm.handle_taskbar_click(mx, 18))
        self.assertIn("toggle_two", activated)
        self.assertIn(two, activated)


if __name__ == "__main__":
    unittest.main()


import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.KEY_MOUSE = 409
    fake.KEY_RESIZE = 410
    fake.error = RuntimeError
    fake.doupdate = mock.Mock()
    fake.update_lines_cols = mock.Mock()
    fake.getmouse = mock.Mock(return_value=(0, 10, 10, 0, 0))
    return fake


class EventLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        cls.fake_curses = _install_fake_curses()
        sys.modules["curses"] = cls.fake_curses
        sys.modules.pop("retrotui.core.event_loop", None)
        cls.event_loop = importlib.import_module("retrotui.core.event_loop")

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("retrotui.core.event_loop", None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _make_app(self):
        stdscr = types.SimpleNamespace(
            erase=mock.Mock(),
            noutrefresh=mock.Mock(),
            getmaxyx=mock.Mock(return_value=(25, 80)),
            get_wch=mock.Mock(return_value="a"),
        )
        win = types.SimpleNamespace(draw=mock.Mock(), x=90, y=40, w=20, h=15)
        app = types.SimpleNamespace(
            stdscr=stdscr,
            draw_desktop=mock.Mock(),
            draw_icons=mock.Mock(),
            draw_taskbar=mock.Mock(),
            draw_statusbar=mock.Mock(),
            menu=types.SimpleNamespace(draw_bar=mock.Mock(), draw_dropdown=mock.Mock()),
            windows=[win],
            dialog=None,
            handle_mouse=mock.Mock(),
            handle_key=mock.Mock(),
            cleanup=mock.Mock(),
            running=True,
        )
        return app

    def test_draw_frame_renders_core_layers(self):
        app = self._make_app()

        self.event_loop.draw_frame(app)

        app.stdscr.erase.assert_called_once_with()
        app.draw_desktop.assert_called_once_with()
        app.draw_icons.assert_called_once_with()
        app.windows[0].draw.assert_called_once_with(app.stdscr)
        app.menu.draw_bar.assert_called_once_with(app.stdscr, 80)
        app.menu.draw_dropdown.assert_called_once_with(app.stdscr)
        app.draw_taskbar.assert_called_once_with()
        app.draw_statusbar.assert_called_once_with()
        app.stdscr.noutrefresh.assert_called_once_with()
        self.fake_curses.doupdate.assert_called_once_with()

    def test_draw_frame_renders_dialog_when_present(self):
        app = self._make_app()
        app.dialog = types.SimpleNamespace(draw=mock.Mock())

        self.event_loop.draw_frame(app)

        app.dialog.draw.assert_called_once_with(app.stdscr)

    def test_read_input_key_returns_none_on_curses_error(self):
        stdscr = types.SimpleNamespace(get_wch=mock.Mock(side_effect=self.fake_curses.error()))

        key = self.event_loop.read_input_key(stdscr)

        self.assertIsNone(key)

    def test_dispatch_input_routes_mouse_event(self):
        app = self._make_app()

        self.event_loop.dispatch_input(app, self.fake_curses.KEY_MOUSE)

        app.handle_mouse.assert_called_once_with((0, 10, 10, 0, 0))

    def test_dispatch_input_ignores_none_key(self):
        app = self._make_app()

        self.event_loop.dispatch_input(app, None)

        app.handle_mouse.assert_not_called()
        app.handle_key.assert_not_called()

    def test_dispatch_input_mouse_error_returns_without_dispatch(self):
        app = self._make_app()
        self.fake_curses.getmouse.side_effect = self.fake_curses.error()
        try:
            self.event_loop.dispatch_input(app, self.fake_curses.KEY_MOUSE)
        finally:
            self.fake_curses.getmouse.side_effect = None

        app.handle_mouse.assert_not_called()

    def test_dispatch_input_resize_clamps_windows(self):
        app = self._make_app()

        self.event_loop.dispatch_input(app, self.fake_curses.KEY_RESIZE)

        self.fake_curses.update_lines_cols.assert_called_once_with()
        self.assertEqual(app.windows[0].x, 60)
        self.assertEqual(app.windows[0].y, 9)

    def test_dispatch_input_routes_regular_key(self):
        app = self._make_app()

        self.event_loop.dispatch_input(app, "x")

        app.handle_key.assert_called_once_with("x")

    def test_run_app_loop_runs_once_and_cleans_up(self):
        app = self._make_app()

        with mock.patch.object(self.event_loop, "draw_frame") as draw_mock:
            with mock.patch.object(self.event_loop, "read_input_key", return_value="a"):
                def _dispatch_once(target, key):
                    target.handle_key(key)
                    target.running = False

                with mock.patch.object(self.event_loop, "dispatch_input", side_effect=_dispatch_once):
                    self.event_loop.run_app_loop(app)

        draw_mock.assert_called_once_with(app)
        app.handle_key.assert_called_once_with("a")
        app.cleanup.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

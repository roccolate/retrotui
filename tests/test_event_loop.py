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

    def setUp(self):
        # fake_curses is shared across tests; reset call history for isolation.
        self.fake_curses.doupdate.reset_mock()
        self.fake_curses.update_lines_cols.reset_mock()
        self.fake_curses.getmouse.reset_mock()

    def _make_app(self):
        stdscr = types.SimpleNamespace(
            erase=mock.Mock(),
            noutrefresh=mock.Mock(),
            getmaxyx=mock.Mock(return_value=(25, 80)),
            get_wch=mock.Mock(return_value="a"),
            timeout=mock.Mock(),
        )
        win = types.SimpleNamespace(draw=mock.Mock(), x=90, y=40, w=20, h=15)
        app = types.SimpleNamespace(
            stdscr=stdscr,
            draw_desktop=mock.Mock(),
            draw_icons=mock.Mock(),
            draw_taskbar=mock.Mock(),
            draw_statusbar=mock.Mock(),
            menu=types.SimpleNamespace(
                draw_bar=mock.Mock(),
                draw_dropdown=mock.Mock(),
                refresh_clock=mock.Mock(return_value=False),
            ),
            windows=[win],
            dialog=None,
            context_menu=None,
            normalize_window_layers=mock.Mock(),
            handle_mouse=mock.Mock(),
            handle_key=mock.Mock(),
            has_background_operation=mock.Mock(return_value=False),
            poll_background_operation=mock.Mock(),
            cleanup=mock.Mock(),
            running=True,
            _install_runtime_signal_handlers=mock.Mock(),
            _consume_pending_signal_key=mock.Mock(return_value=None),
            _consume_pending_sigint=mock.Mock(return_value=None),
            input_timeout_idle_ms=500,
            input_timeout_live_terminal_ms=33,
            input_timeout_background_ms=120,
            _dirty=True,
        )
        return app

    def test_draw_frame_calls_normalize_layers_when_present(self):
        app = self._make_app()

        self.event_loop.draw_frame(app)

        app.normalize_window_layers.assert_called_once_with()

    def test_draw_frame_renders_core_layers(self):
        app = self._make_app()

        self.event_loop.draw_frame(app)

        app.stdscr.getmaxyx.assert_called_once_with()
        app.stdscr.erase.assert_called_once_with()
        app.draw_desktop.assert_called_once_with(frame_size=(25, 80))
        app.draw_icons.assert_called_once_with(frame_size=(25, 80))
        app.windows[0].draw.assert_called_once_with(app.stdscr, frame_size=(25, 80))
        app.menu.draw_bar.assert_called_once_with(app.stdscr, 80, frame_size=(25, 80))
        app.menu.draw_dropdown.assert_called_once_with(app.stdscr, frame_size=(25, 80))
        app.draw_taskbar.assert_called_once_with(frame_size=(25, 80))
        app.draw_statusbar.assert_called_once_with(frame_size=(25, 80))
        app.stdscr.noutrefresh.assert_called_once_with()
        self.fake_curses.doupdate.assert_called_once_with()

    def test_draw_frame_supports_legacy_window_draw_signature(self):
        app = self._make_app()

        class LegacyWindow:
            visible = True

            def __init__(self):
                self.draw_calls = []

            def draw(self, stdscr):
                self.draw_calls.append(stdscr)

        legacy = LegacyWindow()
        app.windows = [legacy]

        self.event_loop.draw_frame(app)

        self.assertEqual(legacy.draw_calls, [app.stdscr])
        self.assertFalse(legacy._retrotui_draw_accepts_frame_size)

    def test_draw_frame_renders_dialog_when_present(self):
        app = self._make_app()
        app.dialog = types.SimpleNamespace(draw=mock.Mock())

        self.event_loop.draw_frame(app)

        app.dialog.draw.assert_called_once_with(app.stdscr, frame_size=(25, 80))

    def test_draw_frame_skips_window_render_when_background_operation_active(self):
        app = self._make_app()
        app.has_background_operation.return_value = True

        self.event_loop.draw_frame(app)

        app.stdscr.getmaxyx.assert_called_once_with()
        app.windows[0].draw.assert_not_called()
        app.menu.draw_bar.assert_called_once_with(app.stdscr, 80, frame_size=(25, 80))

    def test_read_input_key_returns_none_on_curses_error(self):
        stdscr = types.SimpleNamespace(get_wch=mock.Mock(side_effect=self.fake_curses.error()))

        key = self.event_loop.read_input_key(stdscr)

        self.assertIsNone(key)

    def test_read_input_key_maps_keyboard_interrupt_to_ctrl_c(self):
        stdscr = types.SimpleNamespace(get_wch=mock.Mock(side_effect=KeyboardInterrupt()))

        key = self.event_loop.read_input_key(stdscr)

        self.assertEqual(key, "\x03")

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

    def test_select_input_timeout_uses_live_terminal_profile_for_visible_pty(self):
        app = self._make_app()
        app.windows.append(
            types.SimpleNamespace(
                visible=True,
                _session=types.SimpleNamespace(running=True),
            )
        )

        timeout_ms = self.event_loop._select_input_timeout_ms(app)

        self.assertEqual(timeout_ms, self.event_loop.TERMINAL_LIVE_INPUT_TIMEOUT_MS)

    def test_select_input_timeout_uses_background_profile_when_worker_active(self):
        app = self._make_app()
        app.has_background_operation.return_value = True

        timeout_ms = self.event_loop._select_input_timeout_ms(app)

        self.assertEqual(timeout_ms, self.event_loop.TERMINAL_BACKGROUND_INPUT_TIMEOUT_MS)

    def test_select_input_timeout_ignores_hidden_terminal_sessions(self):
        app = self._make_app()
        app.windows.append(
            types.SimpleNamespace(
                visible=False,
                _session=types.SimpleNamespace(running=True),
            )
        )

        timeout_ms = self.event_loop._select_input_timeout_ms(app)

        self.assertEqual(timeout_ms, self.event_loop.TERMINAL_INPUT_TIMEOUT_MS)

    def test_apply_input_timeout_updates_only_when_value_changes(self):
        app = self._make_app()

        self.event_loop._apply_input_timeout(app, 120)
        self.event_loop._apply_input_timeout(app, 120)

        app.stdscr.timeout.assert_called_once_with(120)

    def test_disabled_profiler_avoids_startup_clock_sampling(self):
        app = self._make_app()
        with (
            mock.patch.dict(self.event_loop.os.environ, {}, clear=True),
            mock.patch.object(self.event_loop.time, "perf_counter") as timer,
        ):
            metrics = self.event_loop._ensure_runtime_metrics(app)

        self.assertFalse(metrics["enabled"])
        timer.assert_not_called()

    def test_disabled_profiler_does_not_time_hot_loop_phases(self):
        app = self._make_app()
        app._runtime_metrics = self.event_loop._ensure_runtime_metrics(app)
        app._runtime_metrics["enabled"] = False

        def _dispatch_once(target, key):
            target.running = False
            return False

        with (
            mock.patch.object(self.event_loop, "draw_frame"),
            mock.patch.object(self.event_loop, "read_input_key", return_value=None),
            mock.patch.object(
                self.event_loop,
                "dispatch_input",
                side_effect=_dispatch_once,
            ),
            mock.patch.object(self.event_loop.time, "perf_counter") as timer,
        ):
            self.event_loop.run_app_loop(app)

        timer.assert_not_called()

    def test_runtime_metrics_use_default_for_invalid_profile_interval(self):
        app = self._make_app()

        with mock.patch.dict(
            self.event_loop.os.environ,
            {"RETROTUI_PROFILE_INTERVAL": "not-a-number"},
        ):
            metrics = self.event_loop._ensure_runtime_metrics(app)

        self.assertEqual(metrics["report_interval_s"], 5.0)
        self.assertIn("clock_refreshes", metrics)
        self.assertIn("tick_time_s", metrics)
        self.assertIn("max_draw_time_s", metrics)

    def test_emit_runtime_metrics_uses_default_for_invalid_interval(self):
        metrics = {
            "enabled": True,
            "started_at": 0.0,
            "last_report_at": 0.0,
            "report_interval_s": "not-a-number",
            "loops": 1,
            "redraws": 1,
            "dispatched_events": 1,
        }

        with mock.patch.object(self.event_loop.time, "perf_counter", return_value=10.0):
            with mock.patch.object(self.event_loop.LOGGER, "debug") as debug_mock:
                self.event_loop._emit_runtime_metrics(metrics, final=False)

        debug_mock.assert_called_once()
        self.assertEqual(metrics["last_report_at"], 10.0)

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
        app.poll_background_operation.assert_called_once_with()
        app._install_runtime_signal_handlers.assert_called_once_with()
        app.stdscr.timeout.assert_called_with(self.event_loop.TERMINAL_INPUT_TIMEOUT_MS)
        app.cleanup.assert_called_once_with()

    def test_run_app_loop_consumes_pending_signal_key_when_no_key(self):
        app = self._make_app()
        app._consume_pending_signal_key.return_value = "\x1a"

        with mock.patch.object(self.event_loop, "draw_frame"):
            with mock.patch.object(self.event_loop, "read_input_key", return_value=None):
                def _dispatch_once(target, key):
                    target.handle_key(key)
                    target.running = False

                with mock.patch.object(self.event_loop, "dispatch_input", side_effect=_dispatch_once):
                    self.event_loop.run_app_loop(app)

        app._consume_pending_signal_key.assert_called_once_with()
        app._consume_pending_sigint.assert_not_called()
        app.handle_key.assert_called_once_with("\x1a")

    def test_run_app_loop_falls_back_to_legacy_sigint_consumer(self):
        app = self._make_app()
        app._consume_pending_signal_key = None
        app._consume_pending_sigint.return_value = "\x03"

        with mock.patch.object(self.event_loop, "draw_frame"):
            with mock.patch.object(self.event_loop, "read_input_key", return_value=None):
                def _dispatch_once(target, key):
                    target.handle_key(key)
                    target.running = False

                with mock.patch.object(self.event_loop, "dispatch_input", side_effect=_dispatch_once):
                    self.event_loop.run_app_loop(app)

        app._consume_pending_sigint.assert_called_once_with()
        app.handle_key.assert_called_once_with("\x03")

    def test_run_app_loop_refreshes_only_clock_while_idle(self):
        app = self._make_app()
        app._dirty = False
        app.menu.refresh_clock.side_effect = [True, False]
        state = {"polls": 0}

        def _poll_twice_then_stop():
            state["polls"] += 1
            if state["polls"] >= 2:
                app.running = False

        app.poll_background_operation.side_effect = _poll_twice_then_stop

        with mock.patch.object(self.event_loop, "draw_frame") as draw_mock:
            with mock.patch.object(self.event_loop, "read_input_key", return_value=None):
                with mock.patch.object(self.event_loop, "dispatch_input", return_value=False):
                    self.event_loop.run_app_loop(app)

        draw_mock.assert_not_called()
        self.assertEqual(app.menu.refresh_clock.call_count, 2)
        app.stdscr.noutrefresh.assert_called_once_with()
        self.fake_curses.doupdate.assert_called_once_with()
        self.assertEqual(app._runtime_metrics["redraws"], 0)
        self.assertEqual(app._runtime_metrics["clock_refreshes"], 1)

    def test_run_app_loop_converts_keyboard_interrupt_into_ctrl_c_key(self):
        app = self._make_app()

        with mock.patch.object(self.event_loop, "draw_frame"):
            with mock.patch.object(self.event_loop, "read_input_key", side_effect=[None, "a"]):
                state = {"raised": False}

                def _dispatch(target, key):
                    if not state["raised"]:
                        state["raised"] = True
                        raise KeyboardInterrupt()
                    target.running = False
                    return False

                with mock.patch.object(self.event_loop, "dispatch_input", side_effect=_dispatch):
                    self.event_loop.run_app_loop(app)

        app.handle_key.assert_called_once_with("\x03")


if __name__ == "__main__":
    unittest.main()

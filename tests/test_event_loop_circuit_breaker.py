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


class EventLoopCircuitBreakerTests(unittest.TestCase):
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

    def _make_loop_app(self):
        stdscr = types.SimpleNamespace(
            get_wch=mock.Mock(return_value=None),
            timeout=mock.Mock(),
        )
        return types.SimpleNamespace(
            stdscr=stdscr,
            windows=[],
            menu=types.SimpleNamespace(refresh_clock=mock.Mock(return_value=False)),
            poll_background_operation=mock.Mock(),
            has_background_operation=mock.Mock(return_value=False),
            handle_key=mock.Mock(),
            cleanup=mock.Mock(),
            running=True,
            _dirty=True,
            _notifications=None,
            _install_runtime_signal_handlers=mock.Mock(),
            _consume_pending_signal_key=mock.Mock(return_value=None),
            _consume_pending_sigint=mock.Mock(return_value=None),
            input_timeout_idle_ms=500,
            input_timeout_live_terminal_ms=33,
            input_timeout_periodic_ms=100,
            input_timeout_background_ms=120,
            event_loop_failure_limit=3,
            event_loop_error_backoff_s=0,
        )

    def test_repeated_tick_failure_disables_only_that_tick_hook(self):
        window = types.SimpleNamespace(
            visible=True,
            tick_when_hidden=True,
            wants_periodic_tick=True,
            tick=mock.Mock(side_effect=RuntimeError("broken tick")),
        )
        app = types.SimpleNamespace(windows=[window], event_loop_failure_limit=3)

        for _ in range(4):
            self.event_loop._tick_and_probe_windows(app)

        self.assertEqual(window.tick.call_count, 3)
        self.assertTrue(window._retrotui_tick_disabled)
        self.assertFalse(window.tick_when_hidden)
        self.assertFalse(window.wants_periodic_tick)
        self.assertIsInstance(window._retrotui_tick_first_error, RuntimeError)

    def test_success_resets_component_failure_streak(self):
        window = types.SimpleNamespace(
            visible=True,
            tick_when_hidden=False,
            wants_periodic_tick=True,
            tick=mock.Mock(side_effect=[RuntimeError("once"), False, RuntimeError("again")]),
        )
        app = types.SimpleNamespace(windows=[window], event_loop_failure_limit=3)

        for _ in range(3):
            self.event_loop._tick_and_probe_windows(app)

        self.assertEqual(window._retrotui_tick_failure_count, 1)
        self.assertFalse(getattr(window, "_retrotui_tick_disabled", False))

    def test_repeated_window_draw_failure_hides_only_that_window(self):
        window = types.SimpleNamespace(
            visible=True,
            draw=mock.Mock(side_effect=RuntimeError("broken draw")),
        )
        app = types.SimpleNamespace(event_loop_failure_limit=3)
        stdscr = types.SimpleNamespace()

        for _ in range(4):
            self.event_loop._draw_window_component(app, window, stdscr, (25, 80))

        self.assertEqual(window.draw.call_count, 3)
        self.assertTrue(window._retrotui_draw_disabled)
        self.assertFalse(window.visible)
        self.assertIsInstance(window._retrotui_draw_first_error, RuntimeError)

    def test_repeated_renderer_failure_aborts_cleanly_after_limit(self):
        app = self._make_loop_app()
        first_error = RuntimeError("renderer unavailable")
        polls = {"count": 0}

        def _legacy_safety_stop():
            polls["count"] += 1
            if polls["count"] > app.event_loop_failure_limit:
                app.running = False

        app.poll_background_operation.side_effect = _legacy_safety_stop

        with mock.patch.object(
            self.event_loop,
            "draw_frame",
            side_effect=[first_error, RuntimeError("again"), RuntimeError("third")],
        ) as draw_mock:
            with mock.patch.object(self.event_loop.time, "sleep") as sleep_mock:
                self.event_loop.run_app_loop(app)

        self.assertEqual(draw_mock.call_count, 3)
        self.assertFalse(app.running)
        self.assertIs(app._event_loop_first_error, first_error)
        self.assertEqual(app._event_loop_first_error_phase, "render")
        self.assertIn("render", app._event_loop_abort_reason)
        sleep_mock.assert_not_called()
        app.cleanup.assert_called_once_with()

    def test_successful_iteration_clears_a_recovered_global_failure(self):
        app = self._make_loop_app()
        app.stdscr.get_wch.return_value = "x"

        def _dispatch_once(target, key):
            target.running = False
            return False

        with mock.patch.object(
            self.event_loop, "draw_frame", side_effect=[RuntimeError("transient"), None]
        ):
            with mock.patch.object(
                self.event_loop, "dispatch_input", side_effect=_dispatch_once
            ):
                self.event_loop.run_app_loop(app)

        self.assertIsNone(app._event_loop_first_error)
        self.assertIsNone(app._event_loop_first_error_phase)
        self.assertFalse(hasattr(app, "_event_loop_abort_reason"))
        app.cleanup.assert_called_once_with()

    def test_slotted_plugin_is_isolated_without_dynamic_attributes(self):
        class SlottedWindow:
            __slots__ = (
                "title",
                "visible",
                "tick_when_hidden",
                "wants_periodic_tick",
                "tick",
            )

            def __init__(self):
                self.title = "Slotted plugin"
                self.visible = True
                self.tick_when_hidden = True
                self.wants_periodic_tick = True
                self.tick = mock.Mock(side_effect=RuntimeError("slotted failure"))

        window = SlottedWindow()
        app = types.SimpleNamespace(windows=[window], event_loop_failure_limit=3)

        for _ in range(4):
            self.event_loop._tick_and_probe_windows(app)

        snapshot = self.event_loop._component_failure_snapshot(app, window, "tick")
        self.assertEqual(window.tick.call_count, 3)
        self.assertTrue(snapshot["disabled"])
        self.assertEqual(snapshot["failure_count"], 3)
        self.assertIsInstance(snapshot["first_error"], RuntimeError)
        self.assertFalse(hasattr(window, "_retrotui_tick_disabled"))

    def test_failure_registry_prunes_closed_windows(self):
        window = types.SimpleNamespace(
            visible=True,
            tick_when_hidden=False,
            wants_periodic_tick=True,
            tick=mock.Mock(side_effect=RuntimeError("once")),
        )
        app = types.SimpleNamespace(windows=[window], event_loop_failure_limit=3)
        self.event_loop._tick_and_probe_windows(app)
        self.assertTrue(app._component_failure_states)

        app.windows = []
        self.event_loop._prune_component_failure_states(app)

        self.assertEqual(app._component_failure_states, {})

if __name__ == "__main__":
    unittest.main()

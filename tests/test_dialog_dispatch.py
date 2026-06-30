import unittest
from types import SimpleNamespace
from retrotui.core.dialog_dispatch import DialogDispatcher
from retrotui.core.actions import ActionResult, ActionType, AppAction


class DummyApp:
    def __init__(self):
        self.called = {}
        self.dialog = None
        self.running = True

    def show_open_dialog(self, src):
        self.called['show_open_dialog'] = True

    def open_file_viewer(self, payload):
        self.called['open_file_viewer'] = payload

    def show_url_dialog(self, src, payload):
        self.called['show_url_dialog'] = payload

    def _normalize_action(self, payload):
        if payload == 'close':
            return AppAction.CLOSE_WINDOW
        return payload

    def close_window(self, src):
        self.called['close_window'] = True

    def execute_action(self, action):
        self.called.setdefault('execute_action', []).append(action)

    def _resolve_between_panes_destination(self, source_win, payload):
        return None

    def _run_file_operation_with_progress(self, *args, **kwargs):
        return None

    def show_kill_confirm_dialog(self, src, payload):
        self.called['show_kill_confirm_dialog'] = payload

    def apply_preferences(self, **kwargs):
        self.called['apply_preferences'] = kwargs

    def persist_config(self):
        self.called['persist_config'] = True

    def get_active_window(self):
        return 'active'


class DialogDispatchTests(unittest.TestCase):
    def test_dispatch_basic_branches(self):
        app = DummyApp()
        dd = DialogDispatcher(app)

        # Non-ActionResult ignored
        dd.dispatch_window_result('not an action', None)

        # REQUEST_OPEN_PATH -> calls show_open_dialog when source_win provided
        res = ActionResult(ActionType.REQUEST_OPEN_PATH)
        dd.dispatch_window_result(res, SimpleNamespace())
        self.assertTrue(app.called.get('show_open_dialog'))

        # OPEN_FILE -> calls open_file_viewer
        res2 = ActionResult(ActionType.OPEN_FILE, payload='/tmp/file')
        dd.dispatch_window_result(res2, None)
        self.assertEqual(app.called.get('open_file_viewer'), '/tmp/file')

        # REQUEST_URL -> calls show_url_dialog
        res3 = ActionResult(ActionType.REQUEST_URL, payload='http://x')
        dd.dispatch_window_result(res3, SimpleNamespace())
        self.assertEqual(app.called.get('show_url_dialog'), 'http://x')

        # EXECUTE -> normalized to CLOSE_WINDOW and closes when source_win
        res4 = ActionResult(ActionType.EXECUTE, payload='close')
        dd.dispatch_window_result(res4, SimpleNamespace())
        self.assertTrue(app.called.get('close_window'))

        # REQUEST_COPY_BETWEEN_PANES with no source_win sets dialog
        res5 = ActionResult(ActionType.REQUEST_COPY_BETWEEN_PANES, payload={'a': 'b'})
        dd.dispatch_window_result(res5, None)
        self.assertIsNotNone(app.dialog)

        # SAVE_ERROR sets dialog
        app.dialog = None
        res6 = ActionResult(ActionType.SAVE_ERROR, payload='boom')
        dd.dispatch_window_result(res6, None)
        self.assertIsNotNone(app.dialog)

        # UPDATE_CONFIG should call apply_preferences and persist_config
        app.called.pop('apply_preferences', None)
        app.called.pop('persist_config', None)
        res7 = ActionResult(ActionType.UPDATE_CONFIG, payload={'show_hidden': True})
        dd.dispatch_window_result(res7, None)
        self.assertIsNotNone(app.called.get('apply_preferences'))
        self.assertTrue(app.called.get('persist_config'))

    def test_resolve_dialog_result_exit(self):
        app = DummyApp()
        dd = DialogDispatcher(app)

        # Fake dialog with Exit title and Yes button
        dialog = SimpleNamespace()
        dialog.title = 'Exit RetroTUI'
        dialog.buttons = ['Yes']
        dialog.callback = None
        app.dialog = dialog

        dd.resolve_dialog_result(0)
        self.assertFalse(app.running)

    def test_dispatch_save_confirm_forwards_payload_on_discard(self):
        """REQUEST_SAVE_CONFIRM must pass the payload's on_discard callback
        through to _show_save_confirm_dialog so the Discard button actually
        runs the discard handler. Regression test for B3 (HIGH)."""
        app = DummyApp()
        captured = {}

        def fake_show(win, payload=None):
            captured['win'] = win
            captured['payload'] = payload
            app.dialog = SimpleNamespace(
                title='Discard unsaved changes?',
                buttons=['Discard', 'Cancel'],
                callback=None,
            )
            # Mirror what the real _show_save_confirm_dialog does: stash the
            # discard callback on the app so resolve_dialog_result can find it.
            on_discard = None
            if isinstance(payload, dict):
                cand = payload.get('on_discard')
                if callable(cand):
                    on_discard = cand
            if on_discard is None:
                fb = getattr(win, '_do_open_path_force', None)
                if callable(fb):
                    on_discard = fb

            def _wrapper():
                if on_discard is not None:
                    on_discard()

            app._pending_discard_callback = _wrapper

        app._show_save_confirm_dialog = fake_show

        discard_called = []

        def on_discard():
            discard_called.append(True)

        notepad = SimpleNamespace()
        dd = DialogDispatcher(app)
        result = ActionResult(
            ActionType.REQUEST_SAVE_CONFIRM,
            payload={'on_discard': on_discard},
        )
        dd.dispatch_window_result(result, notepad)
        self.assertIs(captured.get('win'), notepad)
        self.assertIs(captured.get('payload'), result.payload)

        # Now resolve Discard: the payload's on_discard should fire.
        dd.resolve_dialog_result(0)
        self.assertEqual(discard_called, [True])

    def test_dispatch_save_confirm_without_payload_is_noop(self):
        """If the payload is missing/malformed, Discard must NOT crash; it
        must silently no-op (matching the previous safe behaviour)."""
        app = DummyApp()

        def fake_show(win, payload=None):
            app.dialog = SimpleNamespace(
                title='Discard unsaved changes?',
                buttons=['Discard', 'Cancel'],
                callback=None,
            )
            # No on_discard in payload, no fallback on win → wrapper no-ops.
            app._pending_discard_callback = lambda: None

        app._show_save_confirm_dialog = fake_show
        dd = DialogDispatcher(app)
        notepad = SimpleNamespace()

        # No payload at all.
        dd.dispatch_window_result(
            ActionResult(ActionType.REQUEST_SAVE_CONFIRM), notepad,
        )
        dd.resolve_dialog_result(0)  # must not raise

        # Payload without on_discard key.
        app.dialog = None
        dd.dispatch_window_result(
            ActionResult(ActionType.REQUEST_SAVE_CONFIRM, payload={'foo': 1}),
            notepad,
        )
        dd.resolve_dialog_result(0)  # must not raise


if __name__ == "__main__":
    unittest.main()


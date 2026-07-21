import unittest
from types import SimpleNamespace

from retrotui.core.actions import ActionResult, ActionType, AppAction
from retrotui.core.dialog_dispatch import DialogDispatcher
from retrotui.core.dialog_workflow import DialogWorkflowId, bind_dialog


class DummyApp:
    def __init__(self):
        self.called = {}
        self.dialog = None
        self.running = True

    def show_open_dialog(self, src):
        self.called['show_open_dialog'] = src

    def open_file_viewer(self, payload):
        self.called['open_file_viewer'] = payload

    def show_url_dialog(self, src, payload):
        self.called['show_url_dialog'] = payload

    def _normalize_action(self, payload):
        if payload == 'close':
            return AppAction.CLOSE_WINDOW
        return payload

    def close_window(self, src):
        self.called['close_window'] = src

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
        return self.called.get('active')

    def _dispatch_window_result(self, result, source):
        self.called['dispatched'] = (result, source)


class DialogDispatchTests(unittest.TestCase):
    def test_dispatch_basic_branches(self):
        app = DummyApp()
        dispatcher = DialogDispatcher(app)
        source = SimpleNamespace()

        dispatcher.dispatch_window_result('not an action', None)
        dispatcher.dispatch_window_result(ActionResult(ActionType.REQUEST_OPEN_PATH), source)
        self.assertIs(app.called.get('show_open_dialog'), source)

        dispatcher.dispatch_window_result(ActionResult(ActionType.OPEN_FILE, '/tmp/file'), None)
        self.assertEqual(app.called.get('open_file_viewer'), '/tmp/file')

        dispatcher.dispatch_window_result(ActionResult(ActionType.REQUEST_URL, 'http://x'), source)
        self.assertEqual(app.called.get('show_url_dialog'), 'http://x')

        dispatcher.dispatch_window_result(ActionResult(ActionType.EXECUTE, 'close'), source)
        self.assertIs(app.called.get('close_window'), source)

        dispatcher.dispatch_window_result(
            ActionResult(ActionType.REQUEST_COPY_BETWEEN_PANES, {'a': 'b'}),
            None,
        )
        self.assertIsNotNone(app.dialog)

        app.dialog = None
        dispatcher.dispatch_window_result(ActionResult(ActionType.SAVE_ERROR, 'boom'), None)
        self.assertIsNotNone(app.dialog)

        dispatcher.dispatch_window_result(
            ActionResult(ActionType.UPDATE_CONFIG, {'show_hidden': True}),
            None,
        )
        self.assertIsNotNone(app.called.get('apply_preferences'))
        self.assertTrue(app.called.get('persist_config'))

    def test_exit_workflow_does_not_depend_on_visible_copy(self):
        app = DummyApp()
        app.dialog = bind_dialog(
            SimpleNamespace(title='Salir', buttons=['Continuar', 'Volver']),
            workflow_id=DialogWorkflowId.EXIT,
            on_accept=lambda: setattr(app, 'running', False),
        )

        DialogDispatcher(app).resolve_dialog_result(0)

        self.assertFalse(app.running)
        self.assertIsNone(app.dialog)

    def test_callback_result_is_delivered_to_captured_source(self):
        app = DummyApp()
        source = SimpleNamespace(id=7)
        active = SimpleNamespace(id=8)
        app.windows = [source, active]
        app.called['active'] = active
        result = ActionResult(ActionType.REFRESH)
        app.dialog = bind_dialog(
            SimpleNamespace(buttons=['OK'], value='new value'),
            workflow_id=DialogWorkflowId.CALLBACK,
            source_window=source,
            on_accept=lambda value: result,
        )

        DialogDispatcher(app).resolve_dialog_result(0)

        self.assertEqual(app.called.get('dispatched'), (result, source))

    def test_closed_source_cancels_callback_instead_of_using_active_window(self):
        app = DummyApp()
        source = SimpleNamespace(id=7)
        app.windows = []
        app.called['active'] = SimpleNamespace(id=8)
        calls = []
        app.dialog = bind_dialog(
            SimpleNamespace(buttons=['OK']),
            workflow_id=DialogWorkflowId.CALLBACK,
            source_window=source,
            on_accept=lambda: calls.append(True),
        )

        DialogDispatcher(app).resolve_dialog_result(0)

        self.assertEqual(calls, [])
        self.assertNotIn('dispatched', app.called)
        self.assertIsNone(app.dialog)

    def test_save_confirm_uses_callbacks_not_visible_copy(self):
        app = DummyApp()
        source = SimpleNamespace(id=3)
        app.windows = [source]
        calls = []
        dispatcher = DialogDispatcher(app)

        app.dialog = bind_dialog(
            SimpleNamespace(title='Cambios pendientes', buttons=['Descartar', 'Volver']),
            workflow_id=DialogWorkflowId.SAVE_CONFIRM,
            source_window=source,
            on_accept=lambda: calls.append('accept'),
            on_cancel=lambda: calls.append('cancel'),
        )
        dispatcher.resolve_dialog_result(0)

        app.dialog = bind_dialog(
            SimpleNamespace(title='Otro texto', buttons=['No', 'Sí']),
            workflow_id=DialogWorkflowId.SAVE_CONFIRM,
            source_window=source,
            on_accept=lambda: calls.append('accept-2'),
            on_cancel=lambda: calls.append('cancel'),
        )
        dispatcher.resolve_dialog_result(1)

        self.assertEqual(calls, ['accept', 'cancel'])

    def test_legacy_callback_remains_supported(self):
        app = DummyApp()
        calls = []
        app.dialog = SimpleNamespace(
            buttons=['OK'],
            value='abc',
            callback=lambda value: calls.append(value),
        )

        DialogDispatcher(app).resolve_dialog_result(0)

        self.assertEqual(calls, ['abc'])

    def test_dispatch_save_confirm_forwards_payload(self):
        app = DummyApp()
        captured = {}

        def fake_show(win, payload=None):
            captured['win'] = win
            captured['payload'] = payload

        app._show_save_confirm_dialog = fake_show
        source = SimpleNamespace()
        payload = {'on_discard': lambda: None}

        DialogDispatcher(app).dispatch_window_result(
            ActionResult(ActionType.REQUEST_SAVE_CONFIRM, payload),
            source,
        )

        self.assertIs(captured.get('win'), source)
        self.assertIs(captured.get('payload'), payload)


if __name__ == '__main__':
    unittest.main()

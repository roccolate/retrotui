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


def test_dispatch_basic_branches():
    app = DummyApp()
    dd = DialogDispatcher(app)

    # Non-ActionResult ignored
    dd.dispatch_window_result('not an action', None)

    # REQUEST_OPEN_PATH -> calls show_open_dialog when source_win provided
    res = ActionResult(ActionType.REQUEST_OPEN_PATH)
    dd.dispatch_window_result(res, SimpleNamespace())
    assert app.called.get('show_open_dialog')

    # OPEN_FILE -> calls open_file_viewer
    res2 = ActionResult(ActionType.OPEN_FILE, payload='/tmp/file')
    dd.dispatch_window_result(res2, None)
    assert app.called.get('open_file_viewer') == '/tmp/file'

    # REQUEST_URL -> calls show_url_dialog
    res3 = ActionResult(ActionType.REQUEST_URL, payload='http://x')
    dd.dispatch_window_result(res3, SimpleNamespace())
    assert app.called.get('show_url_dialog') == 'http://x'

    # EXECUTE -> normalized to CLOSE_WINDOW and closes when source_win
    res4 = ActionResult(ActionType.EXECUTE, payload='close')
    dd.dispatch_window_result(res4, SimpleNamespace())
    assert app.called.get('close_window')

    # REQUEST_COPY_BETWEEN_PANES with no source_win sets dialog
    res5 = ActionResult(ActionType.REQUEST_COPY_BETWEEN_PANES, payload={'a': 'b'})
    dd.dispatch_window_result(res5, None)
    assert app.dialog is not None

    # SAVE_ERROR sets dialog
    app.dialog = None
    res6 = ActionResult(ActionType.SAVE_ERROR, payload='boom')
    dd.dispatch_window_result(res6, None)
    assert app.dialog is not None

    # UPDATE_CONFIG should call apply_preferences and persist_config
    app.called.pop('apply_preferences', None)
    app.called.pop('persist_config', None)
    res7 = ActionResult(ActionType.UPDATE_CONFIG, payload={'show_hidden': True})
    dd.dispatch_window_result(res7, None)
    assert app.called.get('apply_preferences') is not None
    assert app.called.get('persist_config')


def test_resolve_dialog_result_exit():
    app = DummyApp()
    dd = DialogDispatcher(app)

    # Fake dialog with Exit title and Yes button
    dialog = SimpleNamespace()
    dialog.title = 'Exit RetroTUI'
    dialog.buttons = ['Yes']
    dialog.callback = None
    app.dialog = dialog

    dd.resolve_dialog_result(0)
    assert app.running is False

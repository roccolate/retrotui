import importlib


def test_retroapp_draw_delegates(monkeypatch):
    base = importlib.import_module('retrotui.plugins.base')

    called = {'ok': False}

    class DummyStdScr:
        def getmaxyx(self):
            return (24, 80)

        def addstr(self, *args, **kwargs):
            return None

        def addch(self, *args, **kwargs):
            return None

        def attron(self, *a, **k):
            return None

        def attroff(self, *a, **k):
            return None

    class TestApp(base.RetroApp):
        def draw_content(self, stdscr, x, y, w, h):
            called['ok'] = True

    app = TestApp('T', 0, 0, 20, 10)
    stdscr = DummyStdScr()
    app.draw(stdscr)
    assert called['ok']

import sys
import types
from pathlib import Path

fake = types.ModuleType("curses")
fake.A_BOLD = 1
fake.A_REVERSE = 2
fake.A_DIM = 4
fake.KEY_UP = 259
fake.KEY_DOWN = 258
fake.COLOR_WHITE = 7
fake.COLORS = 16
fake.error = Exception
fake.color_pair = lambda _: 0
fake.can_change_color = lambda: False
fake.start_color = lambda: None
fake.use_default_colors = lambda: None
fake.init_color = lambda *_: None
fake.init_pair = lambda *_: None
sys.modules['curses'] = fake

from retrotui.plugins import loader


def test_todo_plugin_basic():
    repo_root = Path(__file__).resolve().parents[1]
    examples = repo_root / 'examples' / 'plugins'
    loader.PLUGIN_DIR = str(examples)
    manifests = loader.discover_plugins()
    todo_manifest = next(m for m in manifests if m.get('plugin', {}).get('id') == 'todo-list')
    app_cls = loader.load_plugin(todo_manifest)
    assert app_cls is not None
    inst = app_cls('Todo', 1, 1, 40, 10)
    # initial todos list present
    assert hasattr(inst, 'todos')
    inst.handle_key(ord('a'))
    assert len(inst.todos) >= 1

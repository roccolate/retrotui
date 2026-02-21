import sys
import os
import types
from pathlib import Path

# Minimal fake curses for the tests
fake = types.ModuleType("curses")
fake.A_BOLD = 1
fake.A_REVERSE = 2
fake.A_DIM = 4
fake.KEY_UP = 259
fake.KEY_DOWN = 258
fake.KEY_LEFT = 260
fake.KEY_RIGHT = 261
fake.KEY_F9 = 273
fake.COLOR_RED = 1
fake.COLORS = 16
fake.error = Exception
fake.color_pair = lambda v: int(v) * 10
fake.init_pair = lambda *_args, **_kwargs: None
fake.start_color = lambda: None
fake.use_default_colors = lambda: None
fake.init_color = lambda *_args, **_kwargs: None
fake.can_change_color = lambda: False
sys.modules['curses'] = fake

from retrotui.plugins import loader


def test_discover_and_load_example_plugin():
    repo_root = Path(__file__).resolve().parents[1]
    examples = repo_root / 'examples' / 'plugins'
    # Point loader to examples folder for test discovery
    loader.PLUGIN_DIR = str(examples)

    manifests = loader.discover_plugins()
    assert isinstance(manifests, list)
    # We expect todo-list present
    ids = [m.get('plugin', {}).get('id') for m in manifests]
    assert 'todo-list' in ids

    todo_manifest = next(m for m in manifests if m.get('plugin', {}).get('id') == 'todo-list')
    app_cls = loader.load_plugin(todo_manifest)
    assert app_cls is not None
    assert hasattr(app_cls, 'PLUGIN_ID')

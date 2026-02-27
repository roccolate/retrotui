import os
import tempfile
import textwrap

import importlib


def test_discover_and_load_plugin(monkeypatch):
    loader = importlib.import_module('retrotui.plugins.loader')

    with tempfile.TemporaryDirectory() as td:
        # Create plugin folder
        pdir = os.path.join(td, 'p1')
        os.mkdir(pdir)
        toml_path = os.path.join(pdir, 'plugin.toml')
        with open(toml_path, 'w', encoding='utf-8') as f:
            f.write('[plugin]\n')
            f.write('id = "testplugin"\n')

        init_path = os.path.join(pdir, '__init__.py')
        with open(init_path, 'w', encoding='utf-8') as f:
            f.write('class Plugin:\n')
            f.write('    pass\n')

        # Point loader at our temp dir; suppress bundled plugins dir so count is predictable
        monkeypatch.setattr(loader, 'PLUGIN_DIR', td)
        monkeypatch.setattr(loader, '_bundled_plugin_dir', lambda: os.path.join(td, '_nonexistent_bundled'))

        manifests = loader.discover_plugins()
        assert len(manifests) == 1
        manifest = manifests[0]
        assert manifest.get('plugin', {}).get('id') == 'testplugin'

        app_cls = loader.load_plugin(manifest)
        assert app_cls is not None
        assert getattr(app_cls, 'PLUGIN_ID', 'testplugin') == 'testplugin'


def test_load_plugin_missing_init(monkeypatch):
    loader = importlib.import_module('retrotui.plugins.loader')
    with tempfile.TemporaryDirectory() as td:
        pdir = os.path.join(td, 'p2')
        os.mkdir(pdir)
        toml_path = os.path.join(pdir, 'plugin.toml')
        with open(toml_path, 'w', encoding='utf-8') as f:
            f.write('[plugin]\n')
            f.write('id = "noinit"\n')

        monkeypatch.setattr(loader, 'PLUGIN_DIR', td)
        monkeypatch.setattr(loader, '_bundled_plugin_dir', lambda: os.path.join(td, '_nonexistent_bundled'))
        manifests = loader.discover_plugins()
        assert len(manifests) == 1
        app_cls = loader.load_plugin(manifests[0])
        assert app_cls is None


def test_discover_fallback_toml(monkeypatch):
    loader = importlib.import_module('retrotui.plugins.loader')
    # Force fallback parser path
    monkeypatch.setattr(loader, 'tomllib', None)
    with tempfile.TemporaryDirectory() as td:
        pdir = os.path.join(td, 'p3')
        os.mkdir(pdir)
        toml_path = os.path.join(pdir, 'plugin.toml')
        # Use very simple TOML that fallback can parse
        with open(toml_path, 'w', encoding='utf-8') as f:
            f.write('[plugin]\n')
            f.write('id = "fb"\n')

        init_path = os.path.join(pdir, '__init__.py')
        with open(init_path, 'w', encoding='utf-8') as f:
            f.write('class App:\n')
            f.write('    pass\n')

        monkeypatch.setattr(loader, 'PLUGIN_DIR', td)
        monkeypatch.setattr(loader, '_bundled_plugin_dir', lambda: os.path.join(td, '_nonexistent_bundled'))
        manifests = loader.discover_plugins()
        assert len(manifests) == 1
        app_cls = loader.load_plugin(manifests[0])
        assert app_cls is not None
        # App class should have PLUGIN_ID set when possible
        assert getattr(app_cls, 'PLUGIN_ID', 'fb') == 'fb'

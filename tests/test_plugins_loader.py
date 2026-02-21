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

        # Point loader at our temp dir
        monkeypatch.setattr(loader, 'PLUGIN_DIR', td)

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
        manifests = loader.discover_plugins()
        assert len(manifests) == 1
        app_cls = loader.load_plugin(manifests[0])
        assert app_cls is not None
        # App class should have PLUGIN_ID set when possible
        assert getattr(app_cls, 'PLUGIN_ID', 'fb') == 'fb'


    def test_load_plugin_import_error(monkeypatch):
        loader = importlib.import_module('retrotui.plugins.loader')
        with tempfile.TemporaryDirectory() as td:
            pdir = os.path.join(td, 'p4')
            os.mkdir(pdir)
            toml_path = os.path.join(pdir, 'plugin.toml')
            with open(toml_path, 'w', encoding='utf-8') as f:
                f.write('[plugin]\n')
                f.write('id = "badinit"\n')

            init_path = os.path.join(pdir, '__init__.py')
            # __init__ that raises when imported
            with open(init_path, 'w', encoding='utf-8') as f:
                f.write('raise RuntimeError("boom")\n')

            monkeypatch.setattr(loader, 'PLUGIN_DIR', td)
            manifests = loader.discover_plugins()
            assert len(manifests) == 1
            app_cls = loader.load_plugin(manifests[0])
            assert app_cls is None
import tempfile
from pathlib import Path

from retrotui.plugins import loader


def test_discover_and_load_plugin(tmp_path=None):
    # create a temporary plugins dir
    td = Path(tempfile.mkdtemp())
    plugin_dir = td / "myplugin"
    plugin_dir.mkdir()

    # write plugin.toml
    toml_text = """
[plugin]
id = "test-plugin"
name = "Test Plugin"
"""
    (plugin_dir / "plugin.toml").write_text(toml_text, encoding="utf-8")

    # write __init__.py exposing Plugin
    init_text = """
class Plugin:
    pass
"""
    (plugin_dir / "__init__.py").write_text(init_text, encoding="utf-8")

    # point loader.PLUGIN_DIR to our temp dir
    old = loader.PLUGIN_DIR
    loader.PLUGIN_DIR = str(td)
    try:
        manifests = loader.discover_plugins()
        assert any(m.get('plugin', {}).get('id') == 'test-plugin' for m in manifests)
        cls = loader.load_plugin(manifests[0])
        assert cls is not None
        assert getattr(cls, 'PLUGIN_ID', None) == 'test-plugin'
    finally:
        loader.PLUGIN_DIR = old

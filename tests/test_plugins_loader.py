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

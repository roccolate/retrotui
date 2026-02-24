import importlib
import types
import unittest
from pathlib import Path
from unittest import mock

from _support import make_repo_tmpdir


class PluginLoaderUnitTests(unittest.TestCase):
    def setUp(self):
        self.loader = importlib.import_module("retrotui.plugins.loader")
        self._orig_plugin_dir = self.loader.PLUGIN_DIR
        self._orig_default_plugin_dir = self.loader._DEFAULT_PLUGIN_DIR

    def tearDown(self):
        self.loader.PLUGIN_DIR = self._orig_plugin_dir
        self.loader._DEFAULT_PLUGIN_DIR = self._orig_default_plugin_dir

    def _create_plugin(self, root: Path, plugin_id: str) -> Path:
        plugin_dir = root / plugin_id
        plugin_dir.mkdir()
        (plugin_dir / "plugin.toml").write_text(
            "[plugin]\n"
            f'id = "{plugin_id}"\n',
            encoding="utf-8",
        )
        (plugin_dir / "__init__.py").write_text(
            "class Plugin:\n"
            "    pass\n",
            encoding="utf-8",
        )
        return plugin_dir

    def test_load_plugin_returns_none_when_spec_is_missing(self):
        tmpdir = make_repo_tmpdir(prefix="_tmp_plugin_loader_")
        self.addCleanup(tmpdir.cleanup)
        root = Path(tmpdir.name)
        self._create_plugin(root, "demo")
        self.loader.PLUGIN_DIR = str(root)
        manifests = self.loader.discover_plugins()
        self.assertEqual(len(manifests), 1)

        with mock.patch.object(self.loader.importlib.util, "spec_from_file_location", return_value=None):
            app_class = self.loader.load_plugin(manifests[0])

        self.assertIsNone(app_class)

    def test_discover_plugins_skips_invalid_toml_payloads(self):
        tmpdir = make_repo_tmpdir(prefix="_tmp_plugin_loader_")
        self.addCleanup(tmpdir.cleanup)
        root = Path(tmpdir.name)
        plugin_dir = root / "broken"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.toml").write_text("[plugin]\nid = 'broken'\n", encoding="utf-8")
        self.loader.PLUGIN_DIR = str(root)

        fake_tomllib = types.SimpleNamespace(load=mock.Mock(side_effect=ValueError("bad toml")))
        with mock.patch.object(self.loader, "tomllib", fake_tomllib):
            manifests = self.loader.discover_plugins()

        self.assertEqual(manifests, [])

    def test_discover_plugins_uses_repo_examples_fallback_when_default_missing(self):
        tmpdir = make_repo_tmpdir(prefix="_tmp_plugin_loader_")
        self.addCleanup(tmpdir.cleanup)
        root = Path(tmpdir.name)
        examples = root / "examples"
        examples.mkdir()
        self._create_plugin(examples, "bundled")

        missing_default = root / "missing-default"
        self.loader._DEFAULT_PLUGIN_DIR = str(missing_default)
        self.loader.PLUGIN_DIR = str(missing_default)

        with (
            mock.patch.object(self.loader, "_repo_examples_plugin_dir", return_value=str(examples)),
            mock.patch.object(self.loader, "_cwd_examples_plugin_dir", return_value=str(root / "nope")),
        ):
            manifests = self.loader.discover_plugins()

        self.assertEqual(len(manifests), 1)
        self.assertEqual(manifests[0].get("plugin", {}).get("id"), "bundled")

    def test_discover_plugins_uses_repo_examples_when_default_exists_but_empty(self):
        tmpdir = make_repo_tmpdir(prefix="_tmp_plugin_loader_")
        self.addCleanup(tmpdir.cleanup)
        root = Path(tmpdir.name)
        examples = root / "examples"
        examples.mkdir()
        self._create_plugin(examples, "bundled")

        empty_default = root / "empty-default"
        empty_default.mkdir()
        self.loader._DEFAULT_PLUGIN_DIR = str(empty_default)
        self.loader.PLUGIN_DIR = str(empty_default)

        with (
            mock.patch.object(self.loader, "_repo_examples_plugin_dir", return_value=str(examples)),
            mock.patch.object(self.loader, "_cwd_examples_plugin_dir", return_value=str(root / "nope")),
        ):
            manifests = self.loader.discover_plugins()

        self.assertEqual(len(manifests), 1)
        self.assertEqual(manifests[0].get("plugin", {}).get("id"), "bundled")

    def test_discover_plugins_uses_cwd_examples_fallback_when_repo_path_missing(self):
        tmpdir = make_repo_tmpdir(prefix="_tmp_plugin_loader_")
        self.addCleanup(tmpdir.cleanup)
        root = Path(tmpdir.name)
        examples = root / "examples" / "plugins"
        examples.mkdir(parents=True)
        self._create_plugin(examples, "cwd-bundled")

        missing_default = root / "missing-default"
        self.loader._DEFAULT_PLUGIN_DIR = str(missing_default)
        self.loader.PLUGIN_DIR = str(missing_default)

        with (
            mock.patch.object(self.loader, "_repo_examples_plugin_dir", return_value=str(root / "nope")),
            mock.patch.object(self.loader, "_cwd_examples_plugin_dir", return_value=str(examples)),
        ):
            manifests = self.loader.discover_plugins()

        self.assertEqual(len(manifests), 1)
        self.assertEqual(manifests[0].get("plugin", {}).get("id"), "cwd-bundled")


if __name__ == "__main__":
    unittest.main()

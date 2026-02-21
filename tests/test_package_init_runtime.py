import importlib
import sys
import unittest
from pathlib import Path


def _purge_retrotui_modules():
    for mod_name in list(sys.modules):
        if mod_name == "retrotui" or mod_name.startswith("retrotui."):
            sys.modules.pop(mod_name, None)


def _ensure_project_root_on_path():
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)
    return Path(root)


class PackageInitRuntimeTests(unittest.TestCase):
    def test_runtime_import_exposes_version(self):
        _purge_retrotui_modules()
        project_root = _ensure_project_root_on_path()
        package = importlib.import_module("retrotui")
        self.assertEqual(package.__version__, "0.9.1")
        self.assertEqual(Path(package.__file__).resolve(), project_root / "retrotui" / "__init__.py")

    def test_direct_import_executes_package_init(self):
        _purge_retrotui_modules()
        project_root = _ensure_project_root_on_path()
        import retrotui  # noqa: PLC0415

        self.assertEqual(retrotui.__version__, "0.9.1")
        self.assertEqual(Path(retrotui.__file__).resolve(), project_root / "retrotui" / "__init__.py")


if __name__ == "__main__":
    unittest.main()

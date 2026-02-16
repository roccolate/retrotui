import sys
import unittest
from pathlib import Path


class PackageInitTraceTests(unittest.TestCase):
    def test_direct_import_traces_init_module(self):
        root = str(Path(__file__).resolve().parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)

        for mod_name in list(sys.modules):
            if mod_name == "retrotui" or mod_name.startswith("retrotui."):
                sys.modules.pop(mod_name, None)

        import retrotui  # noqa: PLC0415

        self.assertEqual(retrotui.__version__, "0.6.0")
        self.assertEqual(Path(retrotui.__file__).resolve(), Path(root) / "retrotui" / "__init__.py")


if __name__ == "__main__":
    unittest.main()

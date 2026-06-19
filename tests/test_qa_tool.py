import importlib
import io
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _support import make_repo_tmpdir


class QAToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qa = importlib.import_module("tools.qa")

    def _write_version_files(self, root: Path, project="1.2.3", package="1.2.3", app="1.2.3", setup="1.2.3"):
        (root / "retrotui" / "core").mkdir(parents=True)
        (root / "pyproject.toml").write_text(
            "[project]\n"
            f'version = "{project}"\n',
            encoding="utf-8",
        )
        (root / "retrotui" / "__init__.py").write_text(
            f"__version__ = '{package}'\n",
            encoding="utf-8",
        )
        (root / "retrotui" / "core" / "app.py").write_text(
            f"APP_VERSION = '{app}'\n",
            encoding="utf-8",
        )
        (root / "setup.sh").write_text(
            "#!/bin/bash\n"
            f'echo "  RetroTUI v{setup} - Setup"\n',
            encoding="utf-8",
        )

    def test_check_version_sync_includes_setup_script(self):
        tmpdir = make_repo_tmpdir(prefix="_tmp_qa_tool_")
        self.addCleanup(tmpdir.cleanup)
        root = Path(tmpdir.name)
        self._write_version_files(root, setup="1.2.2")

        old_cwd = os.getcwd()
        try:
            os.chdir(root)
            with redirect_stdout(io.StringIO()) as output:
                rc = self.qa.check_version_sync()
        finally:
            os.chdir(old_cwd)

        self.assertEqual(rc, 1)
        self.assertIn("setup.sh", output.getvalue())


if __name__ == "__main__":
    unittest.main()

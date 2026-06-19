import importlib.util
import io
import unittest
from pathlib import Path
from uuid import uuid4
from contextlib import redirect_stdout


def _load_release_tag_module():
    module_path = Path("tools") / "check_release_tag.py"
    spec = importlib.util.spec_from_file_location("check_release_tag", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load tools/check_release_tag.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseTagToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = _load_release_tag_module()

    def _write_files(
        self,
        py_version: str,
        app_version: str,
        package_version: str | None = None,
        setup_version: str | None = None,
    ):
        token = uuid4().hex
        pyproject = Path("tests") / f"_tmp_release_pyproject_{token}.toml"
        app_file = Path("tests") / f"_tmp_release_app_{token}.py"
        package_file = Path("tests") / f"_tmp_release_package_{token}.py"
        setup_file = Path("tests") / f"_tmp_release_setup_{token}.sh"

        pyproject.write_text(
            "[project]\n"
            f'version = "{py_version}"\n',
            encoding="utf-8",
        )
        app_file.write_text(f"APP_VERSION = '{app_version}'\n", encoding="utf-8")
        package_file.write_text(
            f"__version__ = '{package_version or py_version}'\n",
            encoding="utf-8",
        )
        setup_file.write_text(
            f'echo "  RetroTUI v{setup_version or py_version} - Setup"\n',
            encoding="utf-8",
        )
        return pyproject, app_file, package_file, setup_file

    def _cleanup(self, *paths: Path):
        for path in paths:
            if path.exists():
                path.unlink()

    def test_validate_release_tag_ok_when_versions_match(self):
        paths = self._write_files("0.3.4", "0.3.4")
        try:
            with redirect_stdout(io.StringIO()):
                rc = self.tool.validate_release_tag("v0.3.4", *paths)
        finally:
            self._cleanup(*paths)
        self.assertEqual(rc, 0)

    def test_validate_release_tag_fails_without_v_prefix(self):
        paths = self._write_files("0.3.4", "0.3.4")
        try:
            with redirect_stdout(io.StringIO()):
                rc = self.tool.validate_release_tag("0.3.4", *paths)
        finally:
            self._cleanup(*paths)
        self.assertEqual(rc, 1)

    def test_validate_release_tag_fails_on_app_version_mismatch(self):
        paths = self._write_files("0.3.4", "0.3.3")
        try:
            with redirect_stdout(io.StringIO()):
                rc = self.tool.validate_release_tag("v0.3.4", *paths)
        finally:
            self._cleanup(*paths)
        self.assertEqual(rc, 1)

    def test_validate_release_tag_fails_on_package_version_mismatch(self):
        paths = self._write_files("0.3.4", "0.3.4", package_version="0.3.3")
        try:
            with redirect_stdout(io.StringIO()):
                rc = self.tool.validate_release_tag("v0.3.4", *paths)
        finally:
            self._cleanup(*paths)
        self.assertEqual(rc, 1)

    def test_validate_release_tag_fails_on_setup_version_mismatch(self):
        paths = self._write_files("0.3.4", "0.3.4", setup_version="0.3.3")
        try:
            with redirect_stdout(io.StringIO()):
                rc = self.tool.validate_release_tag("v0.3.4", *paths)
        finally:
            self._cleanup(*paths)
        self.assertEqual(rc, 1)

    def test_validate_release_tag_fails_without_traceback_when_file_missing(self):
        paths = self._write_files("0.3.4", "0.3.4")
        missing_pyproject = paths[0]
        missing_pyproject.unlink()
        try:
            with redirect_stdout(io.StringIO()):
                rc = self.tool.validate_release_tag("v0.3.4", *paths)
        finally:
            self._cleanup(*paths)
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()

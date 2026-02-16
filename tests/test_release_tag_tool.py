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

    def _write_files(self, py_version: str, app_version: str):
        token = uuid4().hex
        pyproject = Path("tests") / f"_tmp_release_pyproject_{token}.toml"
        app_file = Path("tests") / f"_tmp_release_app_{token}.py"

        pyproject.write_text(
            "[project]\n"
            f'version = "{py_version}"\n',
            encoding="utf-8",
        )
        app_file.write_text(f"APP_VERSION = '{app_version}'\n", encoding="utf-8")
        return pyproject, app_file

    def test_validate_release_tag_ok_when_versions_match(self):
        pyproject, app_file = self._write_files("0.3.4", "0.3.4")
        try:
            with redirect_stdout(io.StringIO()):
                rc = self.tool.validate_release_tag("v0.3.4", pyproject, app_file)
        finally:
            if pyproject.exists():
                pyproject.unlink()
            if app_file.exists():
                app_file.unlink()
        self.assertEqual(rc, 0)

    def test_validate_release_tag_fails_without_v_prefix(self):
        pyproject, app_file = self._write_files("0.3.4", "0.3.4")
        try:
            with redirect_stdout(io.StringIO()):
                rc = self.tool.validate_release_tag("0.3.4", pyproject, app_file)
        finally:
            if pyproject.exists():
                pyproject.unlink()
            if app_file.exists():
                app_file.unlink()
        self.assertEqual(rc, 1)

    def test_validate_release_tag_fails_on_app_version_mismatch(self):
        pyproject, app_file = self._write_files("0.3.4", "0.3.3")
        try:
            with redirect_stdout(io.StringIO()):
                rc = self.tool.validate_release_tag("v0.3.4", pyproject, app_file)
        finally:
            if pyproject.exists():
                pyproject.unlink()
            if app_file.exists():
                app_file.unlink()
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()

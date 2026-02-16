import importlib.util
import shutil
import sys
import unittest
from pathlib import Path


def _load_module():
    module_path = Path("tools") / "report_module_coverage.py"
    spec = importlib.util.spec_from_file_location("report_module_coverage", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load tools/report_module_coverage.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ModuleCoverageToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_collect_executable_lines_detects_statement_rows(self):
        source = (
            "x = 1\n"
            "def f():\n"
            "    if x:\n"
            "        return x\n"
            "    return 0\n"
        )
        lines = self.mod.collect_executable_lines(source)
        self.assertTrue({1, 2, 3, 4, 5}.issubset(lines))

    def test_collect_executable_lines_excludes_docstrings(self):
        source = (
            "\"\"\"module docs\"\"\"\n"
            "def f():\n"
            "    \"\"\"function docs\"\"\"\n"
            "    return 1\n"
        )
        lines = self.mod.collect_executable_lines(source)
        self.assertIn(2, lines)
        self.assertIn(4, lines)
        self.assertNotIn(1, lines)
        self.assertNotIn(3, lines)

    def test_coverage_percent_handles_zero_denominator(self):
        self.assertEqual(self.mod.coverage_percent(0, 0), 100.0)
        self.assertAlmostEqual(self.mod.coverage_percent(3, 4), 75.0)

    def test_sort_coverage_rows_orders_lowest_first(self):
        rows = [
            self.mod.ModuleCoverage("a.py", executed=8, executable=10),   # 80%
            self.mod.ModuleCoverage("b.py", executed=1, executable=10),   # 10%
            self.mod.ModuleCoverage("c.py", executed=5, executable=10),   # 50%
        ]
        ordered = self.mod.sort_coverage_rows(rows)
        self.assertEqual([r.module for r in ordered], ["b.py", "c.py", "a.py"])

    def test_build_coverage_rows_maps_counts_from_foreign_root_by_suffix(self):
        tmp_root = Path("tests") / "_tmp_module_cov_rows"
        package_root = tmp_root / "retrotui"
        if tmp_root.exists():
            shutil.rmtree(tmp_root, ignore_errors=True)
        package_root.mkdir(parents=True, exist_ok=True)
        module_path = package_root / "sample.py"
        module_path.write_text("x = 1\ny = 2\n", encoding="utf-8")
        try:
            foreign_path = Path("Z:/old_workspace/retrotui/sample.py")
            counts = {(str(foreign_path), 1): 1}
            rows = self.mod.build_coverage_rows(str(package_root), counts)
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

        sample_row = next(row for row in rows if row.module.endswith("retrotui/sample.py"))
        self.assertEqual(sample_row.executable, 2)
        self.assertEqual(sample_row.executed, 1)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Make coverage measurement deterministic without weakening normal test gates."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
report_path = ROOT / "tools/report_module_coverage.py"
text = report_path.read_text(encoding="utf-8")

old_suite = '''def build_unittest_suite(tests_dir: str) -> unittest.TestSuite:
    """Discover and return unittest suite for the provided directory."""
    project_root = str(Path.cwd().resolve())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    return unittest.defaultTestLoader.discover(start_dir=tests_dir)
'''
new_suite = '''DEFAULT_COVERAGE_EXCLUDED_TEST_MODULES = ("test_perf_cache_stress",)


def _iter_test_cases(suite: unittest.TestSuite):
    """Yield individual cases from a recursively nested unittest suite."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_test_cases(item)
        else:
            yield item


def filter_unittest_suite(
    suite: unittest.TestSuite,
    *,
    exclude_modules: Iterable[str] = (),
) -> unittest.TestSuite:
    """Return a suite excluding test modules unsuitable for instrumentation.

    Timing-sensitive tests remain mandatory in the normal unittest and pytest
    jobs. They are excluded only while stdlib ``trace`` instrumentation is
    active, because the tracer changes the performance characteristic being
    asserted and can create false regressions.
    """
    excluded = {str(name).strip() for name in exclude_modules if str(name).strip()}
    filtered = unittest.TestSuite()
    for test in _iter_test_cases(suite):
        module_name = getattr(test.__class__, "__module__", "")
        if any(
            module_name == name or module_name.endswith(f".{name}")
            for name in excluded
        ):
            continue
        filtered.addTest(test)
    return filtered


def build_unittest_suite(
    tests_dir: str,
    *,
    exclude_modules: Iterable[str] = (),
) -> unittest.TestSuite:
    """Discover tests and optionally exclude instrumentation-hostile modules."""
    project_root = str(Path.cwd().resolve())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    suite = unittest.defaultTestLoader.discover(start_dir=tests_dir)
    return filter_unittest_suite(suite, exclude_modules=exclude_modules)
'''
if new_suite not in text:
    if old_suite not in text:
        raise RuntimeError("coverage suite builder changed")
    text = text.replace(old_suite, new_suite, 1)

old_args = '''    parser.add_argument("--quiet-tests", action="store_true", help="Run tests with minimal verbosity")
    parser.add_argument(
        "--fail-under",
'''
new_args = '''    parser.add_argument("--quiet-tests", action="store_true", help="Run tests with minimal verbosity")
    parser.add_argument(
        "--exclude-test-module",
        action="append",
        default=None,
        help=(
            "Test module to exclude only from the traced coverage run. "
            "May be repeated; defaults to timing-sensitive stress tests."
        ),
    )
    parser.add_argument(
        "--fail-under",
'''
if new_args not in text:
    if old_args not in text:
        raise RuntimeError("coverage argument block changed")
    text = text.replace(old_args, new_args, 1)

old_build = '''    suite = build_unittest_suite(args.tests)
    runner = unittest.TextTestRunner(verbosity=0 if args.quiet_tests else 1)
'''
new_build = '''    excluded_modules = (
        DEFAULT_COVERAGE_EXCLUDED_TEST_MODULES
        if args.exclude_test_module is None
        else tuple(args.exclude_test_module)
    )
    suite = build_unittest_suite(
        args.tests,
        exclude_modules=excluded_modules,
    )
    if excluded_modules:
        print(
            "Coverage instrumentation exclusions: "
            + ", ".join(sorted(excluded_modules))
        )
    runner = unittest.TextTestRunner(verbosity=0 if args.quiet_tests else 1)
'''
if new_build not in text:
    if old_build not in text:
        raise RuntimeError("coverage main suite block changed")
    text = text.replace(old_build, new_build, 1)

report_path.write_text(text, encoding="utf-8")


test_path = ROOT / "tests/test_module_coverage_tool.py"
test_text = test_path.read_text(encoding="utf-8")
marker = '''    def test_build_coverage_rows_maps_counts_from_foreign_root_by_suffix(self):
'''
new_test = '''    def test_filter_suite_excludes_only_named_timing_module(self):
        class RegularCase(unittest.TestCase):
            def test_regular(self):
                pass

        class TimingCase(unittest.TestCase):
            def test_timing(self):
                pass

        RegularCase.__module__ = "test_regular"
        TimingCase.__module__ = "tests.test_perf_cache_stress"
        suite = unittest.TestSuite(
            [RegularCase("test_regular"), TimingCase("test_timing")]
        )

        filtered = self.mod.filter_unittest_suite(
            suite,
            exclude_modules=("test_perf_cache_stress",),
        )
        test_ids = [test.id() for test in self.mod._iter_test_cases(filtered)]

        self.assertEqual(len(test_ids), 1)
        self.assertTrue(test_ids[0].startswith("test_regular."))

'''
if new_test not in test_text:
    if marker not in test_text:
        raise RuntimeError("module coverage test insertion point changed")
    test_text = test_text.replace(marker, new_test + marker, 1)
test_path.write_text(test_text, encoding="utf-8")

#!/usr/bin/env python3
"""Report per-module coverage using Python stdlib trace.

Coverage is computed as:
- executable lines: AST nodes with line numbers
- executed lines: trace counts intersected with executable lines
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
import trace
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ModuleCoverage:
    module: str
    executed: int
    executable: int

    @property
    def percent(self) -> float:
        return coverage_percent(self.executed, self.executable)


def coverage_percent(executed: int, executable: int) -> float:
    """Return coverage percentage for executed/executable lines."""
    if executable <= 0:
        return 100.0
    return (executed / executable) * 100.0


def collect_executable_lines(source: str) -> set[int]:
    """Collect executable statement lines from Python source via AST.

    Notes:
    - Counts statement/excepthandler lines, not every AST node.
    - Excludes pure docstring expression lines.
    """
    tree = ast.parse(source)
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    def is_docstring_stmt(node: ast.AST) -> bool:
        if not isinstance(node, ast.Expr):
            return False
        value = getattr(node, "value", None)
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            return False
        parent = parents.get(node)
        if not isinstance(parent, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False
        body = getattr(parent, "body", [])
        return bool(body) and body[0] is node

    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            lineno = getattr(node, "lineno", None)
            if lineno is not None and not is_docstring_stmt(node):
                lines.add(int(lineno))
            continue
        if isinstance(node, ast.excepthandler):
            lineno = getattr(node, "lineno", None)
            if lineno is not None:
                lines.add(int(lineno))
            continue
        lineno = getattr(node, "lineno", None)
        if isinstance(node, ast.match_case) and lineno is not None:
            lines.add(int(lineno))
    return lines


def sort_coverage_rows(rows: Iterable[ModuleCoverage]) -> list[ModuleCoverage]:
    """Sort from lower coverage to higher coverage."""
    return sorted(rows, key=lambda row: (row.percent, -row.executable, row.module))


def normalize_path(path: str | Path) -> str:
    """Normalize paths for stable comparisons across platforms/casing."""
    try:
        resolved = Path(path).resolve()
    except OSError:
        resolved = Path(path)
    return os.path.normcase(os.path.normpath(str(resolved)))


def _package_suffix(path: str | Path, package_name: str) -> str | None:
    """Return lowercase suffix like 'retrotui/core/app.py' when present."""
    parts = [part for part in Path(path).parts if part]
    lowered = [part.lower() for part in parts]
    package_lower = package_name.lower()
    if package_lower not in lowered:
        return None
    idx = lowered.index(package_lower)
    return "/".join(lowered[idx:])


def run_unittest_suite(tests_dir: str, verbosity: int) -> bool:
    """Run unittest discovery and return success state."""
    project_root = str(Path.cwd().resolve())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    suite = unittest.defaultTestLoader.discover(start_dir=tests_dir)
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return result.wasSuccessful()


def run_unittest_suite_result(tests_dir: str, verbosity: int) -> unittest.TestResult:
    """Run unittest discovery and return the unittest result object."""
    project_root = str(Path.cwd().resolve())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    suite = unittest.defaultTestLoader.discover(start_dir=tests_dir)
    return unittest.TextTestRunner(verbosity=verbosity).run(suite)


def build_unittest_suite(tests_dir: str) -> unittest.TestSuite:
    """Discover and return unittest suite for the provided directory."""
    project_root = str(Path.cwd().resolve())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    return unittest.defaultTestLoader.discover(start_dir=tests_dir)


def build_coverage_rows(package_dir: str, counts: dict[tuple[str, int], int]) -> list[ModuleCoverage]:
    """Build per-module rows from trace counts."""
    package_root = Path(package_dir).resolve()
    package_parent = package_root.parent
    module_key_by_suffix: dict[str, str] = {}
    for file_path in package_root.rglob("*.py"):
        suffix = str(file_path.relative_to(package_parent)).replace("\\", "/").lower()
        module_key_by_suffix[suffix] = normalize_path(file_path)

    executed_by_file: dict[str, set[int]] = {}

    for (filename, lineno), count in counts.items():
        if count <= 0:
            continue
        try:
            file_path = Path(filename).resolve()
        except OSError:
            file_path = Path(filename)

        key = None
        if file_path == package_root or package_root in file_path.parents:
            key = normalize_path(file_path)
        else:
            suffix = _package_suffix(filename, package_root.name)
            if suffix is not None:
                key = module_key_by_suffix.get(suffix)

        if key is None:
            continue
        executed_by_file.setdefault(key, set()).add(int(lineno))

    rows: list[ModuleCoverage] = []
    for file_path in sorted(package_root.rglob("*.py")):
        source = file_path.read_text(encoding="utf-8")
        executable_lines = collect_executable_lines(source)
        executed_lines = executed_by_file.get(normalize_path(file_path), set())
        covered_lines = executed_lines & executable_lines
        try:
            rel_module = str(file_path.relative_to(Path.cwd())).replace("\\", "/")
        except ValueError:
            rel_module = str(file_path).replace("\\", "/")
        rows.append(
            ModuleCoverage(
                module=rel_module,
                executed=len(covered_lines),
                executable=len(executable_lines),
            )
        )
    return rows


def print_coverage_table(rows: list[ModuleCoverage], top: int | None = None) -> None:
    """Print a compact table with per-module coverage."""
    ordered = sort_coverage_rows(rows)
    if top is not None and top > 0:
        ordered = ordered[:top]

    print("Module Coverage Summary (trace + AST)")
    print(f"{'Module':<48} {'Exec/Total':>12} {'Coverage':>9}")
    print("-" * 72)
    for row in ordered:
        ratio = f"{row.executed}/{row.executable}"
        print(f"{row.module:<48} {ratio:>12} {row.percent:>8.1f}%")

    total_exec = sum(row.executed for row in rows)
    total_executable = sum(row.executable for row in rows)
    total_percent = coverage_percent(total_exec, total_executable)
    print("-" * 72)
    print(f"{'TOTAL':<48} {f'{total_exec}/{total_executable}':>12} {total_percent:>8.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description="Report per-module coverage with stdlib trace.")
    parser.add_argument("--package", default="retrotui", help="Package directory to analyze (default: retrotui)")
    parser.add_argument("--tests", default="tests", help="Tests directory for unittest discover (default: tests)")
    parser.add_argument("--top", type=int, default=20, help="Show lowest-N coverage modules (default: 20)")
    parser.add_argument("--quiet-tests", action="store_true", help="Run tests with minimal verbosity")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Fail when total coverage is below this percentage",
    )
    args = parser.parse_args()

    suite = build_unittest_suite(args.tests)
    runner = unittest.TextTestRunner(verbosity=0 if args.quiet_tests else 1)

    tracer = trace.Trace(
        count=True,
        trace=False,
        ignoredirs=[sys.prefix, sys.exec_prefix],
    )
    # stdlib trace caches ignore decisions by module *basename* (e.g. "__init__"),
    # which can accidentally hide our package modules if a stdlib module with the
    # same basename is ignored first. Force our package basenames to be traceable.
    package_root = Path(args.package)
    if package_root.exists():
        for module_file in package_root.rglob("*.py"):
            tracer.ignore._ignore[module_file.stem] = 0  # type: ignore[attr-defined]
    test_result = tracer.runfunc(runner.run, suite)
    tests_ok = test_result.wasSuccessful()

    rows = build_coverage_rows(args.package, tracer.results().counts)
    if not rows:
        print("[FAIL] No Python modules found for coverage analysis.")
        return 1

    print_coverage_table(rows, top=args.top)
    total_exec = sum(row.executed for row in rows)
    total_executable = sum(row.executable for row in rows)
    total_percent = coverage_percent(total_exec, total_executable)

    if args.fail_under is not None and total_percent < args.fail_under:
        print(
            f"[FAIL] total coverage {total_percent:.1f}% is below threshold {args.fail_under:.1f}%."
        )
        return 1

    if not tests_ok:
        print("[FAIL] Unit tests failed during coverage run.")
        return 1

    print(f"[OK] module coverage report generated (total {total_percent:.1f}%).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

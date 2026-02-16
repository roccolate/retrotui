#!/usr/bin/env python3
"""Run repository quality checks.

Checks included:
- UTF-8 validation on source/docs/config files
- Python bytecode compilation for project/test packages
- Version consistency between package metadata and runtime constant
- Unit tests in tests/
- Optional per-module coverage summary (stdlib trace)
"""

from __future__ import annotations

import argparse
import compileall
import re
import subprocess
import sys
from pathlib import Path

TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".sh",
    ".txt",
    ".html",
    ".json",
}

EXPLICIT_TEXT_FILES = {
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    "pre-commit",
}

DEFAULT_SCAN_PATHS = [
    "retrotui",
    "tests",
    "tools",
    ".github",
    ".githooks",
    "README.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "PROJECT.md",
    "RELEASE.md",
    "pyproject.toml",
    "setup.sh",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
]

COMPILE_PATHS = [
    "retrotui",
    "tools",
]


def _iter_text_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()

    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue

        if path.is_file():
            if path.name in EXPLICIT_TEXT_FILES or path.suffix.lower() in TEXT_EXTENSIONS:
                if path not in seen:
                    files.append(path)
                    seen.add(path)
            continue

        for child in path.rglob("*"):
            if not child.is_file():
                continue
            if child.name in EXPLICIT_TEXT_FILES or child.suffix.lower() in TEXT_EXTENSIONS:
                if child not in seen:
                    files.append(child)
                    seen.add(child)

    files.sort()
    return files


def check_utf8(paths: list[str]) -> int:
    """Validate UTF-8 decoding for known text files."""
    bad_files: list[str] = []
    for file_path in _iter_text_files(paths):
        try:
            file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            bad_files.append(f"{file_path}: {exc}")

    if bad_files:
        print("[FAIL] UTF-8 validation failed:")
        for line in bad_files:
            print(f"  - {line}")
        return 1

    print("[OK] UTF-8 validation passed.")
    return 0


def check_compile(paths: list[str]) -> int:
    """Compile Python files to bytecode to catch syntax errors."""
    success = True
    for path in paths:
        if not Path(path).exists():
            continue
        if not compileall.compile_dir(path, quiet=1, force=False):
            success = False

    if success:
        print("[OK] compileall passed.")
        return 0

    print("[FAIL] compileall failed.")
    return 1


def check_tests() -> int:
    """Run unit tests."""
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        print("[OK] unit tests passed.")
        return 0

    print("[FAIL] unit tests failed.")
    return result.returncode


def check_module_coverage(top: int, fail_under: float | None) -> int:
    """Run optional module-level coverage report."""
    cmd = [
        sys.executable,
        "tools/report_module_coverage.py",
        "--quiet-tests",
        "--top",
        str(top),
    ]
    if fail_under is not None:
        cmd.extend(["--fail-under", str(fail_under)])

    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        print("[OK] module coverage report passed.")
        return 0

    print("[FAIL] module coverage report failed.")
    return result.returncode


def check_version_sync() -> int:
    """Verify package/version constants stay aligned across release-critical files."""
    pyproject = Path("pyproject.toml")
    app_file = Path("retrotui/core/app.py")

    if not pyproject.exists() or not app_file.exists():
        print("[FAIL] version sync check: required files missing.")
        return 1

    project_text = pyproject.read_text(encoding="utf-8")
    app_text = app_file.read_text(encoding="utf-8")

    project_match = re.search(r'^\s*version\s*=\s*"([^"]+)"', project_text, flags=re.MULTILINE)
    app_match = re.search(r"^APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", app_text, flags=re.MULTILINE)

    if not project_match or not app_match:
        print("[FAIL] version sync check: unable to parse version fields.")
        return 1

    project_version = project_match.group(1)
    app_version = app_match.group(1)
    if project_version != app_version:
        print(
            "[FAIL] version sync mismatch: "
            f"pyproject.toml={project_version} vs retrotui/core/app.py={app_version}"
        )
        return 1

    print(f"[OK] version sync passed ({project_version}).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RetroTUI quality checks.")
    parser.add_argument("--skip-encoding", action="store_true", help="Skip UTF-8 validation.")
    parser.add_argument("--skip-compile", action="store_true", help="Skip compileall check.")
    parser.add_argument("--skip-version-sync", action="store_true", help="Skip version consistency check.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip unit tests.")
    parser.add_argument(
        "--module-coverage",
        action="store_true",
        help="Run module-level coverage report (replaces standard test step).",
    )
    parser.add_argument(
        "--module-coverage-top",
        type=int,
        default=20,
        help="Show lowest N modules in module coverage report (default: 20).",
    )
    parser.add_argument(
        "--module-coverage-fail-under",
        type=float,
        default=None,
        help="Fail module coverage when total percent is below this value.",
    )
    args = parser.parse_args()

    exit_code = 0

    if not args.skip_encoding:
        exit_code |= check_utf8(DEFAULT_SCAN_PATHS)

    if not args.skip_compile:
        exit_code |= check_compile(COMPILE_PATHS)

    if not args.skip_version_sync:
        exit_code |= check_version_sync()

    if args.module_coverage and args.skip_tests:
        print("[FAIL] --module-coverage cannot be combined with --skip-tests.")
        exit_code |= 1
    elif not args.skip_tests:
        if args.module_coverage:
            exit_code |= check_module_coverage(
                top=args.module_coverage_top,
                fail_under=args.module_coverage_fail_under,
            )
        else:
            exit_code |= check_tests()

    if exit_code == 0:
        print("[OK] all quality checks passed.")
    else:
        print("[FAIL] one or more quality checks failed.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

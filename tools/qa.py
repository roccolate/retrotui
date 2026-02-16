#!/usr/bin/env python3
"""Run repository quality checks.

Checks included:
- UTF-8 validation on source/docs/config files
- Python bytecode compilation for project/test packages
- Unit tests in tests/
"""

from __future__ import annotations

import argparse
import compileall
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
}

DEFAULT_SCAN_PATHS = [
    "retrotui",
    "tests",
    "README.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "PROJECT.md",
    "PROJECT_ANALYSIS.md",
    "pyproject.toml",
    "setup.sh",
    ".gitignore",
]

COMPILE_PATHS = [
    "retrotui",
    "tests",
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RetroTUI quality checks.")
    parser.add_argument("--skip-encoding", action="store_true", help="Skip UTF-8 validation.")
    parser.add_argument("--skip-compile", action="store_true", help="Skip compileall check.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip unit tests.")
    args = parser.parse_args()

    exit_code = 0

    if not args.skip_encoding:
        exit_code |= check_utf8(DEFAULT_SCAN_PATHS)

    if not args.skip_compile:
        exit_code |= check_compile(COMPILE_PATHS)

    if not args.skip_tests:
        exit_code |= check_tests()

    if exit_code == 0:
        print("[OK] all quality checks passed.")
    else:
        print("[FAIL] one or more quality checks failed.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

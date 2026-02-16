#!/usr/bin/env python3
"""Validate that a release tag matches project/runtime versions."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def _extract_project_version(pyproject_path: Path) -> str:
    text = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if not match:
        raise ValueError("Unable to parse [project].version from pyproject.toml")
    return match.group(1)


def _extract_app_version(app_path: Path) -> str:
    text = app_path.read_text(encoding="utf-8")
    match = re.search(r"^APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", text, flags=re.MULTILINE)
    if not match:
        raise ValueError("Unable to parse APP_VERSION from retrotui/core/app.py")
    return match.group(1)


def validate_release_tag(tag: str, pyproject_path: Path, app_path: Path) -> int:
    if not tag.startswith("v"):
        print(f"[FAIL] Tag must start with 'v': {tag}")
        return 1

    try:
        project_version = _extract_project_version(pyproject_path)
        app_version = _extract_app_version(app_path)
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return 1

    tag_version = tag[1:]
    if tag_version != project_version:
        print(
            "[FAIL] Tag/version mismatch: "
            f"tag={tag_version} vs pyproject.toml={project_version}"
        )
        return 1

    if tag_version != app_version:
        print(
            "[FAIL] Tag/version mismatch: "
            f"tag={tag_version} vs retrotui/core/app.py={app_version}"
        )
        return 1

    print(f"[OK] release tag matches project/app version ({tag}).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate release tag against project versions.")
    parser.add_argument("--tag", required=True, help="Release tag in format vX.Y.Z")
    parser.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: pyproject.toml)",
    )
    parser.add_argument(
        "--app-file",
        default="retrotui/core/app.py",
        help="Path to app module with APP_VERSION (default: retrotui/core/app.py)",
    )
    args = parser.parse_args()

    return validate_release_tag(args.tag, Path(args.pyproject), Path(args.app_file))


if __name__ == "__main__":
    raise SystemExit(main())

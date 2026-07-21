#!/usr/bin/env python3
"""Apply transactional trash hardening to RetroTUI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, content):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path, old, new):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:80]!r}")
    write(path, text.replace(old, new, 1))


def replace_between(path, start_marker, end_marker, replacement):
    text = read(path)
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"{path}: start marker not found: {start_marker!r}")
    if end_marker:
        end = text.find(end_marker, start)
        if end < 0:
            raise RuntimeError(f"{path}: end marker not found: {end_marker!r}")
        suffix = text[end:]
    else:
        suffix = ""
    write(path, text[:start] + replacement + suffix)

write('retrotui/core/trash_transaction.py', 'PLACEHOLDER')

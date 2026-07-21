#!/usr/bin/env python3
"""Apply transactional trash integration patches."""
from __future__ import annotations

import base64
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = "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"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, content):
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path, old, new):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    write(path, text.replace(old, new, 1))


def replace_between(path, start_marker, end_marker, replacement):
    text = read(path)
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"{path}: start marker not found")
    if end_marker:
        end = text.find(end_marker, start)
        if end < 0:
            raise RuntimeError(f"{path}: end marker not found")
        suffix = text[end:]
    else:
        suffix = ""
    write(path, text[:start] + replacement + suffix)


operations = json.loads(zlib.decompress(base64.b64decode(PAYLOAD)))
for operation in operations:
    if operation[0] == "once":
        _, path, old, new = operation
        replace_once(path, old, new)
    else:
        _, path, start, end, replacement = operation
        replace_between(path, start, end, replacement)

print("transactional trash integration applied")

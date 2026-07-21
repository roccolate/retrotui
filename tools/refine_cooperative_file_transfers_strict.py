#!/usr/bin/env python3
"""Require the literal cooperative marker instead of generic truthiness."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "retrotui" / "core" / "file_operations.py"
text = path.read_text(encoding="utf-8")
old = "        cancellable = bool(getattr(worker, '_retrotui_cancellable', False))\n"
new = "        cancellable = getattr(worker, '_retrotui_cancellable', False) is True\n"
if text.count(old) != 1:
    raise RuntimeError("expected one cancellable worker marker")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("strict cooperative worker marker applied")

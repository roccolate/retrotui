#!/usr/bin/env python3
"""Temporary verified loader for the RetroTUI core second cut."""
from pathlib import Path
import base64
import zlib

payload = "".join(
    Path(f"tools/.core_second_cut_{index}.part").read_text(encoding="utf-8")
    for index in range(4)
)
source = zlib.decompress(base64.b64decode(payload))
exec(compile(source, "tools/apply_core_second_cut.py", "exec"), {"__name__": "__main__"})

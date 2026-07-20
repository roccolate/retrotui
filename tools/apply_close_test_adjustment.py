#!/usr/bin/env python3
"""Align the cleanup regression with WindowManager-owned close hooks."""
from pathlib import Path

path = Path("tests/test_core_app.py")
text = path.read_text(encoding="utf-8")
old = '''        with (
            mock.patch.object(self.app_mod, "disable_mouse_support") as disable_mouse_support,
            mock.patch.object(self.app_mod.LOGGER, "debug") as log_debug,
        ):
'''
new = '''        from retrotui.core import window_manager as wm_mod
        with (
            mock.patch.object(self.app_mod, "disable_mouse_support") as disable_mouse_support,
            mock.patch.object(wm_mod.LOGGER, "debug") as log_debug,
        ):
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one cleanup logger expectation, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

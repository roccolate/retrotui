"""Retarget cleanup tests to the modules that own signal and threading."""

from pathlib import Path


path = Path("tests/test_core_app.py")
text = path.read_text(encoding="utf-8")

anchor = '''        cls.constants_mod = importlib.import_module("retrotui.constants")
        cls.dialog_mod = importlib.import_module("retrotui.ui.dialog")
        cls.app_mod = importlib.import_module("retrotui.core.app")
'''
replacement = '''        cls.constants_mod = importlib.import_module("retrotui.constants")
        cls.dialog_mod = importlib.import_module("retrotui.ui.dialog")
        cls.file_ops_mod = importlib.import_module("retrotui.core.file_operations")
        cls.signal_mod = importlib.import_module("retrotui.core.signal_handler")
        cls.app_mod = importlib.import_module("retrotui.core.app")
'''
if text.count(anchor) != 1:
    raise RuntimeError("test owner-module import anchor not found uniquely")
text = text.replace(anchor, replacement, 1)

owner_replacements = {
    "self.app_mod.threading": "self.file_ops_mod.threading",
    "self.app_mod.signal": "self.signal_mod.signal",
}
for old, new in owner_replacements.items():
    count = text.count(old)
    if count == 0:
        raise RuntimeError(f"expected at least one test reference to {old}")
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8")

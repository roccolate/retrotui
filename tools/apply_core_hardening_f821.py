#!/usr/bin/env python3
"""Patch the remaining F821 baseline found by the hardening gate."""
from pathlib import Path


path = Path(__file__).resolve().parents[1] / "retrotui/apps/wifi_manager.py"
text = path.read_text(encoding="utf-8")

old_import = "import curses\nimport shutil\n"
new_import = "import curses\nimport logging\nimport shutil\n"
if new_import not in text:
    if old_import not in text:
        raise RuntimeError("wifi_manager import block changed")
    text = text.replace(old_import, new_import, 1)

old_marker = "from ..utils import safe_addstr, theme_attr\n\nNMCLI_QUICK_TIMEOUT"
new_marker = (
    "from ..utils import safe_addstr, theme_attr\n\n"
    "LOGGER = logging.getLogger(__name__)\n\n"
    "NMCLI_QUICK_TIMEOUT"
)
if new_marker not in text:
    if old_marker not in text:
        raise RuntimeError("wifi_manager logger marker changed")
    text = text.replace(old_marker, new_marker, 1)

path.write_text(text, encoding="utf-8")

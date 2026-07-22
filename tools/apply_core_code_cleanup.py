"""Apply the conservative RetroTUI core code-cleanup cut.

Temporary one-shot helper. It is removed before the pull request is merged.
"""

from __future__ import annotations

import ast
from pathlib import Path


APP_PATH = Path("retrotui/core/app.py")
TEST_PATH = Path("tests/test_core_app.py")
CI_PATH = Path(".github/workflows/ci.yml")

DEAD_APP_METHODS = {
    "_build_plugin_menu_items",
    "_build_plugin_window",
    "_split_config_csv",
    "_menu_item_visibility_key",
    "_get_hidden_menu_keys",
    "_build_menu_editor_catalog",
    "_close_window_safely",
    "_normalize_icon_style",
    "_icon_style_variants",
    "_style_symbol_for_icon",
    "_styled_icon_entry",
    "_icon_visibility_key",
    "_get_hidden_icon_labels",
    "_plugin_icon_art",
    "_build_plugin_icons",
    "_build_desktop_icon_catalog",
    "_save_icon_positions",
    "_activate_last_visible_window",
    "_consume_pending_sigint",
}


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def remove_class_methods(text: str, class_name: str, method_names: set[str]) -> str:
    tree = ast.parse(text)
    target = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ),
        None,
    )
    if target is None:
        raise RuntimeError(f"class {class_name!r} not found")

    lines = text.splitlines(keepends=True)
    ranges: list[tuple[int, int]] = []
    found: set[str] = set()
    for node in target.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in method_names:
            continue
        found.add(node.name)
        starts = [node.lineno, *(decorator.lineno for decorator in node.decorator_list)]
        start = min(starts) - 1
        end = node.end_lineno
        while end < len(lines) and not lines[end].strip():
            end += 1
        ranges.append((start, end))

    missing = method_names - found
    if missing:
        raise RuntimeError(f"missing methods: {sorted(missing)}")

    for start, end in sorted(ranges, reverse=True):
        del lines[start:end]

    cleaned = "".join(lines)
    while "\n\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n\n", "\n\n\n")
    return cleaned


def patch_app() -> None:
    text = APP_PATH.read_text(encoding="utf-8")

    for unused_import in ("import signal\n", "import threading\n"):
        text = replace_once(
            text,
            unused_import,
            "",
            label=f"remove {unused_import.strip()}",
        )

    text = replace_once(
        text,
        "    ICONS, ICONS_ASCII,\n",
        "",
        label="remove accidental constants re-export",
    )
    text = replace_once(
        text,
        "from ..ui.dialog import Dialog, InputDialog, ProgressDialog\n",
        "from ..ui.dialog import Dialog, InputDialog\n",
        label="remove unused ProgressDialog import",
    )
    text = replace_once(
        text,
        "        from ..ui.dialog import Dialog\n\n",
        "",
        label="remove duplicate local Dialog import",
    )
    text = replace_once(
        text,
        "        from ..ui.dialog import InputDialog\n        from .actions import ActionResult, ActionType\n",
        "",
        label="remove duplicate bookmark imports",
    )

    old_icon_imports = '''from .icon_styles import (
    ICON_STYLE_DEFAULT,
    ICON_STYLE_MINI,
    ICON_STYLE_BRAILLE,
    ICON_STYLE_RETRO_01,
    normalize_icon_style,
    icon_style_variants as _icon_style_variants,
    style_symbol_for_icon as _style_symbol_for_icon,
    styled_icon_entry as _styled_icon_entry,
    icon_style_preview_symbol as _icon_style_preview_symbol,
    icon_visibility_key as _icon_visibility_key,
    get_hidden_icon_labels as _get_hidden_icon_labels,
    split_config_csv as _split_config_csv,
    plugin_icon_art as _plugin_icon_art,
    build_plugin_icons as _build_plugin_icons,
    build_desktop_icon_catalog as _build_desktop_icon_catalog,
    refresh_icons as _refresh_icons,
)
'''
    new_icon_imports = '''from .icon_styles import (
    ICON_STYLE_DEFAULT,
    normalize_icon_style,
    icon_style_preview_symbol as _icon_style_preview_symbol,
    refresh_icons as _refresh_icons,
)
'''
    text = replace_once(
        text,
        old_icon_imports,
        new_icon_imports,
        label="simplify icon-style imports",
    )

    old_signal_imports = '''from .signal_handler import (
    install_runtime_signal_handlers,
    restore_runtime_signal_handlers,
    queue_pending_signal_key,
    consume_pending_signal_key,
    consume_pending_sigint,
)
'''
    new_signal_imports = '''from .signal_handler import (
    install_runtime_signal_handlers,
    restore_runtime_signal_handlers,
    queue_pending_signal_key,
    consume_pending_signal_key,
)
'''
    text = replace_once(
        text,
        old_signal_imports,
        new_signal_imports,
        label="simplify signal-handler imports",
    )

    old_plugin_imports = '''from .plugin_manager import (
    load_plugins_runtime,
    register_plugin_manifest,
    build_plugin_menu_items,
    build_plugin_window,
    open_plugin as _open_plugin,
)
'''
    new_plugin_imports = '''from .plugin_manager import (
    load_plugins_runtime,
    register_plugin_manifest,
    open_plugin as _open_plugin,
)
'''
    text = replace_once(
        text,
        old_plugin_imports,
        new_plugin_imports,
        label="simplify plugin-manager imports",
    )

    old_menu_imports = '''from .menu_builder import (
    menu_item_visibility_key as _menu_item_visibility_key,
    get_hidden_menu_keys as _get_hidden_menu_keys,
    build_global_menu_items,
    rebuild_global_menu,
    build_menu_editor_catalog,
)
'''
    text = replace_once(
        text,
        old_menu_imports,
        "from .menu_builder import build_global_menu_items, rebuild_global_menu\n",
        label="simplify menu-builder imports",
    )
    text = replace_once(
        text,
        "    LONG_FILE_OPERATION_BYTES = 8 * 1024 * 1024\n",
        "",
        label="remove duplicate file-operation threshold",
    )

    text = remove_class_methods(text, "RetroTUI", DEAD_APP_METHODS)
    APP_PATH.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_PATH.read_text(encoding="utf-8")
    old_imports = '''        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.app_mod = importlib.import_module("retrotui.core.app")
'''
    new_imports = '''        cls.actions_mod = importlib.import_module("retrotui.core.actions")
        cls.constants_mod = importlib.import_module("retrotui.constants")
        cls.dialog_mod = importlib.import_module("retrotui.ui.dialog")
        cls.app_mod = importlib.import_module("retrotui.core.app")
'''
    text = replace_once(
        text,
        old_imports,
        new_imports,
        label="test owner-module imports",
    )

    replacements = {
        "self.app_mod.ICONS_ASCII": "self.constants_mod.ICONS_ASCII",
        "self.app_mod.ICONS": "self.constants_mod.ICONS",
        "self.app_mod.ProgressDialog": "self.dialog_mod.ProgressDialog",
        "self.app_mod.InputDialog": "self.dialog_mod.InputDialog",
        "self.app_mod.Dialog(": "self.dialog_mod.Dialog(",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    TEST_PATH.write_text(text, encoding="utf-8")


def patch_ci() -> None:
    text = CI_PATH.read_text(encoding="utf-8")
    anchor = '''      - name: Reject undefined Python names
        run: python -m ruff check --select F821 retrotui tests tools
'''
    replacement = anchor + '''
      - name: Reject unused RetroTUI composition code
        run: python -m ruff check --select F401,F811,F841 retrotui/core/app.py
'''
    count = text.count(anchor)
    if count != 2:
        raise RuntimeError(
            "incremental app cleanup lint gate: "
            f"expected temporary and permanent anchors, found {count}"
        )
    index = text.rfind(anchor)
    text = text[:index] + replacement + text[index + len(anchor):]
    CI_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    patch_app()
    patch_tests()
    patch_ci()


if __name__ == "__main__":
    main()

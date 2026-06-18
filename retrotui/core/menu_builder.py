"""
Global menu construction, filtering, and editor catalog.
"""

from .actions import AppAction


def menu_item_visibility_key(label, action):
    """Return stable visibility key for one global menu item."""
    if isinstance(action, AppAction):
        return action.value.lower()
    if isinstance(action, str):
        return action.lower()
    base_label = str(label or "").split("  ")[0].strip().lower()
    return base_label


def get_hidden_menu_keys(config):
    """Return set of lowercased hidden global menu item keys from config."""
    from .icon_styles import split_config_csv
    raw = getattr(config, 'hidden_menu_items', "")
    return split_config_csv(raw)


def is_menu_key_hidden(item_key, hidden_menu_items):
    """Return True when a menu key is explicitly or wildcard-hidden."""
    key = str(item_key or "").strip().lower()
    if key in hidden_menu_items:
        return True
    return key.startswith("plugin:") and "plugin:*" in hidden_menu_items


def build_global_menu_items(app):
    """Return global menu items with hidden-label filtering and plugin section."""
    from .plugin_manager import build_categorized_plugin_menu_items

    hidden_menu_items = get_hidden_menu_keys(app.config)
    from ..ui.menu import DEFAULT_GLOBAL_ITEMS

    filtered_menu_items = {}
    for category, items in DEFAULT_GLOBAL_ITEMS.items():
        filtered_items = []
        for label, action in items:
            item_key = menu_item_visibility_key(label, action)
            if not is_menu_key_hidden(item_key, hidden_menu_items):
                filtered_items.append((label, action))
        if filtered_items:
            filtered_menu_items[category] = filtered_items

    games, plugins = build_categorized_plugin_menu_items(app)
    if games:
        filtered_menu_items["Games"] = games
    if plugins:
        filtered_menu_items["Plugins"] = plugins
    if not games and not plugins and "plugin:*" not in hidden_menu_items:
        filtered_menu_items["Plugins"] = [("(No plugins installed)", None)]

    return filtered_menu_items


def rebuild_global_menu(app):
    """Rebuild global menu preserving previous selection when possible."""
    from ..ui.menu import Menu

    previous = getattr(app, "menu", None)
    was_active = bool(getattr(previous, "active", False))
    selected_menu = int(getattr(previous, "selected_menu", 0) or 0)
    selected_item = int(getattr(previous, "selected_item", 0) or 0)

    menu = Menu(build_global_menu_items(app))
    menu_names = list(getattr(menu, "menu_names", ()) or ())
    if was_active and menu_names:
        menu.active = True
        menu.selected_menu = max(0, min(selected_menu, len(menu_names) - 1))
        current_items = list(
            (getattr(menu, "items", {}) or {}).get(menu_names[menu.selected_menu], ())
        )
        if current_items:
            menu.selected_item = max(0, min(selected_item, len(current_items) - 1))
        else:
            menu.selected_item = 0

    app.menu = menu


def build_menu_editor_catalog(app):
    """Return editable menu entries (apps, games, plugins) with stable keys."""
    from ..ui.menu import DEFAULT_GLOBAL_ITEMS

    entries = []
    for category, items in DEFAULT_GLOBAL_ITEMS.items():
        for label, action in items:
            if action is None:
                continue
            base_label = str(label).split("  ")[0].strip()
            entries.append(
                {
                    "category": category,
                    "label": base_label,
                    "action": action,
                    "key": menu_item_visibility_key(base_label, action),
                }
            )

    from .plugin_manager import _get_plugin_category

    for plugin_id, info in (getattr(app, "_plugins", None) or {}).items():
        plugin_info = (info.get("manifest", {}) or {}).get("plugin", {}) or {}
        name = str(plugin_info.get("name") or plugin_id)
        action = f"plugin:{plugin_id}"
        cat = _get_plugin_category(info)
        cat_label = "Games" if cat == "game" else "Plugins"
        entries.append(
            {
                "category": cat_label,
                "label": name,
                "action": action,
                "key": menu_item_visibility_key(name, action),
            }
        )

    entries.sort(key=lambda item: (item["category"].lower(), item["label"].lower()))
    return entries

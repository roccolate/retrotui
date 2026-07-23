"""
Plugin discovery, registration, and window instantiation.
"""

import logging

from .window_manager import WindowSpawnSpec, resolve_window_spawn

LOGGER = logging.getLogger(__name__)

_PLUGIN_DISCOVERY_IMPORT_ERRORS = (
    ImportError,
    ModuleNotFoundError,
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
def load_plugins_runtime(app):
    """Discover and register plugins (best effort; never crash startup)."""
    app._plugins = {}
    if plugins_disabled_by_visibility(app):
        app.refresh_icons()
        app._rebuild_global_menu()
        return
    try:
        from ..plugins.loader import discover_plugins, load_plugin
    except _PLUGIN_DISCOVERY_IMPORT_ERRORS:
        LOGGER.debug('plugin discovery unavailable', exc_info=True)
        app.refresh_icons()
        app._rebuild_global_menu()
        return

    try:
        manifests = discover_plugins()
    except Exception:  # Discovery boundary: a plugin source must not abort startup.
        LOGGER.debug("plugin discovery failed", exc_info=True)
        app.refresh_icons()
        app._rebuild_global_menu()
        return
    for manifest in manifests:
        register_plugin_manifest(app, manifest, load_plugin)
    app.refresh_icons()
    app._rebuild_global_menu()


def plugins_disabled_by_visibility(app):
    """Return True when config disables plugin menu entries and desktop icons."""
    from .icon_styles import get_hidden_icon_labels
    from .menu_builder import get_hidden_menu_keys

    return (
        "plugin:*" in get_hidden_icon_labels(getattr(app, "config", None))
        and "plugin:*" in get_hidden_menu_keys(getattr(app, "config", None))
    )


def register_plugin_manifest(app, manifest, load_plugin):
    """Register one plugin manifest with defensive isolation."""
    try:
        app_class = load_plugin(manifest)
    except Exception:  # Plugin boundary: isolate application-defined exceptions.
        LOGGER.debug('failed to load plugin manifest', exc_info=True)
        return
    if not app_class:
        return
    plugin_info = manifest.get('plugin', {})
    pid = plugin_info.get('id')
    if not pid:
        return
    app._plugins[pid] = {
        'class': app_class,
        'manifest': manifest,
    }


def _get_plugin_category(info):
    """Return the category string for a plugin ('game' or 'plugin')."""
    plugin_info = (info.get("manifest", {}) or {}).get("plugin", {}) or {}
    return str(plugin_info.get("category") or "plugin").lower()


def build_plugin_menu_items(app):
    """Build dynamic plugin entries as menu tuples ``(label, action)``."""
    from .menu_builder import is_menu_key_hidden, menu_item_visibility_key, get_hidden_menu_keys

    hidden_menu_items = get_hidden_menu_keys(app.config)
    entries = []
    for plugin_id, info in (getattr(app, "_plugins", None) or {}).items():
        plugin_info = (info.get("manifest", {}) or {}).get("plugin", {}) or {}
        name = str(plugin_info.get("name") or plugin_id)
        action = f"plugin:{plugin_id}"
        item_key = menu_item_visibility_key(name, action)
        if is_menu_key_hidden(item_key, hidden_menu_items):
            continue
        entries.append((name, action))
    entries.sort(key=lambda item: (item[0].lower(), item[1]))
    return entries


def build_categorized_plugin_menu_items(app):
    """Build plugin menu items split by category.

    Returns ``(games, plugins)`` where each is a list of
    ``(label, action)`` tuples.
    """
    from .menu_builder import is_menu_key_hidden, menu_item_visibility_key, get_hidden_menu_keys

    hidden_menu_items = get_hidden_menu_keys(app.config)
    games = []
    plugins = []
    for plugin_id, info in (getattr(app, "_plugins", None) or {}).items():
        plugin_info = (info.get("manifest", {}) or {}).get("plugin", {}) or {}
        name = str(plugin_info.get("name") or plugin_id)
        action = f"plugin:{plugin_id}"
        item_key = menu_item_visibility_key(name, action)
        if is_menu_key_hidden(item_key, hidden_menu_items):
            continue
        category = _get_plugin_category(info)
        if category == "game":
            games.append((name, action))
        else:
            plugins.append((name, action))
    games.sort(key=lambda item: (item[0].lower(), item[1]))
    plugins.sort(key=lambda item: (item[0].lower(), item[1]))
    return games, plugins


def build_plugin_window(app, info, plugin_id):
    """Instantiate plugin window object from manifest metadata."""
    manifest = info.get('manifest', {}).get('plugin', {})
    win_config = manifest.get('window', {})
    w = int(win_config.get('default_width', 40))
    h = int(win_config.get('default_height', 15))
    try:
        cls = info.get('class')
        x, y, width, height = resolve_window_spawn(
            app,
            WindowSpawnSpec(w, h, 8, 3),
        )
        return cls(manifest.get('name', plugin_id), x, y, width, height)
    except Exception:  # Plugin boundary: isolate application-defined exceptions.
        LOGGER.debug('failed to open plugin %s', plugin_id, exc_info=True)
        return None


def open_plugin(app, plugin_id):
    """Instantiate and open a plugin window by id."""
    if not getattr(app, '_plugins', None):
        return
    info = app._plugins.get(plugin_id)
    if not info:
        LOGGER.debug('plugin not found: %s', plugin_id)
        return
    win = build_plugin_window(app, info, plugin_id)
    if win is not None:
        app._spawn_window(win)

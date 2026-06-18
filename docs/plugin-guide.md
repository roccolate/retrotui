Plugin system guide
===================

This guide explains how to create and install RetroTUI plugins.

Plugin layout
-------------

Each plugin is a directory under `~/.config/retrotui/plugins/<id>/` with:

- `plugin.toml` — manifest describing plugin metadata and window defaults.
- `__init__.py` — plugin module; should export a `Plugin` class (subclass of `retrotui.plugins.base.RetroApp`).

Manifest example
----------------

```toml
[plugin]
id = "todo-list"
name = "Todo List"
version = "1.0.0"
description = "Simple task manager"
author = "Community"
category = "plugin"  # use "game" to place it in the Games menu

[plugin.window]
default_width = 40
default_height = 15
resizable = true

[plugin.icon]
emoji = "📝"
token = "TD"
```

API available to plugins
------------------------

- `retrotui.plugins.base.RetroApp` — base window class for plugins. Implement `draw_content` and input handlers.
- `retrotui.utils.safe_addstr(win, y, x, text, attr=0)` — safe string drawing helper.
- `retrotui.utils.theme_attr(role)` — obtain curses color attribute for theme roles.
- Clipboard / other utilities are available via `retrotui.utils` and other modules; prefer not to import internal private symbols.

Installing plugins
------------------

Copy the plugin directory into `~/.config/retrotui/plugins/` and restart RetroTUI. In the stable base profile, plugins are disabled by default; remove `plugin:*` from `ui.hidden_icons` and `ui.hidden_menu_items` in `~/.config/retrotui/config.toml` to enable plugin discovery in the desktop/menu UI.

For development, RetroTUI also discovers plugins from:

1. `RETROTUI_PLUGIN_DIR` — one forced plugin directory.
2. `RETROTUI_PLUGIN_PATH` — multiple directories separated by the OS path separator.
3. `retrotui/bundled_plugins/` — package bundled plugins.
4. `~/.config/retrotui/plugins/` — user plugins.
5. `examples/plugins/` — repo examples when using the default user plugin directory.

Plugin ids are de-duplicated by discovery order; the first matching id wins.

Testing plugins
---------------

Unit tests can point the loader at a local directory by setting `retrotui.plugins.loader.PLUGIN_DIR` to the test fixtures path.

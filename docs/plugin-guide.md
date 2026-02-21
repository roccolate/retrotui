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
name = "Todo List"
id = "todo-list"
version = "1.0.0"
description = "Simple task manager"
author = "Community"
icon = "📝"
menu_category = "Apps"

[plugin.window]
default_width = 40
default_height = 15
resizable = true
```

API available to plugins
------------------------

- `retrotui.plugins.base.RetroApp` — base window class for plugins. Implement `draw_content` and input handlers.
- `retrotui.utils.safe_addstr(win, y, x, text, attr=0)` — safe string drawing helper.
- `retrotui.utils.theme_attr(role)` — obtain curses color attribute for theme roles.
- Clipboard / other utilities are available via `retrotui.utils` and other modules; prefer not to import internal private symbols.

Installing plugins
------------------

Copy the plugin directory into `~/.config/retrotui/plugins/` and restart RetroTUI. The loader will discover and load the plugin manifest and module.

Testing plugins
---------------

Unit tests can point the loader at a local directory by setting `retrotui.plugins.loader.PLUGIN_DIR` to the test fixtures path.

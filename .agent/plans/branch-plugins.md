# Branch: feature/plugins (v0.9.3 Plugin System)
# Agente asignado: Sonnet o GPT-5 mini

## Setup
```bash
git checkout main
git pull
git checkout -b feature/plugins
```

## Contexto del proyecto
RetroTUI es un entorno de escritorio estilo Windows 3.1 para terminal Linux.
Usa Python + curses. Las apps heredan de `retrotui.ui.window.Window`.
Estructura: `retrotui/apps/` contiene cada app como módulo.
Config en `~/.config/retrotui/config.toml`.

Estudiar estos archivos ANTES de empezar:
- `retrotui/ui/window.py` — clase base Window (draw, handle_key, handle_click, handle_scroll)
- `retrotui/core/app.py` — cómo se registran apps, iconos de escritorio, menú
- `retrotui/core/actions.py` — sistema ActionResult/ActionType
- `retrotui/apps/calculator.py` — app simple como referencia
- `retrotui/core/config.py` — sistema de configuración actual
- `retrotui/theme.py` — sistema de temas

## Tareas

### 1. Clase base RetroApp

Crear `retrotui/plugins/base.py`:

```python
"""Base class for RetroTUI plugins."""
from ..ui.window import Window


class RetroApp(Window):
    """Ergonomic base class for plugin apps.
    
    Plugins subclass this and implement:
    - draw_content(stdscr, x, y, w, h): Draw app content in body area
    - handle_key(key): Handle keyboard input
    - handle_click(mx, my): Handle mouse clicks
    
    Metadata comes from plugin.toml manifest.
    """
    
    PLUGIN_ID = None  # Set by loader from manifest
    
    def __init__(self, title, x, y, w, h, **kwargs):
        super().__init__(title, x, y, w, h, **kwargs)
    
    def draw_content(self, stdscr, x, y, w, h):
        """Override this to draw your app content."""
        pass
    
    def draw(self, stdscr):
        """Draw frame + delegate body to draw_content."""
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        self.draw_content(stdscr, bx, by, bw, bh)
```

### 2. Plugin manifest format

Cada plugin es un directorio en `~/.config/retrotui/plugins/<name>/`:

```
~/.config/retrotui/plugins/
  todo-list/
    plugin.toml      # Manifest
    __init__.py       # Main module, exports the app class
    (optional files)
```

**plugin.toml:**
```toml
[plugin]
name = "Todo List"
id = "todo-list"
version = "1.0.0"
description = "Simple task manager"
author = "Community"
icon = "📝"
menu_category = "Apps"  # Where it appears in the menu bar

[plugin.window]
default_width = 40
default_height = 15
resizable = true
```

### 3. Plugin loader

Crear `retrotui/plugins/loader.py`:

```python
"""Plugin discovery and loading."""
import os
import sys
import tomllib  # Python 3.11+, fallback to tomli for 3.9-3.10
import importlib.util
from pathlib import Path


PLUGIN_DIR = os.path.join(os.path.expanduser('~'), '.config', 'retrotui', 'plugins')


def discover_plugins():
    """Scan plugin directory and return list of plugin manifests."""
    plugins = []
    if not os.path.isdir(PLUGIN_DIR):
        return plugins
    
    for entry in os.scandir(PLUGIN_DIR):
        if not entry.is_dir():
            continue
        manifest_path = os.path.join(entry.path, 'plugin.toml')
        if not os.path.exists(manifest_path):
            continue
        
        try:
            with open(manifest_path, 'rb') as f:
                manifest = tomllib.load(f)
            manifest['_path'] = entry.path
            plugins.append(manifest)
        except Exception:
            continue  # Skip malformed plugins
    
    return plugins


def load_plugin(manifest):
    """Import plugin module and return the app class."""
    plugin_path = manifest['_path']
    init_path = os.path.join(plugin_path, '__init__.py')
    
    if not os.path.exists(init_path):
        return None
    
    plugin_id = manifest['plugin']['id']
    spec = importlib.util.spec_from_file_location(
        f'retrotui_plugin_{plugin_id}',
        init_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Plugin must export a class named 'Plugin' or the app class
    app_class = getattr(module, 'Plugin', None) or getattr(module, 'App', None)
    if app_class:
        app_class.PLUGIN_ID = plugin_id
    return app_class
```

### 4. Integración con app.py

Modificar `retrotui/core/app.py`:

**En `__init__` o startup:**
```python
from retrotui.plugins.loader import discover_plugins, load_plugin

# After normal app registration:
self._plugins = {}
for manifest in discover_plugins():
    try:
        app_class = load_plugin(manifest)
        if app_class:
            plugin_info = manifest['plugin']
            self._plugins[plugin_info['id']] = {
                'class': app_class,
                'manifest': manifest,
            }
    except Exception:
        pass  # Log but don't crash
```

**En desktop icons:** Agregar iconos dinámicos para cada plugin.

**En menú:** Agregar entrada bajo categoría del manifest.

**Al abrir plugin:**
```python
def open_plugin(self, plugin_id):
    info = self._plugins[plugin_id]
    manifest = info['manifest']['plugin']
    win_config = info['manifest'].get('plugin', {}).get('window', {})
    w = win_config.get('default_width', 40)
    h = win_config.get('default_height', 15)
    win = info['class'](
        manifest['name'],
        self.next_window_x(), self.next_window_y(),
        w, h
    )
    self.windows.append(win)
    self.focused = len(self.windows) - 1
```

### 5. Plugin de ejemplo: Todo List

Crear `examples/plugins/todo-list/`:

**plugin.toml:**
```toml
[plugin]
name = "Todo List"
id = "todo-list"
version = "1.0.0"
description = "Simple task manager with priorities"
author = "RetroTUI"
icon = "📝"
menu_category = "Apps"

[plugin.window]
default_width = 45
default_height = 20
resizable = true
```

**__init__.py:**
```python
"""Todo List plugin for RetroTUI."""
import json
import os
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.todos = []
        self.selected = 0
        self._load()
    
    def _data_path(self):
        return os.path.expanduser('~/.config/retrotui/todo-list.json')
    
    def _load(self):
        path = self._data_path()
        if os.path.exists(path):
            with open(path) as f:
                self.todos = json.load(f)
    
    def _save(self):
        path = self._data_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.todos, f)
    
    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        for i, todo in enumerate(self.todos[:h]):
            check = '[x]' if todo.get('done') else '[ ]'
            line = f" {check} {todo['text']}"
            a = attr
            if i == self.selected:
                a = theme_attr('menu_selected')
            safe_addstr(stdscr, y + i, x, line[:w], a)
    
    def handle_key(self, key):
        if key == ord('j') or key == 258:  # down
            self.selected = min(self.selected + 1, len(self.todos) - 1)
        elif key == ord('k') or key == 259:  # up
            self.selected = max(self.selected - 1, 0)
        elif key == ord(' '):  # toggle
            if self.todos:
                self.todos[self.selected]['done'] = not self.todos[self.selected].get('done')
                self._save()
        elif key == ord('a'):  # add (simplified)
            self.todos.append({'text': f'New task {len(self.todos)+1}', 'done': False})
            self._save()
        elif key == ord('d'):  # delete
            if self.todos:
                self.todos.pop(self.selected)
                self.selected = min(self.selected, max(len(self.todos)-1, 0))
                self._save()
```

### 6. Paquete retrotui/plugins/

Crear `retrotui/plugins/__init__.py` (vacío).

Estructura final:
```
retrotui/plugins/
  __init__.py
  base.py          # RetroApp class
  loader.py        # discover_plugins, load_plugin
```

### 7. Tests

Crear:
- `tests/test_plugin_loader.py` — discovery, manifest parsing, loading
- `tests/test_plugin_base.py` — RetroApp base class, draw delegation
- `tests/test_plugin_example.py` — Todo List funciona correctamente

Patrón de tests:
```python
import sys
from _support import make_fake_curses
sys.modules['curses'] = make_fake_curses()
```

### 8. Documentación

Crear `docs/plugin-guide.md`:
- Cómo crear un plugin paso a paso
- Formato del manifest
- API disponible (RetroApp, safe_addstr, theme_attr, clipboard)
- Cómo instalar un plugin (copiar directorio)
- Cómo testear un plugin

## Verificación
```bash
python tools/qa.py
git add -A
git commit -m "feat(v0.9.3): plugin system with loader, RetroApp base, and todo-list example"
```

## IMPORTANTE
- El plugin system NO debe crashear RetroTUI si un plugin falla
- Usar try/except generoso en loader
- `tomllib` es Python 3.11+; para 3.9-3.10 hacer fallback graceful o usar parser simple
  - Verificar `requires-python = ">=3.9"` en pyproject.toml
- Los plugins son OPCIONALES — RetroTUI debe funcionar perfecto sin ninguno instalado
- Correr `python tools/qa.py` ANTES de commitear

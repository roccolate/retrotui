# Branch: feature/cleanup-docs (v0.9.1 Foundation)
# Agente asignado: Sonnet o GPT-5 mini

## Setup
```bash
git checkout main
git pull
git checkout -b feature/cleanup-docs
```

## Tareas

### 1. Refactor filemanager.py → package

El archivo `retrotui/apps/filemanager.py` tiene 1289 líneas. Dividirlo en:

```
retrotui/apps/filemanager/
  __init__.py          # Re-exports: FileManagerWindow, FileEntry
  window.py            # La clase FileManagerWindow (navigation, draw, events, bookmarks, dual-pane)
  operations.py        # Métodos extraídos: copy_selected, move_selected, delete_selected,
                       # rename_selected, create_directory, create_file, undo_last_delete,
                       # _resolve_destination_path, _next_trash_path, _normalize_new_name,
                       # _dual_copy_move_between_panes (~300 líneas)
  preview.py           # Métodos extraídos: _read_text_preview, _read_image_preview,
                       # _detect_image_preview_backend, _entry_preview_lines,
                       # _entry_info_lines, _preview_lines, _preview_stat_key (~200 líneas)
```

**Técnica de extracción:** Usa mixins. `operations.py` define `FileOperationsMixin`, `preview.py` define `PreviewMixin`. `FileManagerWindow` hereda de `Window, FileOperationsMixin, PreviewMixin`.

**`__init__.py`:**
```python
from .window import FileManagerWindow, FileEntry
```

**Verificación:**
```bash
python tools/qa.py  # 702+ tests deben pasar
```

Ningún import externo debe cambiar. `from retrotui.apps.filemanager import FileManagerWindow` debe seguir funcionando.

### 2. README bilingüe

Editar `README.md`:
- Mover contenido actual español abajo bajo `## 🇪🇸 Español`
- Agregar sección `## 🇬🇧 English` arriba con traducción
- Mantener badges al inicio (ya están)
- Agregar sección "Features" con lista de apps incluidas
- Agregar sección "Screenshots" (placeholder `<!-- TODO: screenshots -->`)

### 3. ARCHITECTURE.md

Renombrar `PROJECT.md` → `ARCHITECTURE.md`:
```bash
git mv PROJECT.md ARCHITECTURE.md
```

Actualizar contenido:
- Agregar diagrama mermaid de la arquitectura
- Documentar el patrón Window → ActionResult → App
- Documentar estructura de directorios actual
- Mencionar el split de filemanager

### 4. CONTRIBUTING.md

Crear `CONTRIBUTING.md` con:
- Cómo correr tests: `python tools/qa.py`
- Convenciones: UTF-8/LF, fake curses pattern, `from _support import`
- Cómo agregar una app nueva (subclass Window, registro en app.py)
- Cómo agregar un tema nuevo (editar theme.py)
- CI: GitHub Actions en Linux + Windows

## Verificación final
```bash
python tools/qa.py
git add -A
git commit -m "feat(v0.9.1): refactor filemanager, bilingual README, ARCHITECTURE.md, CONTRIBUTING.md"
```

## IMPORTANTE
- NO tocar archivos fuera del scope de esta branch
- NO modificar `pyproject.toml` version
- Si un test falla, arreglarlo
- Correr `python tools/qa.py` ANTES de commitear

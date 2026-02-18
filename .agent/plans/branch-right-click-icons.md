# Branch: feature/right-click-icons (v0.9.1 UX)
# Agente asignado: Sonnet o GPT-5 mini

## Setup
```bash
git checkout main
git pull
git checkout -b feature/right-click-icons
```

## Tareas

### 1. Context Menu (clic derecho)

**Componente UI: ContextMenu**

Crear `retrotui/ui/context_menu.py`:
- Clase `ContextMenu` que extiende el patrón de `retrotui/ui/menu.py`
- Se abre en posición (x, y) del mouse
- Lista de items con acción asociada
- Tecla Escape o click fuera cierra
- Soporte de separadores

**Integración con mouse_router.py:**
- En `retrotui/core/mouse_router.py`, detectar `BUTTON3_PRESSED` (botón derecho)
- Si click derecho en Desktop → context menu desktop
- Si click derecho en File Manager → context menu de archivos
- Si click derecho en Notepad → context menu de edición

**Context menus por zona:**

Desktop:
```
┌──────────────────┐
│ Nuevo Terminal   │
│ Nuevo Notepad    │
│ ──────────────── │
│ Cambiar Tema     │
│ Settings         │
│ ──────────────── │
│ Acerca de...     │
└──────────────────┘
```

File Manager:
```
┌──────────────────┐
│ Abrir            │
│ Abrir con...     │
│ ──────────────── │
│ Copiar           │
│ Mover            │
│ Renombrar        │
│ Eliminar         │
│ ──────────────── │
│ Propiedades      │
└──────────────────┘
```

Notepad:
```
┌──────────────────┐
│ Copiar           │
│ Pegar            │
│ Seleccionar todo │
│ ──────────────── │
│ Guardar          │
│ Guardar como...  │
└──────────────────┘
```

**Archivos a modificar:**
- `retrotui/ui/context_menu.py` [NEW]
- `retrotui/core/mouse_router.py` — detectar BUTTON3
- `retrotui/core/app.py` — manejar context menu responses
- `retrotui/apps/filemanager.py` — definir items de context menu
- `retrotui/apps/notepad.py` — definir items de context menu

### 2. Iconos de escritorio móviles

**Estado actual:** Los iconos están en posiciones fijas calculadas en `app.py` método `_draw_desktop_icons`.

**Cambios:**
- Agregar `icon_positions: dict[str, tuple[int, int]]` al state de app
- Cargar/guardar posiciones en `~/.config/retrotui/config.toml` sección `[icons]`
- En `mouse_router.py`: detectar drag de iconos (BUTTON1_PRESSED sobre icono + movimiento)
- Al soltar (BUTTON1_RELEASED): guardar nueva posición
- Snap-to-grid para alineación visual
- Posiciones default si no hay config guardada

### 3. Tests

Crear tests para:
- `test_context_menu.py` — renderizado, click en items, escape, click fuera
- `test_icon_drag.py` — posiciones, snap-to-grid, persistencia
- Verificar que click derecho en zonas correctas abre menu correcto

## Verificación
```bash
python tools/qa.py
git add -A
git commit -m "feat(v0.9.1): context menus (right-click) and movable desktop icons"
```

## IMPORTANTE
- El context menu debe usar el sistema de temas existente (theme_attr)
- Los iconos deben funcionar con TODOS los temas existentes
- NO romper ninguna funcionalidad existente de click izquierdo
- Correr `python tools/qa.py` ANTES de commitear

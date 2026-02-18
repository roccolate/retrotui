# Branch: feature/ux-games (v0.9.2 Games & Classic Apps)
# Agente asignado: Sonnet o GPT-5 mini

## Setup
```bash
git checkout main
git pull
git checkout -b feature/ux-games
```

## Contexto del proyecto
RetroTUI es un entorno de escritorio estilo Windows 3.1 para terminal Linux.
Usa Python + curses. Las apps heredan de `retrotui.ui.window.Window`.
Estructura: `retrotui/apps/` contiene cada app como módulo.
Los tests usan fake curses: `from _support import make_fake_curses`.
QA se corre con `python tools/qa.py`.

Estudiar estos archivos para entender el patrón:
- `retrotui/ui/window.py` — clase base Window
- `retrotui/apps/calculator.py` — app simple, buen ejemplo
- `retrotui/apps/clock.py` — otro ejemplo simple
- `retrotui/core/app.py` — cómo se registran apps e iconos
- `retrotui/constants.py` — constantes de color pairs
- `retrotui/utils.py` — helpers (safe_addstr, draw_box, theme_attr)
- `tests/test_calculator.py` — patrón de testing

## Tareas

### 1. 💣 Minesweeper

Crear `retrotui/apps/minesweeper.py`:

**Clase:** `MinesweeperWindow(Window)`
- Grid configurable (9x9 default, 10 minas)
- Click izquierdo: revelar celda
- Click derecho: poner/quitar flag 🚩
- Timer en title bar
- Detección de victoria/derrota
- Caracteres: `█` oculto, ` ` vacío, `1-8` números, `💣` mina, `🚩` flag
- Colores: números verde/azul/rojo según valor

**Registro:** Agregar icono `💣` en `app.py` y entrada en menú Apps.

### 2. 🃏 Solitaire

Crear `retrotui/apps/solitaire.py`:

**Clase:** `SolitaireWindow(Window)`
- Klondike clásico (7 columnas, deck, 4 foundations)
- Cartas ASCII:
```
┌───┐
│A ♠│
│   │
│ A♠│
└───┘
```
- Click para seleccionar, click para mover
- Double-click para auto-move a foundation
- Palos: ♠ ♥ ♦ ♣ (usando Unicode)
- Colores: rojo para ♥♦, negro para ♠♣
- Detección de victoria con animación

**Registro:** Agregar icono `🃏` en `app.py` y entrada en menú Apps.

### 3. 🐍 Snake

Crear `retrotui/apps/snake.py`:

**Clase:** `SnakeWindow(Window)`
- Grid de juego dentro de la ventana
- Teclas: flechas para dirección
- Score counter en title bar
- Velocidad incremental
- Caracteres: `█` serpiente, `●` comida
- Game over dialog con score

**Registro:** Agregar icono `🐍` en `app.py` y entrada en menú Apps.

### 4. 🔤 Character Map

Crear `retrotui/apps/charmap.py`:

**Clase:** `CharacterMapWindow(Window)`
- Grid de caracteres Unicode organizado por bloques
- Click en carácter → muestra info (codepoint, nombre)
- Botón "Copiar" → copia al clipboard interno de RetroTUI
- Búsqueda por nombre de carácter
- Bloques: ASCII, Latin Extended, Box Drawing, Block Elements, Symbols, Emoji

**Registro:** Agregar icono `🔤` en `app.py` y entrada en menú Apps.

### 5. 📋 Clipboard Viewer

Crear `retrotui/apps/clipboard_viewer.py`:

**Clase:** `ClipboardViewerWindow(Window)`
- Muestra contenido actual del clipboard interno (`retrotui/core/clipboard.py`)
- Auto-refresh al cambiar el clipboard
- Botón "Limpiar"
- Historial de últimos N items copiados

**Registro:** Agregar icono `📋` en `app.py` y entrada en menú Apps.

### 6. 📻 WiFi Manager

Crear `retrotui/apps/wifi_manager.py`:

**Clase:** `WifiManagerWindow(Window)`
- Lista de redes WiFi (output de `nmcli dev wifi list`)
- Mostrar SSID, señal (barras █), seguridad, conectado/no
- Click en red → dialog para password → conectar (`nmcli dev wifi connect`)
- Botón refresh
- Indicador de red actual conectada
- Fallback graceful si `nmcli` no existe: mostrar mensaje "nmcli no disponible"

**Registro:** Agregar icono `📻` en `app.py` y entrada en menú Apps.

### 7. Tests

Crear tests para cada app siguiendo el patrón existente:
- `tests/test_minesweeper.py`
- `tests/test_solitaire.py`
- `tests/test_snake.py`
- `tests/test_charmap.py`
- `tests/test_clipboard_viewer.py`
- `tests/test_wifi_manager.py`

Cada test debe:
- Usar `from _support import make_fake_curses` (NO `from tests._support`)
- Instanciar la ventana con `sys.modules['curses'] = make_fake_curses()`
- Testear: init, draw sin crash, handle_key, handle_click, game logic

## Verificación
```bash
python tools/qa.py
git add -A
git commit -m "feat(v0.9.2): minesweeper, solitaire, snake, character map, clipboard viewer, wifi manager"
```

## IMPORTANTE
- CADA app debe ser autocontenida en su archivo
- Usar `safe_addstr` de `retrotui/utils.py` para escritura segura
- Usar `theme_attr` para colores basados en el tema activo
- NO instalar dependencias externas (solo stdlib + lo que ya existe)
- Para WiFi: usar `subprocess.run` con manejo de errores
- Correr `python tools/qa.py` ANTES de commitear

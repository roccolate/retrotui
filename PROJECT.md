# RetroTUI — Entorno de Escritorio Retro para Consola Linux

## Resumen del Proyecto

**RetroTUI** es un entorno de escritorio basado en texto (TUI) para Linux que emula la
experiencia visual y funcional de DOS/Windows 3.1, diseñado para ejecutarse en una
terminal Linux sin dependencia de X11 ni Wayland.

---

## 1. Soporte de Mouse sin X11

### ¿Es posible? — Sí, con dos mecanismos:

### 1.1 GPM (General Purpose Mouse)

GPM es un daemon que provee soporte de mouse directamente en las consolas virtuales
de Linux (tty1–tty6), sin necesidad de servidor gráfico.

```
┌─────────────────────────────────────────────┐
│  Hardware Mouse                             │
│       ↓                                     │
│  /dev/input/mice (kernel driver)            │
│       ↓                                     │
│  gpm daemon (userspace)                     │
│       ↓                                     │
│  /dev/gpmctl (socket)                       │
│       ↓                                     │
│  ncurses/curses (librería)                  │
│       ↓                                     │
│  RetroTUI (aplicación)                      │
└─────────────────────────────────────────────┘
```

**Instalación en Ubuntu minimal:**
```bash
sudo apt install gpm
sudo systemctl enable gpm
sudo systemctl start gpm
```

**Protocolos soportados:** PS/2, USB (auto-detectado), serial.

### 1.2 Protocolo xterm mouse tracking

Cualquier emulador de terminal moderno (xterm, gnome-terminal, tmux, screen, SSH
clients) soporta secuencias de escape para reportar eventos de mouse:

- **X10 mode** — solo clicks
- **Normal tracking (1000)** — clicks + release
- **Button-event tracking (1002)** — clicks + drag
- **Any-event tracking (1003)** — todo movimiento
- **SGR extended (1006)** — coordenadas > 223 columnas

Python `curses` y `ncurses` en C abstraen esto completamente vía `mousemask()`.

### 1.3 Estrategia híbrida de RetroTUI

```
if (running in TTY console):
    use GPM via /dev/gpmctl → ncurses
elif (running in terminal emulator):
    use xterm mouse protocol → ncurses
```

Ambos caminos convergen en la misma API de `curses.getmouse()`, por lo que el
código de la aplicación no necesita distinguirlos.

---

## 2. Arquitectura del Sistema

```
┌──────────────────────────────────────────────────────────┐
│                    RetroTUI Shell                         │
├──────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐ │
│  │ Desktop  │  │ Window   │  │ Widget Toolkit         │ │
│  │ Manager  │  │ Manager  │  │ (Button, Menu, Input,  │ │
│  │          │  │ (z-order │  │  Dialog, FileList,     │ │
│  │          │  │  focus)  │  │  ScrollBar, Icon)      │ │
│  └──────────┘  └──────────┘  └────────────────────────┘ │
├──────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐│
│  │           Event Loop (mouse + keyboard)              ││
│  └──────────────────────────────────────────────────────┘│
├──────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐│
│  │         Python curses / ncurses abstraction          ││
│  └──────────────────────────────────────────────────────┘│
├──────────────────────────────────────────────────────────┤
│         Linux Console (TTY) + GPM  /  Terminal          │
└──────────────────────────────────────────────────────────┘
```

### Componentes principales:

| Componente         | Responsabilidad                                         |
|--------------------|---------------------------------------------------------|
| `EventLoop`        | Captura teclado y mouse, despacha eventos               |
| `WindowManager`    | Z-order, foco, mover/redimensionar ventanas             |
| `DesktopManager`   | Fondo del escritorio, iconos, barra de tareas           |
| `WidgetToolkit`    | Botones, menús, inputs, listas, scrollbars              |
| `ThemeEngine`      | Colores y caracteres de borde (DOS vs Win3.1)           |
| `AppLauncher`      | Ejecutar apps internas y programas externos             |

---

## 3. Requisitos del Sistema

### Mínimos:
- Ubuntu Server / minimal (sin GUI)
- Python 3.8+
- ncurses (incluido en Python stdlib como `curses`)
- Terminal con soporte de al menos 80x25 caracteres
- GPM (para mouse en TTY) o emulador de terminal con xterm mouse

### Recomendados:
- Terminal con soporte Unicode (UTF-8) para bordes decorativos
- 256 colores o truecolor
- Resolución de terminal 120x40 o superior

### Sin dependencias externas:
- **NO** X11 / Xorg
- **NO** Wayland
- **NO** framebuffer gráfico
- Solo Python stdlib (`curses`, `os`, `sys`, `time`, `locale`, `termios`)

---

## 4. Características del Prototipo (v0.1)

- [x] Escritorio con patrón de fondo estilo Windows 3.1
- [x] Barra de menú superior (≡ Menu | Clock)
- [x] Ventanas con bordes dobles Unicode (╔═╗║╚═╝)
- [x] Barra de título con botón de cerrar [×]
- [x] Soporte de mouse: click para seleccionar, arrastrar ventanas
- [x] Diálogos modales (About, Exit confirmation)
- [x] Menú desplegable con opciones
- [x] Iconos de escritorio clickeables
- [x] Reloj en tiempo real
- [x] Navegación completa por teclado (Tab, Enter, Escape, Alt+F4)

## 4.1 Características de v0.2 — File Manager

- [x] File Manager con navegación de directorios
- [x] Clase FileManagerWindow con estado de directorio
- [x] Navegación: click en carpeta para entrar, ".." para subir
- [x] Selección con highlight (blanco sobre azul, estilo Win3.1)
- [x] Teclado: ↑↓ selección, Enter abrir, Backspace padre, PgUp/PgDn, Home/End
- [x] Toggle archivos ocultos (tecla H)
- [x] Visor de archivos de texto (Notepad read-only)
- [x] Detección de archivos binarios
- [x] Auto-scroll para mantener selección visible
- [x] Re-selección del directorio previo al navegar hacia arriba
- [x] Sin límite artificial de entradas (dirs + archivos)
- [x] Delegación de eventos mouse/teclado por ventana (handle_click/handle_key)

## 4.2 Características de v0.3 — Editor de Texto, Resize, Maximize/Minimize

- [x] Editor de texto (NotepadWindow) con cursor y edición
- [x] Word wrap toggle (Ctrl+W) con cache de líneas envueltas
- [x] Abrir archivos desde File Manager en el editor (reemplaza visor read-only)
- [x] Resize de ventanas: drag bordes inferior/derecho/esquinas
- [x] Maximize/Minimize: botones [─][□][×] en title bar
- [x] Taskbar para ventanas minimizadas (fila h-2)
- [x] Doble-click en título = toggle maximize
- [x] Refactorización: Window.draw() → draw_frame() + draw_body()
- [x] Tab cycling salta ventanas minimizadas
- [x] Status bar muestra ventanas visibles/total
- [x] Notepad en menú File

## 4.3 Características de v0.3.1 — Barras de Menú por Ventana

- [x] Clase WindowMenu: dropdown menu system per-window
- [x] FileManager: menú File (Open, Parent Dir, Close) + View (Hidden Files, Refresh)
- [x] Notepad: menú File (New, Close) + View (Word Wrap)
- [x] Indicador ≡ en title bar de ventanas con menú
- [x] F10 abre menú de ventana activa (prioridad sobre global)
- [x] Escape cierra menú de ventana primero, luego global
- [x] Hover tracking y click-outside-close para dropdowns
- [x] body_rect() auto-ajuste con window_menu

## 4.4 Características de v0.3.2 — ASCII Video Player

- [x] Reproductor ASCII de video usando mplayer + aalib (-vo aa)
- [x] Icono "ASCII Vid" en escritorio y opción "ASCII Video" en menú File
- [x] Detección automática de videos desde File Manager (.mp4, .mkv, .webm, etc.)
- [x] Manejo de errores: mplayer no instalado, error de ejecución
- [x] Restauración correcta de curses después de reproducción

## 4.5 Características de v0.3.3 — Modularización y Hardening

- [x] Refactor del monolito a paquete Python (`retrotui/core`, `retrotui/ui`, `retrotui/apps`)
- [x] Contrato tipado de acciones (`ActionType` / `ActionResult`) en el dispatcher principal
- [x] Unificación de menús (`Menu` + `WindowMenu`) en `MenuBar`
- [x] Descomposición de `handle_mouse()` y `handle_key()` en helpers de routing
- [x] Correcciones de guardado Save/Save As y errores de `InputDialog`
- [x] Bootstrap de packaging con `pyproject.toml` y entrypoint `retrotui`
- [x] Tests smoke iniciales para rutas no-curses (`tests/`)

## 4.6 Características de v0.3.4 — Release de Mantenimiento

- [x] Bump de versión global a `0.3.4` (runtime + packaging)
- [x] Sincronización de versión visible en UI (welcome/status/about)
- [x] Documentación y preview alineados con el estado actual del proyecto

### Roadmap futuro:
- [x] File Manager con navegación de directorios
- [x] Editor de texto integrado
- [x] Barras de menú por ventana
- [x] ASCII Video Player
- [x] Modularización base del proyecto
- [ ] Terminal embebida
- [ ] Temas configurables (CGA, EGA, VGA, Win3.1, Win95)
- [ ] Task switcher (Alt+Tab)
- [ ] Configuración persistente (`~/.config/retrotui/config.toml`)

---

## 5. Paleta de Colores

### Tema Windows 3.1:
```
Escritorio:       Teal (fondo) con patrón
Barra de título:  Azul marino (activa) / Gris (inactiva)
Texto título:     Blanco
Fondo ventana:    Blanco
Texto:            Negro
Menú:             Blanco con texto negro
Selección menú:   Azul marino con texto blanco
Botones:          Gris claro con borde 3D
Diálogos:         Gris claro
```

---

## 6. Controles de Teclado

| Tecla         | Acción                          |
|---------------|---------------------------------|
| Tab           | Ciclar foco entre ventanas      |
| Escape        | Cerrar menú / diálogo           |
| Enter         | Activar botón / opción          |
| Ctrl+Q        | Salir del entorno               |
| Arrow keys    | Navegar menús                   |
| F10           | Activar barra de menú           |

### Controles del File Manager (v0.2):

| Tecla         | Acción                          |
|---------------|---------------------------------|
| ↑ / ↓         | Mover selección                 |
| Enter         | Abrir directorio / archivo      |
| Backspace     | Ir al directorio padre          |
| PgUp / PgDn   | Mover selección una página      |
| Home / End    | Ir al inicio / final            |
| H             | Toggle archivos ocultos         |
| Click         | Seleccionar y abrir entrada     |

---

## 7. Ejecución

```bash
# Instalar GPM (solo necesario en TTY, no en emulador de terminal)
sudo apt install gpm
sudo systemctl start gpm

# Ejecutar
cd retro-tui
python3 -m retrotui
```

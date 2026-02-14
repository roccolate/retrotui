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
- Solo Python stdlib (`curses`, `os`, `subprocess`, `json`)

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

### Roadmap futuro:
- [x] File Manager con navegación de directorios
- [ ] Editor de texto integrado
- [ ] Terminal embebida
- [ ] Temas configurables (CGA, EGA, VGA, Win3.1, Win95)
- [ ] Task switcher (Alt+Tab)
- [ ] Configuración persistente (~/.retrotui/config.json)

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
| Alt+F4        | Cerrar ventana activa           |
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
python3 src/retrotui.py
```

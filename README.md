# RetroTUI

[![CI](https://github.com/roccolate/RetroTUI/actions/workflows/ci.yml/badge.svg)](https://github.com/roccolate/RetroTUI/actions/workflows/ci.yml)
[![Release](https://github.com/roccolate/RetroTUI/actions/workflows/release.yml/badge.svg)](https://github.com/roccolate/RetroTUI/actions/workflows/release.yml)
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/I2I1WKMLQ)

**Un entorno de escritorio retro para tu terminal.** *(English below)*

```text
╔══════════════════════════════════════════════════════════════╗
║ ≡ File   Edit   Help                            12:30:45     ║
╠══════════════════════════════════════════════════════════════╣
║░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
║░░ 📁 ░░░░╔═══ File Manager ═══════════[─][□][×]╗░░░░░░░░░░░░░║
║░ Files ░░║ 📂 /home/user                       ║░░░░░░░░░░░░░║
║░░░░░░░░░░║ ──────────────────────────           ║░░░░░░░░░░░░░║
║░░ 📝 ░░░░║  📁 Documents/                      ║░░░░░░░░░░░░░║
║░Notepad░░║  📁 Downloads/                      ║░░░░░░░░░░░░░║
║░░░░░░░░░░║  📄 readme.txt            2.4K      ║░░░░░░░░░░░░░║
║░░ 💻 ░░░░║  📄 config.json           512B      ║░░░░░░░░░░░░░║
║░Terminal░╚══════════════════════════════════════╝░░░░░░░░░░░░░║
║░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
║ RetroTUI v0.9.3 │ Windows: 1/1 │ Mouse: Enabled │ Ctrl+Q: Exit║
╚══════════════════════════════════════════════════════════════╝
```

## Descripcion

RetroTUI es un entorno de escritorio estilo Windows 3.1 que corre completamente en la terminal. Sin X11, sin Wayland, solo Python y `curses`. Funciona en Linux, WSL y Windows nativo.

### Caracteristicas

*   **Gestor de Ventanas**: Mover, redimensionar, maximizar, minimizar, arrastrar y soltar.
*   **Soporte de Mouse**: Funciona en consola TTY (via `gpm`) y emuladores de terminal (protocolo xterm).
*   **Terminal Embebida**: Shell PTY completo dentro de una ventana (POSIX y Windows via `pywinpty`).
*   **Perfil base estable**: Explorador de Archivos, Bloc de Notas y Terminal son las unicas apps visibles por defecto.
*   **Apps secundarias instaladas pero deshabilitadas por defecto**: Calculadora, Visor Hex, Visor Markdown, Monitor de Procesos, Monitor de Sistema, Visor de Logs, Clipboard Viewer, Settings, Panel de Control, Papelera, Editor de Iconos y Editor de Menus.
*   **Juegos y plugins opcionales**: Buscaminas, Solitario, Snake, Tetris, RetroNet Explorer, Mapa de Caracteres, Reloj/Calendario, Visor de Imagenes y WiFi Manager quedan fuera del perfil base.
*   **Temas**: Windows 3.1, DOS, Windows 95, Hacker, Amiga.
*   **Sistema de Plugins**: Plugins bundled, de ejemplo/desarrollo y propios desde directorios configurables; se mantienen deshabilitados en el perfil base hasta que la configuracion los habilite.
*   **Sin dependencias en Linux**: Solo Python 3.10+ estandar. En Windows requiere `pywinpty` y `windows-curses`.

## Instalacion

```bash
git clone https://github.com/roccolate/RetroTUI.git
cd RetroTUI
python -m retrotui
```

### Requisitos

| Plataforma | Requisitos |
| :--- | :--- |
| **Linux/WSL** | Python 3.10+, terminal 80x24 minimo, UTF-8 recomendado |
| **Windows** | Python 3.10+, `pip install pywinpty windows-curses` |

Para Python 3.14+ en Windows: [windows-curses fork](https://github.com/roccolate/windows-curses).

## Controles

| Tecla | Accion |
| :--- | :--- |
| `Tab` | Cambiar ventana activa |
| `F10` | Abrir menu |
| `Ctrl+Q` | Salir |
| `Alt+Tab` | Ciclar ventanas |
| Click derecho | Menu contextual |

### Apps
*   **File Manager**: `Enter` abrir, `F5` Copiar, `F4`/`F6` Mover, `F2` Renombrar, `F7` Nueva carpeta, `F8` Nuevo archivo, `U` Deshacer borrado, `D` doble panel.
*   **Notepad**: `Ctrl+S` Guardar, `Ctrl+O` Abrir, `Ctrl+W` Ajuste de linea.
*   **Terminal**: `Ctrl+C` Copiar/Interrumpir, `Ctrl+V` Pegar, `F6` Interrumpir, `F7` Terminar.

## Documentacion
*   [ARCHITECTURE.md](ARCHITECTURE.md) - Arquitectura del sistema.
*   [ROADMAP.md](ROADMAP.md) - Estado del proyecto y plan de versiones.
*   [CONTRIBUTING.md](CONTRIBUTING.md) - Guia de contribucion.
*   [CHANGELOG.md](CHANGELOG.md) - Historial de cambios.
*   [docs/plugin-guide.md](docs/plugin-guide.md) - Guia para crear plugins.
*   [tools/TESTING.md](tools/TESTING.md) - Checklist de pruebas manuales.
*   [IMPROVEMENTS.md](IMPROVEMENTS.md) - Auditoria tecnica y backlog de mejoras.

---

# RetroTUI (English)

**A retro desktop environment for your terminal.**

## Overview

RetroTUI is a Windows 3.1-style desktop environment that runs entirely in the terminal. No X11, no Wayland, just Python and `curses`. Works on Linux, WSL, and native Windows.

### Features

*   **Window Manager**: Move, resize, maximize, minimize, drag and drop.
*   **Mouse Support**: Works in TTY consoles (via `gpm`) and terminal emulators (xterm protocol).
*   **Embedded Terminal**: Full PTY shell inside a window (POSIX and Windows via `pywinpty`).
*   **Stable base profile**: File Manager, Notepad, and Terminal are the only apps visible by default.
*   **Secondary apps installed but disabled by default**: Calculator, Hex Viewer, Markdown Viewer, Process Manager, System Monitor, Log Viewer, Clipboard Viewer, Settings, Control Panel, Trash, Icon Editor, and Menu Editor.
*   **Optional games and plugins**: Minesweeper, Solitaire, Snake, Tetris, RetroNet Explorer, Character Map, Clock/Calendar, Image Viewer, and WiFi Manager stay outside the base profile.
*   **Themes**: Windows 3.1, DOS, Windows 95, Hacker, Amiga.
*   **Plugin System**: Bundled, development/example, and custom plugins from configurable directories; they stay disabled in the base profile until enabled by config.
*   **No dependencies on Linux**: Just standard Python 3.10+. Windows requires `pywinpty` and `windows-curses`.

## Installation

```bash
git clone https://github.com/roccolate/RetroTUI.git
cd RetroTUI
python -m retrotui
```

### Requirements

| Platform | Requirements |
| :--- | :--- |
| **Linux/WSL** | Python 3.10+, terminal 80x24 minimum, UTF-8 recommended |
| **Windows** | Python 3.10+, `pip install pywinpty windows-curses` |

For Python 3.14+ on Windows: [windows-curses fork](https://github.com/roccolate/windows-curses).

## Controls

| Key | Action |
| :--- | :--- |
| `Tab` | Switch window focus |
| `F10` | Toggle menu bar |
| `Ctrl+Q` | Exit |
| `Alt+Tab` | Cycle windows |
| Right click | Context menu |

### Apps
*   **File Manager**: `Enter` to open, `F5` Copy, `F4`/`F6` Move, `F2` Rename, `F7` New folder, `F8` New file, `U` Undo delete, `D` dual-pane.
*   **Notepad**: `Ctrl+S` Save, `Ctrl+O` Open, `Ctrl+W` Toggle word wrap.
*   **Terminal**: `Ctrl+C` Copy/Interrupt, `Ctrl+V` Paste, `F6` Interrupt, `F7` Terminate.

## Documentation
*   [ARCHITECTURE.md](ARCHITECTURE.md) - System design and internals.
*   [ROADMAP.md](ROADMAP.md) - Project status and release plan.
*   [CONTRIBUTING.md](CONTRIBUTING.md) - Development guide.
*   [CHANGELOG.md](CHANGELOG.md) - Release notes.
*   [docs/plugin-guide.md](docs/plugin-guide.md) - Plugin development guide.
*   [tools/TESTING.md](tools/TESTING.md) - Manual testing checklist.
*   [IMPROVEMENTS.md](IMPROVEMENTS.md) - Technical audit and improvement backlog.

---

## License
MIT

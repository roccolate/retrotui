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
*   **Apps principales**: Explorador de Archivos (doble panel), Bloc de Notas, Terminal, Calculadora, Visor Hex, Visor Markdown, Monitor de Procesos, Monitor de Sistema, Visor de Logs, Clipboard Viewer, Panel de Control, Papelera.
*   **Juegos**: Buscaminas, Solitario, Snake, Tetris.
*   **Plugins**: RetroNet Explorer (navegador web de texto), Mapa de Caracteres, Reloj/Calendario, Visor de Imagenes, WiFi Manager.
*   **Temas**: Windows 3.1, DOS, Windows 95, Hacker, Amiga.
*   **Sistema de Plugins**: Carga automatica de plugins propios desde directorio configurable. Campo `category` en `plugin.toml` para separar juegos de herramientas.
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
*   **File Manager**: `Enter` abrir, `F5` Copiar, `F4` Mover, `F2` Renombrar, `Del` Borrar, `D` doble panel.
*   **Notepad**: `Ctrl+S` Guardar, `Ctrl+O` Abrir, `Ctrl+W` Ajuste de linea.
*   **Terminal**: `Ctrl+C` Copiar/Interrumpir, `Ctrl+V` Pegar, `F6` Interrumpir, `F7` Terminar.

## Documentacion
*   [ARCHITECTURE.md](ARCHITECTURE.md) - Arquitectura del sistema.
*   [CONTRIBUTING.md](CONTRIBUTING.md) - Guia de contribucion.
*   [CHANGELOG.md](CHANGELOG.md) - Historial de cambios.

---

# RetroTUI (English)

**A retro desktop environment for your terminal.**

## Overview

RetroTUI is a Windows 3.1-style desktop environment that runs entirely in the terminal. No X11, no Wayland, just Python and `curses`. Works on Linux, WSL, and native Windows.

### Features

*   **Window Manager**: Move, resize, maximize, minimize, drag and drop.
*   **Mouse Support**: Works in TTY consoles (via `gpm`) and terminal emulators (xterm protocol).
*   **Embedded Terminal**: Full PTY shell inside a window (POSIX and Windows via `pywinpty`).
*   **Core Apps**: File Manager (dual-pane), Notepad, Terminal, Calculator, Hex Viewer, Markdown Viewer, Process Manager, System Monitor, Log Viewer, Clipboard Viewer, Control Panel, Trash.
*   **Games**: Minesweeper, Solitaire, Snake, Tetris.
*   **Plugins**: RetroNet Explorer (text web browser), Character Map, Clock/Calendar, Image Viewer, WiFi Manager.
*   **Themes**: Windows 3.1, DOS, Windows 95, Hacker, Amiga.
*   **Plugin System**: Auto-loads custom plugins from a configurable directory. Use `category` field in `plugin.toml` to separate games from tools.
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
*   **File Manager**: `Enter` to open, `F5` Copy, `F4` Move, `F2` Rename, `Del` Delete, `D` dual-pane.
*   **Notepad**: `Ctrl+S` Save, `Ctrl+O` Open, `Ctrl+W` Toggle word wrap.
*   **Terminal**: `Ctrl+C` Copy/Interrupt, `Ctrl+V` Paste, `F6` Interrupt, `F7` Terminate.

## Documentation
*   [ARCHITECTURE.md](ARCHITECTURE.md) - System design and internals.
*   [CONTRIBUTING.md](CONTRIBUTING.md) - Development guide.
*   [CHANGELOG.md](CHANGELOG.md) - Release notes.

---

## License
MIT

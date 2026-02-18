# RetroTUI 🖥️

[![CI](https://github.com/roccolate/RetroTUI/actions/workflows/ci.yml/badge.svg)](https://github.com/roccolate/RetroTUI/actions/workflows/ci.yml)
[![Release](https://github.com/roccolate/RetroTUI/actions/workflows/release.yml/badge.svg)](https://github.com/roccolate/RetroTUI/actions/workflows/release.yml)
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/I2I1WKMLQ)

**Un entorno de escritorio estilo Windows 3.1 para tu terminal.**

*(English below)*

## Descripción General

RetroTUI trae la nostalgia de los escritorios clásicos a tu terminal Linux. Funciona sin interfaz gráfica (X11/Wayland), usando solo texto y `curses`.

```text
╔══════════════════════════════════════════════════════════════╗
║ ≡ File   Edit   Help                            12:30:45   ║
╠══════════════════════════════════════════════════════════════╣
║░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
║░░ 📁 ░░░░╔═══ File Manager ═══════════[─][□][×]╗░░░░░░░░░░║
║░ Files ░░║ 📂 /home/user                       ║░░░░░░░░░░║
║░░░░░░░░░░║ ──────────────────────────           ║░░░░░░░░░░║
║░░ 📝 ░░░░║  📁 Documents/                      ║░░░░░░░░░░║
║░Notepad░░║  📁 Downloads/                      ║░░░░░░░░░░║
║░░░░░░░░░░║  📄 readme.txt            2.4K      ║░░░░░░░░░░║
║░░ 💻 ░░░░║  📄 config.json           512B      ║░░░░░░░░░░║
║░Terminal░╚══════════════════════════════════════╝░░░░░░░░░░║
║░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
║ RetroTUI v0.9.1 │ Windows: 1/1 │ Mouse: Enabled │ Ctrl+Q: Exit║
╚══════════════════════════════════════════════════════════════╝
```

### Características
*   **Gestor de Ventanas**: Mover, redimensionar, maximizar, minimizar.
*   **Soporte de Mouse**: Funciona en consola TTY (vía `gpm`) y emuladores (protocolo xterm).
*   **Terminal Embebida**: Ejecuta tu shell dentro de una ventana.
*   **Apps Incluidas**: Explorador de Archivos, Bloc de Notas, Calculadora, Monitor de Procesos, Visor de Logs.
*   **Temas**: Windows 3.1, DOS, Windows 95, Hacker, Amiga.
*   **Sin Dependencias**: Solo requiere Python 3.9 estándar.

## Instalación

```bash
git clone https://github.com/roccolate/RetroTUI.git
cd RetroTUI
python3 -m retrotui
```

### Requisitos
*   **Linux/WSL** (Windows nativo no soportado por falta de `curses` completo).
*   **Python 3.9+**.
*   **Tamaño de terminal**: Al menos 80x24.
*   **Locale UTF-8** (Recomendado).

## Controles Principales

### Globales
| Tecla | Acción |
| :--- | :--- |
| `Tab` | Cambiar ventana activa |
| `F10` | Abrir menú |
| `Ctrl+Q` | Salir |
| `Alt+Tab` | Ciclar ventanas |

### Apps
*   **File Manager**: `Enter` abrir, `F5` Copiar, `F6` Mover, `F8` Borrar.
*   **Notepad**: `Ctrl+S` Guardar, `Ctrl+W` Ajuste de línea.
*   **Terminal**: `Ctrl+Shift+C` Copiar, `Ctrl+Shift+V` Pegar.

## Documentación
*   [ARCHITECTURE.md](ARCHITECTURE.md) - Arquitectura del sistema.
*   [CONTRIBUTING.md](CONTRIBUTING.md) - Guía de contribución.
*   [CHANGELOG.md](CHANGELOG.md) - Historial de cambios.

---

# RetroTUI (English)

**A Windows 3.1-style desktop environment for your terminal.**

## Overview

RetroTUI brings the nostalgic experience of a classic desktop to your Linux/WSL terminal. No X11, no Wayland, just pure Python and `curses`.

### Key Features
*   **Window Management**: Move, resize, maximize, minimize.
*   **Mouse Support**: Works in TTY (via `gpm`) and terminal emulators (xterm protocol).
*   **Embedded Terminal**: Run your shell inside a window.
*   **Apps**: File Manager, Notepad, Calculator, Process Manager, Log Viewer, Hex Editor.
*   **Themes**: Switch between Win 3.1, DOS, Win 95, Hacker, and Amiga styles.
*   **No Dependencies**: Runs on standard Python 3.9+ library.

## Installation

```bash
git clone https://github.com/roccolate/RetroTUI.git
cd RetroTUI
python3 -m retrotui
```

### Requirements
*   **Linux/WSL** (Windows native not supported due to missing `curses`).
*   **Python 3.9+**.
*   **Terminal size**: At least 80x24.
*   **UTF-8 Locale** (Recommended).

## Controls

### Global
| Key | Action |
| :--- | :--- |
| `Tab` | Switch Window Focus |
| `F10` | Toggle Menu Bar |
| `Ctrl+Q` | Exit RetroTUI |
| `Alt+Tab` | Cycle Windows |

### Apps
*   **File Manager**: `Enter` to open, `F5` Copy, `F6` Move, `F8` Delete.
*   **Notepad**: `Ctrl+S` Save, `Ctrl+W` Toggle Word Wrap.
*   **Terminal**: `Ctrl+Shift+C` Copy, `Ctrl+Shift+V` Paste.

## Documentation
*   [ARCHITECTURE.md](ARCHITECTURE.md) - System design and internals.
*   [CONTRIBUTING.md](CONTRIBUTING.md) - Development guide.
*   [CHANGELOG.md](CHANGELOG.md) - Release notes.

---

## Licencia / License
MIT

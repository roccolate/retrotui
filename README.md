# RetroTUI

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/roccolate/retrotui/actions/workflows/ci.yml/badge.svg)](https://github.com/roccolate/retrotui/actions/workflows/ci.yml)
[![Release](https://github.com/roccolate/retrotui/actions/workflows/release.yml/badge.svg)](https://github.com/roccolate/retrotui/actions/workflows/release.yml)
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/I2I1WKMLQ)

**A retro desktop environment for your terminal.**

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
║ RetroTUI v0.9.5 │ Windows: 1/1 │ Mouse: Enabled │ Ctrl+Q: Exit║
╚══════════════════════════════════════════════════════════════╝
```

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
*   **No dependencies on Linux**: Just standard Python 3.10+. Windows requires `pywinpty` (Python 3.13 or earlier; on 3.14+ curses is native).

## Installation

```bash
pip install retrotui
retrotui
```

The `retrotui` command is installed as a console script by `pyproject.toml` and works the same as `python -m retrotui`.

### From source

```bash
git clone https://github.com/roccolate/retrotui.git
cd retrotui
python -m pip install -e .
retrotui
```

### Requirements

| Platform | Requirements |
| :--- | :--- |
| **Linux/WSL** | Python 3.10+, terminal 80x24 minimum, UTF-8 recommended |
| **Windows** | Python 3.10+. On 3.13 or earlier: `pip install pywinpty`. On 3.14+ no extra dependencies required (curses is native and the PTY uses ConPTY). |

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
*   **Terminal**: `Ctrl+C` Copy/Interrupt, `Ctrl+V` Paste, `F6` Interrupt, `F7` Terminate. Mouse events forward to the child program when it has enabled DEC mouse reporting (`?1006h` / `?1003h` / etc.) — full-screen TUI apps (vim, htop) just work.
*   **RetroNet** (bundled browser plugin): `Ctrl+T` new tab, `Ctrl+W` close tab, `Ctrl+I` next tab, `Shift+Tab` previous tab. `Ctrl+B` bookmarks list, `Ctrl+D` add bookmark, `Ctrl+U` view source, `/` in-page search. Bookmarks persist to `~/.config/retrotui/bookmarks.toml`.

## Documentation
*   [ARCHITECTURE.md](ARCHITECTURE.md) - System design and internals.
*   [ROADMAP.md](ROADMAP.md) - Project status and release plan.
*   [CONTRIBUTING.md](CONTRIBUTING.md) - Development guide.
*   [CHANGELOG.md](CHANGELOG.md) - Release notes.
*   [docs/plugin-guide.md](docs/plugin-guide.md) - Plugin development guide.
*   [tools/TESTING.md](tools/TESTING.md) - Manual testing checklist.
*   [docs/IMPROVEMENTS.md](docs/IMPROVEMENTS.md) - Technical audit and improvement backlog.

---

## License
MIT

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
║░░┌──┐░░░░╔═══ File Manager ═══════════[─][□][×]╗░░░░░░░░░░░░░║
║░░│FL│░░░░║ 📂 /home/user                       ║░░░░░░░░░░░░░║
║░░└──┘░░░░║ ──────────────────────────           ║░░░░░░░░░░░░░║
║░ Files ░░║  📁 Documents/                      ║░░░░░░░░░░░░░║
║░░╔══╗░░░░║  📁 Downloads/                      ║░░░░░░░░░░░░░║
║░░║NP║░░░░║  📄 readme.txt            2.4K      ║░░░░░░░░░░░░░║
║░░╚══╝░░░░║  📄 config.json           512B      ║░░░░░░░░░░░░░║
║░Notepad░░╚══════════════════════════════════════╝░░░░░░░░░░░░░║
║░░┌──┐░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
║░░│>_│░░░░ RetroTUI v0.9.5 │ Mouse: Enabled │ Ctrl+Q: Exit   ║
║░░└──┘░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
╚══════════════════════════════════════════════════════════════╝
```

## Overview

RetroTUI is a Windows 3.1-style desktop environment that runs entirely in the terminal. No X11, no Wayland, just Python and `curses`. Linux, WSL and native Windows are target platforms; verified support and known differences are tracked in the cross-terminal test matrix.

### Features

*   **Window Manager**: Move, resize, maximize, minimize, drag and drop.
*   **Mouse Support**: Implementations for TTY consoles (via `gpm`) and terminal emulators (xterm/SGR protocol); behavior varies by backend and is being certified in the TTY matrix.
*   **Embedded Terminal**: PTY-backed shell window for POSIX and Windows (`pywinpty`/ConPTY). ANSI coverage and full-screen TUI compatibility are active certification areas, not blanket guarantees.
*   **Stable base profile**: File Manager, Notepad, and Terminal are the only apps visible by default.
*   **Desktop icon styles**: Classic clean letter boxes, Win31 Art 3-line per-app artwork, and Retro 0.1 compact icons for very small screens.
*   **Secondary apps installed but disabled by default**: Calculator, Hex Viewer, Markdown Viewer, Process Manager, System Monitor, Log Viewer, Clipboard Viewer, Settings, Control Panel, Trash, Icon Editor, and Menu Editor.
*   **Optional games and plugins**: Minesweeper, Solitaire, Snake, Tetris, RetroNet Explorer, Character Map, Clock/Calendar, Image Viewer, and WiFi Manager stay outside the base profile.
*   **Themes**: Windows 3.1, DOS, Windows 95, Hacker, Amiga.
*   **Plugin System**: Bundled, development/example, and custom plugins from configurable directories; they stay disabled in the base profile until enabled by config.
*   **Base Linux runtime**: Standard Python 3.10+ only. Optional media, clipboard and networking features can use external system commands. Windows terminal support may require `pywinpty` depending on Python/runtime capabilities.

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
| **Windows** | Python 3.10+. On 3.13 or earlier: `pip install pywinpty`. On 3.14+ curses may be available natively; validate PTY behavior against the current TTY matrix. |

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
*   **Terminal**: `Ctrl+C` Copy/Interrupt, `Ctrl+V` Paste, `F6` Interrupt, `F7` Terminate. DEC mouse-reporting pass-through is implemented, but global shortcuts, ANSI coverage and real-world compatibility with `vim`, `htop`, `mc`, `less` and similar apps must be checked against [docs/TTY_TEST_MATRIX.md](docs/TTY_TEST_MATRIX.md).
*   **RetroNet** (bundled browser plugin): `Ctrl+T` new tab, `Ctrl+W` close tab, `Ctrl+I` next tab, `Shift+Tab` previous tab. `Ctrl+B` bookmarks list, `Ctrl+D` add bookmark, `Ctrl+U` view source, `/` in-page search. Bookmarks persist to `~/.config/retrotui/bookmarks.toml`.

## Documentation
*   [ARCHITECTURE.md](ARCHITECTURE.md) - System design and internals.
*   [ROADMAP.md](ROADMAP.md) - Project status and release plan.
*   [docs/TECHNICAL_AUDIT_2026-07.md](docs/TECHNICAL_AUDIT_2026-07.md) - Code-first audit, confirmed failures and P0-P2 stabilization gates.
*   [docs/CORE_AUDIT_2026-07.md](docs/CORE_AUDIT_2026-07.md) - Deep analysis of `retrotui/core/` contracts and lifecycle.
*   [docs/CODEX_NEXT_STEPS.md](docs/CODEX_NEXT_STEPS.md) - Operational handoff for the active v0.9.6 milestone.
*   [docs/ICON_STYLES.md](docs/ICON_STYLES.md) - Supported desktop icon styles and legacy aliases.
*   [CHANGELOG.md](CHANGELOG.md) - Release notes and unreleased hardening notes.
*   [CONTRIBUTING.md](CONTRIBUTING.md) - Development guide.
*   [tools/TESTING.md](tools/TESTING.md) - Full manual testing checklist.
*   [docs/TTY_TEST_MATRIX.md](docs/TTY_TEST_MATRIX.md) - Cross-terminal/TTY certification matrix and result log.
*   [docs/IMPROVEMENTS.md](docs/IMPROVEMENTS.md) - Technical audit history and improvement backlog.
*   [docs/RELEASE.md](docs/RELEASE.md) - Release process and version gates.
*   [docs/plugin-guide.md](docs/plugin-guide.md) - Plugin development guide.
*   [docs/SHORTCUT_POLICY_PLAN.md](docs/SHORTCUT_POLICY_PLAN.md) - Keyboard shortcut policy and cleanup plan.

---

## License
MIT

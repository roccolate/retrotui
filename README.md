# RetroTUI

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/roccolate/retrotui/actions/workflows/ci.yml/badge.svg)](https://github.com/roccolate/retrotui/actions/workflows/ci.yml)
[![Release](https://github.com/roccolate/retrotui/actions/workflows/release.yml/badge.svg)](https://github.com/roccolate/retrotui/actions/workflows/release.yml)
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/I2I1WKMLQ)

**A retro desktop environment that runs entirely inside your terminal.**

```text
╔══════════════════════════════════════════════════════════════╗
║░░┌──┐░░░░╔═══ File Manager ═══════════[─][□][×]╗░░░░░░░░░║
║░░│FL│░░░░║ 📂 /home/user                       ║░░░░░░░░░║
║░░└──┘░░░░║ ──────────────────────────           ║░░░░░░░░░║
║░ Files ░░║  📁 Documents/                      ║░░░░░░░░░║
║░░╔══╗░░░░║  📁 Downloads/                      ║░░░░░░░░░║
║░░║NP║░░░░║  📄 readme.txt            2.4K      ║░░░░░░░░░║
║░░╚══╝░░░░╚══════════════════════════════════════╝░░░░░░░░░║
║░Notepad░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
║░░┌──┐░░░░ RetroTUI v0.9.x │ Mouse │ PTY │ Plugins         ║
║░░│>_│░░░░ Ctrl+Q: Exit                                     ║
║░░└──┘░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
╠══════════════════════════════════════════════════════════════╣
║ [ Inicio ] File Edit Help [ File Manager ]       12:30:45  ║
╚══════════════════════════════════════════════════════════════╝
```

## Project status

| Item | Current state |
|---|---|
| Published package | `0.9.5` |
| Primary branch | `main` |
| Automated stabilization | ✅ Pre-v0.9.6 P0/P1 gate completed |
| Active milestone | `v0.9.6 — cross-terminal certification` |
| v0.9.6 release | Not published yet |
| v1.0 status | Planned after v0.9.7–v0.9.9 |

The pre-v0.9.6 core stabilization is complete. Subsequent hardening added cooperative worker ownership, crash-recoverable file operations, a conservative embedded-terminal capability contract, Unicode-aware terminal cells and physical-column geometry across window chrome, menus, dialogs, desktop icons and list applications. The global shell now uses a classic bottom taskbar with an `Inicio` control, minimized-window buttons and the clock on one shared row.

The current milestone is **real-environment certification**. A green automated suite validates internal behavior, but does not by itself certify a physical TTY, terminal emulator, SSH client, multiplexer or Windows terminal host.

Start here:

- [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) — concise current state, completed work and pending certification.
- [docs/TTY_TEST_MATRIX.md](docs/TTY_TEST_MATRIX.md) — live real-terminal certification results.
- [docs/STABILIZATION_PRE_0.9.6.md](docs/STABILIZATION_PRE_0.9.6.md) — completed stabilization record.
- [ROADMAP.md](ROADMAP.md) — path from v0.9.6 to 1.0.

## What RetroTUI is

RetroTUI recreates a Windows 3.1-style desktop using Python and `curses` without X11 or Wayland. The UI, input router and renderer run on one main thread. Background work is isolated behind explicit managers or worker state and returns results to the main loop.

The stable base profile exposes:

- **File Manager**
- **Notepad**
- **Terminal**

Additional built-in applications and bundled plugins can be enabled through configuration.

## Highlights

- Window manager with focus, z-order, move, resize, maximize and minimize behavior.
- Classic bottom shell bar with `Inicio`, global menus, minimized-window buttons and clock.
- Unicode-aware physical-column clipping, centering and mouse hitboxes across shared UI surfaces.
- Keyboard and mouse routing for terminal emulators and Linux console/GPM environments.
- POSIX PTY and Windows ConPTY terminal backends.
- Terminal normal/alternate screens, Unicode-aware physical cells, DEC scrolling regions, tab stops, reports, cursor state, per-cell attributes and scrollback.
- Honest child capability negotiation through the bundled conservative `retrotui` terminfo profile.
- Bounded PTY reads and writes so terminal traffic cannot monopolize the UI loop.
- Transactional close protocol for windows with unsaved state.
- Typed dialog workflows bound to the window that opened them.
- Capability-based drag-and-drop dispatch.
- Deterministic EventBus lifecycle and isolated plugin failures.
- Color-pair negotiation for terminals with limited `COLOR_PAIRS` capacity.
- Built-in themes: Windows 3.1, DOS/CGA, Windows 95, Hacker and Amiga.
- Bundled and custom plugin discovery.
- Automated CI on Ubuntu and Windows with Python 3.10, 3.12 and 3.14.

## Installation

### From PyPI

```bash
python -m pip install retrotui
retrotui
```

### From source

```bash
git clone https://github.com/roccolate/retrotui.git
cd retrotui
python -m pip install -e .
retrotui
```

For development and tests:

```bash
python -m pip install -e ".[test]"
python tools/qa.py --skip-tests
python -m unittest discover -s tests -v
python -m pytest tests -q
```

## Platform requirements

| Platform | Runtime requirements | Embedded terminal |
|---|---|---|
| Linux / WSL / macOS-like POSIX | Python 3.10+, stdlib `curses`, UTF-8 terminal recommended | `pty`, `fcntl`, `termios` |
| Native Windows | Python 3.10+, `windows-curses`, `pywinpty` | ConPTY through `winpty` |

The package declares Windows-only dependencies using environment markers, so a normal installation installs them only on Windows.

Real behavior still depends on terminal capabilities. Consult [docs/TTY_TEST_MATRIX.md](docs/TTY_TEST_MATRIX.md) before treating a specific emulator, TTY, SSH or multiplexer combination as certified.

## Controls

| Key | Action |
|---|---|
| `Tab` | Switch window focus |
| `Alt+Tab` | Cycle windows |
| `F10` | Toggle the global menu |
| `Ctrl+Q` | Close menus first, then request application exit |
| Right click | Context menu |

### Base applications

**File Manager**

- `Enter`: open selected entry
- `F5`: copy
- `F4` / `F6`: move
- `F2`: rename
- `F7`: new folder
- `F8`: new file
- `U`: undo supported trash operation
- `D`: toggle dual pane

**Notepad**

- `Ctrl+S`: save
- `Ctrl+O`: open
- `Ctrl+W`: toggle word wrap
- Dirty buffers are protected by the transactional close/open workflow.

**Terminal**

- `Ctrl+C`: copy selection or interrupt the child process, depending on context
- `Ctrl+V`: paste
- `F6`: interrupt
- `F7`: terminate
- PTY input and output are serviced from `tick()`, including while minimized.
- DEC mouse-reporting pass-through is supported when the child enables it.

**RetroNet**

- `Ctrl+T`: new tab
- `Ctrl+W`: close tab
- `Ctrl+I`: next tab
- `Shift+Tab`: previous tab
- `Ctrl+B`: bookmarks
- `Ctrl+D`: add bookmark
- `Ctrl+U`: view source
- `/`: in-page search

## Configuration

The primary user configuration is stored at:

```text
~/.config/retrotui/config.toml
```

RetroNet bookmarks use:

```text
~/.config/retrotui/bookmarks.toml
```

Plugins can be discovered from bundled, user and development locations. See [docs/plugin-guide.md](docs/plugin-guide.md).

## Architecture contracts

The current architecture is built around a small set of authorities:

- `WindowManager` owns window spawn, focus and close lifecycle.
- `Window.request_close()` decides whether a close is accepted, vetoed or requires confirmation.
- `tick()` reports visual changes; `wants_periodic_tick` controls cadence; `tick_when_hidden` controls hidden service work.
- `EventBus` publishes deterministic lifecycle and subsystem events.
- `DialogDispatcher` resolves typed workflows using the captured source window.
- `DragDropManager` invokes `accept_dropped_path()` before generic `open_path()` fallback.
- `TerminalSession` owns PTY process state, bounded reads, queued writes and verified shutdown.
- `shell_geometry` owns the global bottom row and workspace bounds.
- Shared `wcwidth`-backed helpers own physical-column clipping, padding and centering.
- `WorkerScope` owns background worker cancellation, publication validity and bounded shutdown.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete model.

## Documentation

- [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) — current project state and active work.
- [ARCHITECTURE.md](ARCHITECTURE.md) — runtime architecture and ownership contracts.
- [ROADMAP.md](ROADMAP.md) — current milestone and path to 1.0.
- [CHANGELOG.md](CHANGELOG.md) — release and unreleased change history.
- [docs/STABILIZATION_PRE_0.9.6.md](docs/STABILIZATION_PRE_0.9.6.md) — completed P0/P1 stabilization record.
- [docs/TECHNICAL_AUDIT_2026-07.md](docs/TECHNICAL_AUDIT_2026-07.md) — original code-first audit.
- [docs/CORE_AUDIT_2026-07.md](docs/CORE_AUDIT_2026-07.md) — original deep core audit.
- [docs/CODEX_NEXT_STEPS.md](docs/CODEX_NEXT_STEPS.md) — operational handoff for v0.9.6 certification.
- [docs/TTY_TEST_MATRIX.md](docs/TTY_TEST_MATRIX.md) — live compatibility matrix.
- [tools/TESTING.md](tools/TESTING.md) — manual test checklist.
- [docs/RELEASE.md](docs/RELEASE.md) — release policy and gates.
- [CONTRIBUTING.md](CONTRIBUTING.md) — contributor workflow.
- [docs/plugin-guide.md](docs/plugin-guide.md) — plugin development.
- [docs/ICON_STYLES.md](docs/ICON_STYLES.md) — icon styles and aliases.
- [docs/SHORTCUT_POLICY_PLAN.md](docs/SHORTCUT_POLICY_PLAN.md) — shortcut policy work.

## Support policy

Automated tests validate behavior without requiring a physical terminal. Real-terminal certification is tracked separately because input protocols, Unicode width, color capacity, mouse support and ConPTY behavior can vary by environment.

Do not infer universal support from a green unit-test suite. Use the TTY matrix for environment-specific claims.

## License

MIT

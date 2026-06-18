# RetroTUI Architecture

This document describes the internals of RetroTUI for anyone who wants to contribute, fix bugs, or build plugins.

## Design Principles

- **Windows 3.1 Experience**: A faithful TUI recreation of the classic desktop environment — no X11, no Wayland, just Python and `curses`.
- **Zero Dependencies on Linux**: Only the Python 3.10+ standard library. Windows requires `pywinpty` (ConPTY backend for the embedded terminal). On Python 3.14+ `curses` is part of the standard library on Windows, so no extra curses package is needed.
- **Main-Thread UI**: Rendering and input dispatch happen on one curses thread. Long-running work must run through explicit background workers and communicate back through polled state, locks, events, or `ActionResult`.
- **Testability**: Core logic is decoupled from curses via a fake curses module injected in tests. No real terminal needed to run the test suite.

## Directory Structure

```text
retrotui/
├── __main__.py             # Entry point (python -m retrotui)
├── constants.py            # Box-drawing chars, color pair IDs, layout constants
├── utils.py                # safe_addstr, draw_box, theme_attr, key normalization
├── theme.py                # Theme dataclass + built-in themes (win31, dos, win95, hacker, amiga)
│
├── core/                   # Core system — the "engine"
│   ├── app.py              # RetroTUI facade class (~150 methods, delegates everything)
│   ├── event_loop.py       # Main loop: input → dispatch → draw
│   ├── bootstrap.py        # Terminal setup (cbreak, mouse, flow control)
│   ├── rendering.py        # Desktop background, icons, taskbar, status bar
│   ├── window_manager.py   # Window list, z-order, focus, spawn/close
│   ├── mouse_router.py     # Mouse event routing (hit-test → dispatch)
│   ├── mouse_utils.py      # Mouse utility functions (arity cache, hit-tests, captures)
│   ├── key_router.py       # Keyboard routing (hotkeys → active window)
│   ├── actions.py          # ActionType, AppAction, ActionResult — the message contract
│   ├── action_runner.py    # App-level action dispatch (_APP_REGISTRY → spawn window)
│   ├── dialog_dispatch.py  # Routes ActionResult from windows to dialogs/operations
│   ├── context_menu_handler.py  # Right-click menu logic
│   ├── drag_drop.py        # File drag-and-drop between windows
│   ├── event_bus.py        # Pub/sub event system (clipboard, file ops, window events)
│   ├── ipc.py              # Window-to-window messaging (IPCRouter)
│   ├── notifications.py    # Toast notification system
│   ├── signal_handler.py   # Unix signal → synthetic key queue (no curses corruption)
│   ├── plugin_manager.py   # Plugin lifecycle (discover, register, spawn)
│   ├── menu_builder.py     # Global menu construction + plugin menu items
│   ├── icon_manager.py     # Desktop icon positions (draggable, persisted)
│   ├── icon_styles.py      # Icon style system (default, mini, braille, codex)
│   ├── config.py           # AppConfig dataclass, TOML load/save
│   ├── clipboard.py        # Internal clipboard + system clipboard bridge
│   ├── file_operations.py  # File dialogs + background copy/move with progress
│   ├── terminal_session.py # PTY session (POSIX pty + Windows ConPTY via pywinpty)
│   ├── ansi.py             # ANSI escape code state machine for terminal emulation
│   ├── viewer.py           # File type detection → viewer window dispatch
│   ├── content.py          # Static text (welcome, about, help)
│   └── platform/
│       └── mouse_backend.py  # Mouse event normalization (GPM, SGR, fallback)
│
├── ui/                     # Reusable UI widgets
│   ├── window.py           # Base Window class — the "app protocol"
│   ├── dialog.py           # Dialog, InputDialog, ProgressDialog
│   ├── menu.py             # MenuBar, Menu (global), WindowMenu (per-window)
│   ├── context_menu.py     # ContextMenu widget
│   └── selectable_text.py  # Text selection mixin (notepad, terminal, log viewer)
│
├── apps/                   # Built-in applications
│   ├── app_manager.py      # Desktop Icon Editor + Menu Editor
│   ├── filemanager/        # File Manager (dual-pane)
│   │   ├── window.py       # FileManagerWindow (main class)
│   │   ├── core.py         # PaneState, directory listing, sorting
│   │   ├── operations.py   # Copy, move, rename, delete helpers
│   │   ├── bookmarks.py    # Path bookmarks
│   │   └── preview.py      # File preview panel
│   ├── notepad.py          # Text editor (dispatch table pattern)
│   ├── terminal.py         # Embedded terminal emulator
│   ├── calculator.py       # Calculator
│   ├── hexviewer.py        # Hex viewer
│   ├── process_manager.py  # Process manager
│   ├── sysmon.py           # System monitor
│   ├── logviewer.py        # Log file viewer
│   ├── trash.py            # Trash / recycle bin
│   ├── clipboard_viewer.py # Clipboard viewer
│   ├── control_panel.py    # Control Panel / Settings
│   ├── settings.py         # Settings window
│   ├── image_viewer.py     # Image viewer implementation (also exposed by bundled plugin)
│   ├── markdown_viewer.py  # Markdown viewer
│   ├── retronet.py         # RetroNet implementation (also exposed by bundled plugin)
│   └── wifi_manager.py     # WiFi manager implementation (also exposed by bundled plugin)
│
├── plugins/                # Plugin infrastructure
│   ├── base.py             # RetroApp — ergonomic base class for plugins
│   └── loader.py           # Plugin discovery (plugin.toml) + module loading
│
└── bundled_plugins/        # Shipped as plugins, loaded via the plugin system
    ├── charmap/            # Character Map
    ├── clock/              # Clock
    ├── image-viewer/       # Image Viewer
    ├── minesweeper/        # Minesweeper
    ├── retronet/           # RetroNet
    ├── snake/              # Snake
    ├── solitaire/          # Solitaire
    ├── tetris/             # Tetris
    └── wifi-manager/       # WiFi Manager
```

## How the Main Loop Works

`core/event_loop.py` → `run_app_loop(app)` is the heart of RetroTUI. Single-threaded, runs at ~30 FPS when active.

```
┌─────────────────────────────────────────────────────┐
│                    Main Loop                        │
│                                                     │
│  1. Poll background operations (file copy/move)     │
│  2. Tick notifications (expire old toasts)          │
│  3. If dirty → draw_frame(app)                      │
│  4. Adjust input timeout based on state:            │
│     - Idle: 500ms                                   │
│     - Live PTY session: faster polling              │
│     - Background file op: faster polling            │
│  5. Read input (get_wch, blocks until timeout)      │
│  6. If no input → check signal queue, idle refresh  │
│  7. dispatch_input(app, key) → sets dirty if changed│
│  └── loop                                           │
└─────────────────────────────────────────────────────┘
```

### Draw Order (back to front)

1. Desktop background (theme pattern)
2. Desktop icons
3. Windows (bottom to top, list order = z-order)
4. Global menu bar + dropdown
5. Taskbar (minimized window buttons)
6. Status bar
7. Modal dialog (if any)
8. Context menu
9. Toast notifications (top-right overlay)

### Input Dispatch Priority

1. Context menu (modal — swallows all input when open)
2. Mouse events → `mouse_router.handle_mouse_event()`
3. Resize events → clamp windows to new terminal size
4. Keyboard → `key_router.handle_key_event()`

## The Facade Pattern (`core/app.py`)

`RetroTUI` is a **thin facade** with ~150 methods. It holds state and delegates to specialized modules:

| Concern | Module |
|---|---|
| Window list, z-order, focus | `WindowManager` |
| File dialogs, background ops | `FileOperationManager` |
| Desktop icon positions | `IconPositionManager` |
| File drag-and-drop | `DragDropManager` |
| Dialog result routing | `DialogDispatcher` |
| Pub/sub events | `EventBus` |
| Window-to-window messaging | `IPCRouter` |
| Toast notifications | `NotificationManager` |
| Mouse routing | `mouse_router` (free functions) |
| Keyboard routing | `key_router` (free functions) |
| Rendering | `rendering` (free functions) |
| Action dispatch | `action_runner` (free functions) |
| Menu construction | `menu_builder` (free functions) |
| Icon styling | `icon_styles` (free functions) |
| Signal handling | `signal_handler` (free functions) |
| Plugin lifecycle | `plugin_manager` (free functions) |
| Terminal setup | `bootstrap` (free functions) |

Most facade methods are one-liners. This means you can mock individual module functions in tests without patching the entire class.

## The Application Protocol

Every app is a subclass of `ui/window.py → Window`. The protocol:

```python
class MyApp(Window):
    def draw(self, stdscr):
        """Render window content. Called every frame."""

    def handle_key(self, key) -> ActionResult | None:
        """Process a keystroke. Return ActionResult to request app-level action."""

    def handle_click(self, mx, my) -> ActionResult | None:
        """Process mouse click (coordinates relative to window)."""

    def handle_right_click(self, mx, my) -> list | None:
        """Return context menu items, or None."""

    def close(self):
        """Cleanup hook called when the window is closed."""

    def on_ipc_message(self, message):
        """Receive messages from other windows (optional)."""

    def subscribe_to_bus(self, bus):
        """Subscribe to event bus topics (optional)."""
```

### The Message Contract

Windows never call app methods directly. Instead they return `ActionResult` objects:

```python
# In your window's handle_key:
return ActionResult(type=ActionType.OPEN_FILE, payload="/path/to/file")
return ActionResult(type=ActionType.EXECUTE, payload=AppAction.NOTEPAD)
return ActionResult(type=ActionType.REQUEST_SAVE_AS, payload={"content": text})
return ActionResult(type=ActionType.ERROR, payload="Something went wrong")
```

The `DialogDispatcher` (`core/dialog_dispatch.py`) routes these to the appropriate app-level handler — showing dialogs, spawning windows, starting file operations, etc.

### Action Types

- `ActionType` — window-to-app requests: `OPEN_FILE`, `EXECUTE`, `REQUEST_SAVE_AS`, `REQUEST_RENAME_ENTRY`, `REQUEST_DELETE_CONFIRM`, `REQUEST_COPY_ENTRY`, `REQUEST_MOVE_ENTRY`, `ERROR`, `UPDATE_CONFIG`, etc.
- `AppAction` — app-level actions used by menus and icons: `FILE_MANAGER`, `NOTEPAD`, `TERMINAL`, `FM_COPY`, `NP_SAVE`, etc. These are the "commands" that the menu system and desktop icons trigger.

## Window Management

`core/window_manager.py → WindowManager` manages the window list.

- **Z-Order**: Windows are drawn in list order. Index 0 = bottom, last = top (active).
- **Focus**: `set_active_window(win)` deactivates all others, moves `win` to the top of its layer. Windows marked `always_on_top` stay above normal windows.
- **Spawning**: `_spawn_window(win)` appends to the list, publishes `window.opened` on the event bus, and calls `win.subscribe_to_bus()` if available.
- **Closing**: `close_window(win)` calls `win.close()`, removes from list, activates the next visible window, publishes `window.closed`.

## Mouse Routing

`core/mouse_router.py` routes normalized mouse events through a priority chain:

1. **Active drag/resize** (fast-path, O(1)) — if a window is being dragged or resized, route directly.
2. **File drag-and-drop** — handled by `DragDropManager`.
3. **Global menu bar** — clicks on the top menu row.
4. **Right-click** → `context_menu_handler.handle_right_click()`.
5. **Window hit-test** — reversed loop (topmost first). Tests: close/minimize/maximize buttons → title bar → resize borders → client area.
6. **Desktop** — icon clicks, desktop background.

Mouse events are normalized by `platform/mouse_backend.py` into a dict with boolean fields (`is_click_like`, `right_click`, `is_drag`, `button1_double`, etc.) to abstract away differences between GPM, SGR, and xterm mouse protocols.

## Keyboard Routing

`core/key_router.py` processes keys in this order:

1. `normalize_app_key(key)` — converts raw `get_wch()` values to canonical control codes.
2. Ctrl+Q — closes open menus first (context → window → global), then exits if none open.
3. F10 / Escape — toggles menus.
4. If global menu is active → consumes all keys for menu navigation.
5. Tab → cycle window focus.
6. Otherwise → delegates to `active_window.handle_key(key)`.

## Signal Handling

`core/signal_handler.py` installs handlers for SIGINT, SIGTERM, SIGTSTP, etc. Signals are **not** acted on immediately — they enqueue synthetic key codes that the event loop consumes on the next iteration. This prevents signal delivery from corrupting curses state mid-render.

## Terminal Emulation

`apps/terminal.py` provides an embedded terminal using `core/terminal_session.py` as the PTY backend.

### PTY Backend

Dual-platform, lazily resolved and cached:

| Platform | Backend | Shell default | Key module |
|---|---|---|---|
| **Linux/macOS** | `pty.fork()` + `fcntl` non-blocking | `$SHELL` or `/bin/sh` | `pty`, `fcntl`, `termios` |
| **Windows** | `pywinpty` ConPTY | `%COMSPEC%` or `cmd.exe` | `winpty` |

POSIX is always preferred when available. The Windows path only activates when `winpty` is importable.

### ANSI Parsing

`core/ansi.py → AnsiStateMachine` parses PTY output character by character. It yields typed tuples:

- `('TEXT', char, curses_attr)` — printable character with SGR attributes resolved to curses color pairs.
- `('CSI', final_char, params)` — cursor movement, erase, etc.
- `('CONTROL', char)` — `\n`, `\r`, `\b`, `\t`.

## Event Bus

`core/event_bus.py → EventBus` provides synchronous pub/sub. All dispatch happens on the main thread — subscribers must not block.

Built-in topics: `clipboard.changed`, `file_op.started/completed/failed`, `window.opened/closed/focused`, `config.changed`, `theme.changed`, `ipc.message`, `notification`.

```python
# Subscribe
unsub = bus.subscribe("clipboard.changed", my_callback)

# Publish
bus.publish("clipboard.changed", {"text": "hello"}, source="notepad")
```

## Plugin System

### Plugin Structure

A plugin is a directory containing `plugin.toml` and `__init__.py`:

```text
my-plugin/
├── plugin.toml      # Manifest (id, name, window size)
└── __init__.py      # Must export a class named Plugin
```

`plugin.toml` example:
```toml
[plugin]
id = "my-plugin"
name = "My Plugin"
version = "1.0.0"
category = "plugin"

[plugin.window]
default_width = 40
default_height = 20

[plugin.icon]
emoji = "🔧"
token = "MP"
```

`__init__.py` example:
```python
from retrotui.plugins.base import RetroApp

class Plugin(RetroApp):
    def draw_content(self, stdscr, x, y, w, h):
        # Draw your app here
        pass

    def handle_key(self, key):
        # Handle keyboard input
        pass
```

### Plugin Discovery

`plugins/loader.py` searches these locations (in order):

1. `RETROTUI_PLUGIN_DIR` env var (single forced directory)
2. `RETROTUI_PLUGIN_PATH` env var (colon/semicolon-separated on POSIX, semicolon-separated on Windows)
3. `retrotui/bundled_plugins/` (shipped with the package)
4. `~/.config/retrotui/plugins/`
5. `examples/plugins/` (only when the default user plugin directory is active, for development)

All errors during plugin loading are isolated — a broken plugin never crashes startup. The stable base profile keeps plugins disabled by default with `plugin:*` in `hidden_icons` and `hidden_menu_items`; when both wildcards are present, runtime plugin discovery is skipped.

### Bundled Plugins

Games and utilities that ship with RetroTUI and can load through the plugin system when enabled: Character Map, Clock, Image Viewer, Minesweeper, RetroNet, Snake, Solitaire, Tetris, WiFi Manager.

The repository also includes 21 example plugins under `examples/plugins/`. These are visible in a checkout/development run when the default plugin directory is used.

## Configuration

`core/config.py → AppConfig` is a frozen dataclass persisted to `~/.config/retrotui/config.toml`.

Fields include `theme`, `show_hidden`, `word_wrap_default`, `sunday_first`, `show_welcome`, `icon_style`, `hidden_icons`, `hidden_menu_items`, and persisted desktop/menu customization state.

Uses `tomllib` on Python 3.11+, falls back to a hand-rolled minimal TOML parser for older versions.

## Themes

`theme.py` defines 5 built-in themes as frozen dataclasses:

| Theme | Key | Desktop Pattern |
|---|---|---|
| Windows 3.1 | `win31` | spaces |
| DOS/CGA | `dos_cga` | `▒` |
| Windows 95 | `win95` | spaces |
| Hacker | `hacker` | `▓` |
| Amiga | `amiga` | spaces |

Each theme defines color pairs for 256-color and 8-color terminals. `utils.init_colors(theme)` calls `curses.init_pair()` for every semantic role (`desktop`, `menubar`, `window_border`, etc.). `utils.theme_attr(role)` provides cached lookups.

## Clipboard

`core/clipboard.py` maintains an internal clipboard and bridges to system clipboard tools:

- **Windows**: `clip.exe` / `powershell Get-Clipboard`
- **Wayland**: `wl-copy` / `wl-paste`
- **X11**: `xclip` or `xsel`

Falls back to internal-only if no system tool is found. Backend detection is cached.

## Platform Support

| Platform | curses | PTY | Mouse |
|---|---|---|---|
| **Linux/WSL** | stdlib `curses` | `pty.fork()` | GPM (TTY) or xterm protocol |
| **Windows** | stdlib `curses` (3.14+; `windows-curses` on 3.13-) | `pywinpty` (ConPTY) | xterm protocol |

### Windows-Specific

- **`core/terminal_session.py`**: Dual backend — tries POSIX first, falls back to `pywinpty`. All methods (`read`, `write`, `resize`, `close`, `send_signal`, `poll_exit`) branch on `self._win_pty is not None`. Flow control on Windows is handled by the stdlib curses module (or the legacy `windows-curses` package on Python ≤ 3.13), so no shim is needed.

## Testing

The repo currently has 97 `tests/test_*.py` files. The v0.9.3 release notes recorded 970 collected tests. Most tests use `unittest.TestCase` + `unittest.mock`, and can run without a real terminal.

### Fake Curses

Tests inject a fake curses module into `sys.modules["curses"]` before importing application code. The fake provides:

- All key code constants (`KEY_UP`, `KEY_MOUSE`, etc.)
- All mouse bitmask constants (`BUTTON1_PRESSED`, etc.)
- All attribute constants (`A_BOLD`, `A_REVERSE`, etc.)
- No-op implementations of `init_pair`, `start_color`, `mousemask`, etc.
- `color_pair = lambda value: int(value) * 10`

The shared implementation is in `tests/_support.py`. Some test files define their own inline version following the same pattern.

### Test File Conventions

- `test_<module>.py` — unit tests for one module.
- `test_<app>_<aspect>.py` — tests for a specific aspect of an app (the file manager has 15+ test files).
- `test_core_app.py` — integration-level tests for the `RetroTUI` facade.

### Running Tests

```bash
python -m unittest discover tests      # Standard-library runner
python tools/qa.py                     # Project QA helper
python tools/qa.py --module-coverage   # Optional module coverage gate
python -m pytest tests/ -q             # Optional if pytest is installed
```

## Common Patterns

### Dispatch Tables

Several apps use class-level dicts mapping key codes to method name strings, dispatched via `getattr()`:

```python
_KEY_DISPATCH = {
    curses.KEY_UP: "_key_up",
    curses.KEY_DOWN: "_key_down",
    "\x13": "_key_save",       # Ctrl+S
}

def handle_key(self, key):
    handler = self._KEY_DISPATCH.get(key)
    if handler:
        return getattr(self, handler)()
```

Used in: Notepad, File Manager (`_MENU_ACTION_MAP`).

### Lazy Initialization

The `RetroTUI` facade uses lazy init for optional subsystems:

```python
@property
def event_bus(self):
    if not hasattr(self, "_event_bus"):
        self._event_bus = EventBus()
    return self._event_bus
```

### Backend Resolution Caching

Module-level caches with a sentinel object:

```python
_BACKENDS_UNSET = object()
_CACHE = {"value": _BACKENDS_UNSET}

def _resolve_backend():
    if _CACHE["value"] is not _BACKENDS_UNSET:
        return _CACHE["value"]
    # ... resolve ...
    _CACHE["value"] = result
    return result

def _reset_cache():  # For tests
    _CACHE["value"] = _BACKENDS_UNSET
```

Used in: `terminal_session.py`, `clipboard.py`.

### Safe Rendering

All curses write calls go through `utils.safe_addstr()`, which clamps coordinates to terminal bounds and silently catches curses errors. This prevents crashes when windows are near screen edges or during resize transitions.

## Debug / Profiling

- `RETROTUI_DEBUG=1` — enables verbose mouse-trace logging.
- `RETROTUI_PROFILE=1` — tracks loop iterations, draw time, dispatch time, and input wait time per interval.
- `RETROTUI_MOUSE_BACKEND=gpm|sgr|fallback` — override mouse protocol detection.
- `RETROTUI_PLUGIN_DIR=/path` — override plugin search directory.
- `RETROTUI_PLUGIN_PATH=/path1:/path2` — additional plugin search paths.

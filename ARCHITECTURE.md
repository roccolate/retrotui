# RetroTUI Architecture

This document describes the high-level architecture and technical decisions of RetroTUI.

## Design Principles

- **Windows 3.1 Experience**: A faithful TUI recreation of the classic desktop environment (without X11/Wayland).
- **Zero External Dependencies**: Relies solely on Python's standard library (`curses`, `os`, `sys`, `subprocess`).
- **Testability**: Core logic is decoupled from the UI to allow unit testing with a `fake curses` implementation.

## System Overview

RetroTUI runs as a single-threaded Python application. It uses a **custom event loop** to handle input (keyboard/mouse) and rendering.

### Directory Structure

```text
retrotui/
├── core/           # Core system logic
│   ├── app.py          # Main application state & window manager
│   ├── event_loop.py   # Main RunLoop (Input -> Update -> Draw)
│   ├── rendering.py    # Global UI rendering (Desktop, Taskbar)
│   ├── mouse_router.py # Mouse event dispatching
│   ├── key_router.py   # Keyboard event dispatching
│   └── theme.py        # Theme engine & color definitions
├── ui/             # Reusable UI widgets
│   ├── window.py       # Base Window class
│   ├── dialog.py       # Modal dialogs
│   └── menu.py         # MenuBar and Dropdown logic
└── apps/           # Built-in Applications
    ├── filemanager/    # File Manager (dual-pane, operations)
    ├── notepad.py      # Text Editor
    ├── terminal.py     # Embedded Terminal Emulator
    └── ...             # Calculator, Clock, etc.
```

## Core Components

### 1. The Event Loop (`core/event_loop.py`)
The heart of RetroTUI. It runs at `30 FPS` (approx) and performs:
1.  **Input Processing**: Polls `curses.get_wch()` and `curses.getmouse()`.
2.  **Dispatch**: Routes events to the active window or global handlers.
3.  **Drawing**: Clears the screen and asks the Window Manager to draw the desktop and windows.

### 2. Window Manager (`core/app.py`)
Manages the list of open windows (`self.windows`).
-   **Z-Order**: Windows are drawn in order. The last window in the list is the "topmost" (active) one.
-   **Focus**: Only the active window receives keyboard input.

### 3. Input Routing (`core/mouse_router.py` & `core/key_router.py`)
Decouples raw `curses` events from application logic.
-   **Mouse**: Hit-testing determines if a click targets a Window (Client Area, Title Bar, Resize Border), the Taskbar, or the Desktop icons.
-   **Keyboard**: Global hotkeys (`F10`, `Tab`) are handled first, then passed to the active window's `handle_key()`.

### 4. Application Protocol
Every app is a subclass of `Window`.
-   `handle_key(key)`: Process keystrokes.
-   `handle_mouse(x, y, event)`: Process clicks relative to window coordinates.
-   `draw(stdscr)`: Render the window content.

## Terminal Emulation

The embedded terminal (`apps/terminal.py`) uses Python's `pty` module to spawn a real shell process (`bash`/`sh`).
-   **Output**: Reads stdout from the PTY fd in non-blocking mode and parses ANSI escape codes.
-   **Input**: Forwards RetroTUI keystrokes to the PTY stdin.
-   **Resize**: Sends `SIGWINCH` to the subprocess when the window is resized.

## Platform Specifics

-   **Linux Console (TTY)**: Uses `GPM` for mouse support.
-   **Terminal Emulators**: Uses xterm mouse tracking sequences.
-   **Windows**: Not supported natively (missing `curses`), but used for CI/Testing via mocks.

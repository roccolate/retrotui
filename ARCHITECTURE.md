# RetroTUI Architecture

This document describes the current runtime architecture after the pre-v0.9.6 stabilization pass. It is the primary reference for contributors changing lifecycle, input, rendering, dialogs, plugins or terminal behavior.

## Design goals

- Recreate a Windows 3.1-style desktop inside a terminal.
- Keep rendering and input on one curses-owning main thread.
- Make lifecycle ownership explicit instead of relying on incidental focus or visible strings.
- Keep long-running or blocking work outside render paths.
- Preserve compatibility with constrained terminals and older plugin integrations where practical.
- Make every critical contract testable without requiring a physical terminal.

## Platform model

| Platform | UI backend | Embedded terminal backend |
|---|---|---|
| POSIX systems | stdlib `curses` | `pty.fork()`, `fcntl`, `termios` |
| Native Windows | `windows-curses` | `pywinpty` / ConPTY |

The package declares Windows dependencies with environment markers. POSIX backend resolution is preferred whenever available.

Real terminal capabilities still vary. Unit tests validate internal behavior; [docs/TTY_TEST_MATRIX.md](docs/TTY_TEST_MATRIX.md) records environment certification.

## Repository layout

```text
retrotui/
├── __main__.py                 # CLI entry point
├── constants.py                # layout and logical constants
├── color_pairs.py              # logical-to-physical color negotiation
├── theme.py                    # built-in themes
├── utils.py                    # safe drawing and shared helpers
│
├── core/
│   ├── app.py                  # RetroTUI facade and shared state
│   ├── event_loop.py           # main loop and hook isolation
│   ├── rendering.py            # desktop/frame composition
│   ├── window_manager.py       # window lifecycle authority
│   ├── event_bus.py            # synchronous pub/sub
│   ├── key_router.py           # keyboard dispatch
│   ├── mouse_router.py         # mouse dispatch
│   ├── actions.py              # ActionType, AppAction, ActionResult
│   ├── action_runner.py        # app-level action execution
│   ├── dialog_workflow.py      # stable workflow IDs and bindings
│   ├── dialog_dispatch.py      # dialog result resolution
│   ├── drag_drop.py            # capability-based dropped-path routing
│   ├── file_operations.py      # asynchronous file-operation coordination
│   ├── file_transfer.py        # cooperative copy/move and transactional publish
│   ├── worker_scope.py         # worker ownership, cancellation and bounded join
│   ├── shell_geometry.py       # bottom shell row and workspace bounds
│   ├── terminal_session.py     # POSIX PTY and Windows ConPTY process layer
│   ├── terminal_modes.py       # conservative DEC/capability state
│   ├── ansi.py                 # ANSI parser/state machine
│   ├── viewer.py               # file type to viewer dispatch
│   ├── clipboard.py            # internal/system clipboard bridge
│   ├── notifications.py        # toast lifecycle
│   ├── ipc.py                  # window-to-window messages
│   ├── config.py               # TOML configuration
│   └── platform/               # platform-specific input adapters
│
├── ui/
│   ├── window.py               # base Window protocol
│   ├── dialog.py               # dialog widgets
│   ├── menu.py                 # global/window menus
│   ├── context_menu.py         # context menu widget
│   └── selectable_text.py      # shared selection behavior
│
├── apps/                       # built-in application implementations
├── bundled_plugins/            # packaged plugins
└── plugins/                    # plugin API and loader
```

## Authority map

RetroTUI deliberately assigns each cross-cutting concern to one authority.

| Concern | Authority |
|---|---|
| Spawn, focus, z-order and close | `WindowManager` |
| Permission to close a window | `Window.request_close()` |
| One-frame visual invalidation | return value of `tick()` |
| Tick cadence | `wants_periodic_tick` |
| Service while hidden | `tick_when_hidden` |
| App-level requests | `ActionResult` + dispatcher |
| Dialog identity and ownership | `dialog_workflow` + `DialogDispatcher` |
| Dropped-path behavior | `DragDropManager` |
| Pub/sub lifecycle events | `EventBus` |
| PTY ownership | `TerminalSession` |
| Terminal cell/screen invariants | `TerminalScreenBuffer` |
| Global shell row and workspace bounds | `shell_geometry` |
| Physical text width and fitting | shared `utils` column helpers |
| Background worker lifetime | `WorkerScope` |
| Cooperative filesystem transfer | `file_transfer` + `file_operations` |
| Logical color IDs | `color_pairs` negotiation |

Do not introduce a second authority for one of these concerns. Compatibility adapters should translate legacy behavior at a boundary rather than reintroduce competing state inside the core loop.

## Main-thread model

Curses calls, input dispatch, window lifecycle and rendering belong to the main thread.

Background workers may perform file I/O, previews or other blocking tasks, but they must return state through explicit managers, locks, events, queues or `ActionResult` objects. A worker must not draw directly and must not mutate curses-owned UI state without synchronization.

## Event loop

`core/event_loop.py` owns the runtime loop.

A logical cycle performs:

1. Poll subsystem/background state.
2. Tick eligible windows.
3. Record whether any window reported a visual change.
4. Render when dirty.
5. Choose an input timeout from current service needs.
6. Read and normalize input.
7. Dispatch input through modal, mouse and keyboard routers.
8. Repeat until shutdown.

### Tick contract

`Window.tick()` is the only punctual signal that a window changed visually.

```python
def tick(self) -> bool:
    # service state
    return visual_state_changed
```

Related properties have separate meanings:

- `wants_periodic_tick`: this window needs recurring service even without input.
- `tick_when_hidden`: service must continue while minimized or hidden.
- `tick()` return value: this cycle changed something visible and should invalidate the frame.

The event loop does not inspect app-specific `_animated` or `needs_redraw` flags. Legacy plugin compatibility is isolated in `RetroApp`.

### Circuit breaker

Each window hook has independent failure tracking.

- Repeated `tick()` failures can isolate ticking without disabling drawing.
- Repeated `draw()` failures can isolate drawing without disabling service.
- A successful call resets that hook's consecutive-failure count.
- Renderer-level failures use backoff and retain the first useful cause.

This protects the desktop from one broken app or plugin while preserving diagnosis.

## Rendering

Rendering composes the frame back to front:

1. Desktop background.
2. Desktop icons.
3. Windows by z-order.
4. Global menu and upward dropdown.
5. Unified bottom shell bar (`Inicio`, menu titles, minimized windows and clock).
6. Modal dialog.
7. Context menu.
8. Notifications.

Curses writes should go through safe helpers that clamp coordinates and tolerate resize races. Drawing must not start network requests, read PTYs, poll files or perform other blocking service work.

### Shell geometry and physical text columns

`core/shell_geometry.py` is the authority for the global bottom row and workspace limits. The workspace starts at row zero and ends immediately before the reserved shell row. Window maximize, drag, resize, desktop icon clipping, taskbar drawing, clock routing and global-menu mouse handling consume the same geometry.

The global shell row contains, from left to right:

1. `[ Inicio ]`;
2. global menu titles;
3. minimized-window buttons;
4. the clock.

Global dropdowns open upward from this row. Per-window menus retain downward dropdown behavior.

Text geometry uses shared `wcwidth`-backed helpers:

- `text_display_width()` measures physical terminal columns;
- `clip_text_columns()` clips without splitting wide/combining sequences;
- `pad_text_columns()` fits a row to an exact column budget;
- `center_text_columns()` centers within an exact physical width.

Rendering and hit-testing must use the same measured geometry. Python `len()`, ordinary slicing and format-field widths are not valid substitutes for user-visible terminal columns.

## Window lifecycle

`core/window_manager.py` owns the window collection, active pointer and lifecycle events.

### Spawn

All windows must enter through the manager's spawn path. The manager:

- inserts the window into the correct z-order;
- establishes focus;
- subscribes it to the EventBus when supported;
- publishes `window.opened`;
- keeps the active-window cache consistent.

Directly appending to `app.windows` bypasses lifecycle and is not allowed.

### Close protocol

Closing is transactional.

1. A caller asks `WindowManager` to close a window.
2. The manager calls `window.request_close()` unless `force=True` is reserved for cleanup.
3. The window may:
   - accept immediately;
   - veto;
   - request a confirmation workflow.
4. Only after authorization does the manager run cleanup, remove the window, select a new active window and publish `window.closed`.

Applications with unsaved state, especially Notepad, must protect every close/open route through this protocol.

### Cleanup result

A window cleanup hook may release external resources. Terminal cleanup can report failure when the child process cannot be verified as stopped. The caller must not convert an unverified cleanup into a false success.

## Actions and dispatch

Windows request app-level behavior with `ActionResult` rather than reaching into `RetroTUI` internals.

```python
return ActionResult(type=ActionType.OPEN_FILE, payload=path)
return ActionResult(type=ActionType.EXECUTE, payload=AppAction.NOTEPAD)
return ActionResult(type=ActionType.ERROR, payload="Operation failed")
```

`action_runner`, `dialog_dispatch` and related managers resolve those requests.

The `source` window should be preserved whenever a result can complete asynchronously or after focus changes.

## Dialog workflows

Dialog behavior is identified by stable workflow metadata, not by visible titles or button labels.

A bound dialog carries:

- `workflow_id`;
- `source_window`;
- `source_window_id`;
- `on_accept`;
- `on_cancel`.

`DialogDispatcher` resolves the workflow using those fields. Before invoking a callback it verifies that the captured source window is still registered. Focus changes do not redirect the result to another window.

`dialog.callback` remains a compatibility alias for older integrations, but it is not the authoritative contract.

## Input routing

### Keyboard

The keyboard router normalizes raw curses values before dispatch. Modal/global UI consumes input before the active application.

A typical priority is:

1. Active modal/context UI.
2. Global exit/menu shortcuts.
3. Global menu navigation.
4. Focus cycling.
5. Active window `handle_key()`.

### Mouse

The mouse router processes captures and top-level UI before ordinary client clicks.

A typical priority is:

1. Active window drag/resize capture.
2. File drag-and-drop.
3. Global menu.
4. Context menu.
5. Window chrome and client hit-test from topmost to bottom.
6. Desktop icons/background.

Mouse events are normalized by platform adapters so applications do not depend directly on GPM or xterm bitmasks.

## Drag-and-drop

`DragDropManager` uses capability precedence:

1. `accept_dropped_path(path)` for a destination-specific operation.
2. `open_path(path)` only as a generic fallback.

For File Manager this distinction is critical: accepting a drop means copy/move into the current directory, while opening a path means navigation.

If the specific handler raises, the generic fallback is not invoked automatically. A failure must not silently transform into a different operation.

## EventBus

`EventBus` is created deterministically and dispatches synchronously on the main thread.

Common topics include:

- `window.opened`, `window.closed`, `window.focused`;
- clipboard changes;
- file operation state;
- configuration and theme changes;
- IPC and notifications.

Subscribers must not block. Publishers should use the public EventBus contract rather than probing optional private attributes.

## Color-pair negotiation

RetroTUI keeps stable logical color IDs but cannot assume every terminal exposes the same number of physical pairs.

The color layer:

- inspects `curses.COLOR_PAIRS`;
- allocates physical pairs within the available capacity;
- reuses identical foreground/background combinations;
- degrades safely to pair `0` when necessary;
- avoids corrupting logical roles that share a compacted physical pair.

Code should request semantic/logical roles rather than calling `curses.init_pair()` ad hoc.

## Terminal architecture

`apps/terminal.py` owns terminal UI state. `core/terminal_session.py` owns the child process and byte transport. `core/ansi.py` owns escape-sequence parsing.

### Separation of responsibilities

| Layer | Responsibility |
|---|---|
| `TerminalWindow` | UI, selection, scrolling, resize requests and service cadence |
| `TerminalSession` | process spawn, read/write, signal, liveness and close |
| `AnsiStateMachine` | parse terminal control sequences |
| `TerminalScreenBuffer` | rows, cells, cursor and scrolling invariants |

PTY reads and writes occur from `tick()`, never from `draw()`.

### Hidden service

`TerminalWindow.tick_when_hidden = True` keeps live sessions draining while minimized. Hidden service does not imply continuous redraw; `tick()` returns true only when visible state changes.

### Read budget

`TerminalSession.read()` defaults to an aggregate 8 KiB budget per service call.

- Multiple POSIX reads may occur until the total budget is reached.
- Remaining bytes stay in the OS/PTY buffer for the next tick.
- The incremental UTF-8 decoder preserves split multibyte sequences.
- `max_total_bytes=None` is an explicit unbounded drain.
- Windows performs a bounded ConPTY read under the same contract.

### Write queue

PTY input uses a FIFO pending-byte queue.

- `write(payload)` accepts the complete payload into session ownership.
- `flush_pending_writes()` sends up to 8 KiB per service cycle.
- Partial writes remove only the acknowledged prefix.
- Return `0`, `BlockingIOError` and `EAGAIN` retain the unsent suffix.
- `TerminalWindow.tick()` flushes pending input before reading output.
- Closing a successfully terminated session clears pending input.

### Terminal capabilities and DEC modes

`core/terminal_modes.py` declares the conservative capability contract and
holds mutable per-session DEC mode state. `AnsiStateMachine` preserves CSI
private markers through a list-compatible `CsiParams` object so `?25`, `?1`,
`?7` and `?2004` cannot be confused with ordinary CSI parameters.

`TerminalWindow` owns the side effects:

- `?25h` / `?25l` controls cursor visibility;
- `?1h` / `?1l` selects application or normal cursor-key encoding;
- `?2004h` / `?2004l` enables bracketed paste framing;
- `?7h` / `?7l` enables or disables autowrap in the active Unicode-aware screen buffer;
- alternate-screen and mouse modes remain owned by the same window authority.

Bracketed paste sanitizes an embedded end marker before framing the payload, so
clipboard content cannot terminate paste mode early.

### Unicode cell and DEC screen model

`TerminalScreenBuffer` stores physical terminal columns while preserving the public two-item `(text, attr)` cell tuple contract. A double-width glyph owns a leading cell plus an internal empty-text continuation cell. Combining marks, variation selectors and zero-width-joiner sequences merge into the preceding leading cell without advancing the cursor.

Screen editing expands operations that touch a wide continuation back to the leading cell, preventing orphan halves during insert, delete, erase and resize. Autowrap decides whether a glyph wraps before the final column or is clamped/replaced when wrapping is disabled.

Per-screen state includes DEC scrolling margins, origin mode, saved cursor coordinates and tab stops. Implemented controls include:

- `DECSTBM`, DECOM, CSI save/restore, ICH, DCH, ECH, IL and DL;
- IND, NEL and RI with active-region semantics;
- HTS, TBC, CHT and CBT;
- ANSI/DEC-private device-status and cursor-position reports;
- `?1049` alternate-screen save, clear, home and normal-cursor restore.

Protocol replies go directly to the existing PTY child and do not enter scrollback.

### Scrollback

The normal screen buffer is the source of truth for visible rows. Only rows expelled by scroll operations enter the scrollback deque. Newlines that remain inside the viewport do not duplicate content.

If the scrollback deque is replaced, the buffer's scroll sink must be rebound.

### POSIX backend

POSIX start uses `pty.fork()`.

The child:

- merges `extra_env` into `os.environ`;
- applies `cwd` when supplied;
- executes the selected shell.

The parent:

- stores child PID and master FD;
- sets the master nonblocking;
- resizes through `TIOCSWINSZ`;
- reaps the child on exit;
- escalates termination during close when necessary.

### Windows backend

Windows start creates `winpty.PTY(cols, rows)` and supports multiple API generations:

1. keyword `spawn(shell, cwd=..., env=...)`;
2. positional context arguments;
3. legacy single bytes argument.

The environment passed to ConPTY is the inherited process environment merged with `extra_env` and encoded as a CreateProcess-style null-separated block.

### Verified Windows close

Dropping the Python reference is not considered a close.

The backend close path:

1. prefers `close(force=True)` when available;
2. falls back to `close()` for wrappers without the keyword;
3. uses `cancel_io()` for raw backends;
4. requests SIGTERM by PID;
5. escalates to the platform force signal if needed;
6. checks `isalive()` between stages.

If the child is still observably alive, `close()` returns false and retains the backend and pending input so the caller cannot mistake an unverified shutdown for success.

## File operations and workers

File operations may run outside the main thread. `WorkerScope` owns thread registration, cancellation, bounded joins and publication validity. Global filesystem operations additionally belong to `FileOperationManager`, which rejects new work during shutdown and suppresses late UI dispatch.

`core/file_transfer.py` implements cooperative copy/move with pre-scan progress, block-level cancellation and transactional destination publication through sibling temporary paths. Same-filesystem moves prefer atomic no-replace rename; cross-filesystem moves publish the complete destination before removing the source.

Trash operations write recovery journals before irreversible transitions. Move-to-trash, restore, permanent delete and empty trash reconcile incomplete state on startup and hide internal sidecars, staging paths and tombstones from the user view.

Important invariants:

- metadata required for recovery is written before the transition it describes;
- a final destination is not exposed until its payload is complete;
- expected cancellation is not reported as an asynchronous error;
- UI updates are consumed on the main thread;
- previews and operations use cancellation or generation ownership;
- stale worker output cannot overwrite newer state;
- a shutdown that cannot physically join side-effecting work reports that limitation instead of declaring success.

## Plugin model

A plugin contains `plugin.toml` and an importable `Plugin` class, usually based on `RetroApp`.

Discovery may include:

1. `RETROTUI_PLUGIN_DIR`;
2. `RETROTUI_PLUGIN_PATH`;
3. bundled plugins;
4. the user plugin directory;
5. development example plugins.

Loader errors are isolated. A broken plugin must not abort startup.

Bundled plugins use the modern `wants_periodic_tick` contract. `RetroApp` translates selected legacy plugin flags at the plugin boundary.

## Configuration

Primary configuration is persisted in:

```text
~/.config/retrotui/config.toml
```

Configuration changes should flow through the public config/apply path so open windows, menus and EventBus subscribers observe a consistent value.

When adding fields, define defaults, serialization behavior and migration/preservation policy. Do not silently discard unknown sections without an explicit schema policy.

## Testing and CI

The permanent CI matrix runs on:

- Ubuntu: Python 3.10, 3.12 and 3.14.
- Windows: Python 3.10, 3.12 and 3.14.

Each combination executes:

```bash
python tools/qa.py --skip-tests
python -m unittest discover -s tests -v
python -m pytest tests -q
```

Both runners are intentional. A test should not be considered protected unless it is collected by the permanent gate.

Tests use fake curses implementations and backend doubles to exercise lifecycle and platform logic without requiring a live terminal. Real-terminal behavior belongs in the TTY matrix.

## Contribution rules for core changes

Before changing a cross-cutting contract:

1. Identify the current authority in the authority map.
2. Avoid introducing parallel private flags.
3. Preserve source-window ownership across asynchronous/dialog flows.
4. Keep blocking work outside `draw()` and input handlers.
5. Add focused regression coverage.
6. Run both test runners.
7. Update this document when ownership or public behavior changes.

## Historical audits

The July 2026 audits document the original findings and should remain unchanged as historical evidence:

- [docs/TECHNICAL_AUDIT_2026-07.md](docs/TECHNICAL_AUDIT_2026-07.md)
- [docs/CORE_AUDIT_2026-07.md](docs/CORE_AUDIT_2026-07.md)

The completion mapping from those findings to the stabilized implementation is in [docs/STABILIZATION_PRE_0.9.6.md](docs/STABILIZATION_PRE_0.9.6.md).

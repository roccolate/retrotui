# RetroTUI — Current Project Status

**Status date:** 2026-07-21  
**Published package version:** `0.9.5`  
**Active milestone:** `v0.9.6 — cross-terminal certification`  
**Primary branch:** `main`

## Executive summary

RetroTUI has completed the pre-v0.9.6 automated stabilization gate. The core runtime now has explicit authorities for window lifecycle, redraw scheduling, dialog ownership, drag-and-drop dispatch, terminal PTY service, color-pair negotiation and CI test collection.

The project is not yet v0.9.6-certified. Automated tests demonstrate internal contracts and regression protection; they do not prove that every physical TTY, emulator, SSH client, multiplexer or Windows terminal host behaves correctly. The active work is therefore real-environment certification and documentation of support boundaries.

## Completed

### Core and lifecycle

- `WindowManager` is the authority for spawn, focus, z-order and close.
- `Window.request_close()` provides transactional close authorization.
- EventBus creation and lifecycle events are deterministic.
- `tick()`, `wants_periodic_tick` and `tick_when_hidden` have separate responsibilities.
- Repeated `tick()` or `draw()` failures are isolated by the event-loop circuit breaker.
- Logical color IDs are mapped according to real terminal capacity.

### Dialogs and input

- Dialog workflows use stable IDs and capture the source window.
- Dialog results are not routed by visible titles or incidental focus.
- Drag-and-drop calls `accept_dropped_path()` before generic `open_path()` fallback.
- RetroNet tab rendering and hit testing share the same geometry.

### Terminal PTY

- Terminal sessions continue to receive service while minimized.
- PTY reads and writes use bounded per-tick budgets.
- Partial writes are retained in a FIFO queue without losing or reordering bytes.
- Scrollback has a single source of truth and does not duplicate visible rows.
- Windows ConPTY receives `cwd` and merged environment where supported.
- Current, positional and legacy `pywinpty.spawn()` variants are covered.
- Windows PTY close is explicit and verified instead of relying on reference deletion.

### Automated gate

The permanent CI matrix covers:

| OS | Python | Repository QA | unittest | pytest |
|---|---:|---:|---:|---:|
| Ubuntu | 3.10 | ✅ | ✅ | ✅ |
| Ubuntu | 3.12 | ✅ | ✅ | ✅ |
| Ubuntu | 3.14 | ✅ | ✅ | ✅ |
| Windows | 3.10 | ✅ | ✅ | ✅ |
| Windows | 3.12 | ✅ | ✅ | ✅ |
| Windows | 3.14 | ✅ | ✅ | ✅ |

Commands:

```bash
python tools/qa.py --skip-tests
python -m unittest discover -s tests -v
python -m pytest tests -q
```

## Pending for v0.9.6

The following environments still need real certification:

- Linux console / physical TTY.
- Linux GUI terminal emulator.
- SSH.
- tmux.
- GNU screen.
- WSL with Windows Terminal.
- Native Windows with `pywinpty` / ConPTY.

For each environment record startup, shutdown, keyboard, mouse, resize, Unicode, colors, File Manager, Notepad, Terminal and representative plugins in [TTY_TEST_MATRIX.md](TTY_TEST_MATRIX.md).

The embedded terminal should also be exercised with available tools such as `nano`, `vim`, `less`, `top`, `htop` and `mc`.

## Not currently in scope

Do not begin these until v0.9.6 certification is closed unless a certification blocker requires them:

- session restore;
- first-run wizard;
- Start Menu redesign;
- new games, themes or bundled apps;
- marketplace/discovery UX;
- broad plugin API redesign;
- networking expansion;
- large core refactors.

These belong to v0.9.7, v0.9.8 or post-1.0.

## Source-of-truth map

- [README.md](../README.md) — public overview and support policy.
- [ARCHITECTURE.md](../ARCHITECTURE.md) — runtime authorities and contracts.
- [ROADMAP.md](../ROADMAP.md) — milestone boundaries and path to 1.0.
- [STABILIZATION_PRE_0.9.6.md](STABILIZATION_PRE_0.9.6.md) — completed stabilization record.
- [TTY_TEST_MATRIX.md](TTY_TEST_MATRIX.md) — live real-environment certification results.
- [CODEX_NEXT_STEPS.md](CODEX_NEXT_STEPS.md) — operational workflow for the active milestone.
- [RELEASE.md](RELEASE.md) — release gates and branch policy.
- [../CHANGELOG.md](../CHANGELOG.md) — historical change record.

The July audit documents are historical evidence, not active task lists:

- [TECHNICAL_AUDIT_2026-07.md](TECHNICAL_AUDIT_2026-07.md)
- [CORE_AUDIT_2026-07.md](CORE_AUDIT_2026-07.md)

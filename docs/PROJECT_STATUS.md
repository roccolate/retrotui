# RetroTUI — Current Project Status

**Status date:** 2026-07-22  
**Published package version:** `0.9.5`  
**Active milestone:** `v0.9.6 — cross-terminal certification`  
**Primary branch:** `main`

## Executive summary

RetroTUI has completed the pre-v0.9.6 automated stabilization gate and an additional hardening campaign on top of that baseline. The runtime now has explicit authorities for window lifecycle, redraw scheduling, dialogs, drag-and-drop, shell geometry, physical text width, worker lifetime, file-operation recovery, PTY transport and terminal screen state.

The visible shell now uses a classic bottom taskbar. Unicode geometry is based on physical terminal columns across window chrome, menus, dialogs, desktop icons, File Manager, Process Manager and App Manager. The embedded terminal has an honest `TERM`/terminfo contract, Unicode-aware cells, DEC scrolling regions and editing controls, tab stops, status reports and hardened OSC handling.

The project is still not v0.9.6-certified. Automated tests demonstrate internal contracts and regression protection; they do not prove that every physical TTY, emulator, SSH client, multiplexer or Windows terminal host behaves correctly. The active work remains real-environment certification and documentation of support boundaries.

## Completed

### Core, lifecycle and workers

- `WindowManager` is the authority for spawn, focus, z-order and close.
- `Window.request_close()` provides transactional close authorization.
- EventBus creation and lifecycle events are deterministic.
- `tick()`, `wants_periodic_tick` and `tick_when_hidden` have separate responsibilities.
- Repeated `tick()` or `draw()` failures are isolated by the event-loop circuit breaker.
- Circuit-breaker state is owned outside application windows; legacy `_retrotui_*` fields are compatibility mirrors only.
- `WorkerScope` owns cancellation, bounded joins and rejection of stale worker publications.
- Logical color IDs are mapped according to real terminal capacity.

### Shell, dialogs and Unicode UI

- The unified global shell bar occupies the final terminal row.
- `[ Inicio ]`, global menus, minimized-window buttons and the clock share one bottom-row geometry.
- Global dropdowns open upward; window-local menus continue to open downward.
- Maximized, moved and resized windows stop above the taskbar and use the full workspace from row zero.
- Shared `wcwidth`-backed helpers clip, pad and center text by physical columns.
- Window titles, taskbar labels, menus, dialogs, icon art/labels and list-oriented apps use physical widths for drawing and hit testing.
- Control Panel checkbox hitboxes are restricted to their rendered labels and apply preferences immediately.
- Dialog workflows use stable IDs and capture the source window.
- Drag-and-drop calls `accept_dropped_path()` before generic `open_path()` fallback.
- RetroNet tab rendering and hit testing share the same geometry.

### File operations and recovery

- Background file operations have explicit ownership and suppress results after shutdown.
- Copy and move use cooperative block transfers, progress reporting and safe cancellation.
- Destination publication is transactional and does not silently replace an existing path.
- Trash move, restore, permanent delete and empty-trash operations use recovery journals.
- Startup reconciliation hides and repairs internal sidecars, staged payloads and deferred cleanup state.

### Embedded terminal

- Terminal sessions continue to receive service while minimized.
- PTY reads and writes use bounded per-tick budgets and a FIFO pending-write queue.
- Focused terminal windows own common terminal keys; `F12` is the explicit host-command prefix.
- Child sessions receive an honest conservative `TERM` contract and can use the bundled `retrotui` terminfo entry when installed.
- Unicode-aware cells preserve wide-glyph continuation and combining-sequence invariants.
- DEC autowrap, scrolling margins, origin mode, insert/delete/erase operations and alternate-screen restoration are implemented.
- IND, NEL, RI, HTS, TBC, CHT, CBT, status reports and cursor-position reports are implemented.
- OSC strings require BEL or a complete ST terminator and no longer leak malformed payload text.
- Windows ConPTY receives `cwd` and merged environment where supported, and close is explicit and verified.

### Automated gate

The permanent CI matrix covers:

| OS | Python | Repository QA | Ruff F821 | unittest | pytest | Coverage gate |
|---|---:|---:|---:|---:|---:|---:|
| Ubuntu | 3.10 | ✅ | ✅ | ✅ | ✅ | shared job |
| Ubuntu | 3.12 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ubuntu | 3.14 | ✅ | ✅ | ✅ | ✅ | shared job |
| Windows | 3.10 | ✅ | ✅ | ✅ | ✅ | shared job |
| Windows | 3.12 | ✅ | ✅ | ✅ | ✅ | shared job |
| Windows | 3.14 | ✅ | ✅ | ✅ | ✅ | shared job |

Commands:

```bash
python tools/qa.py --skip-tests
python -m ruff check --select F821 retrotui tests tools
python -m unittest discover -s tests -v
python -m pytest tests -q
python tools/report_module_coverage.py --quiet-tests --top 20 --fail-under 75.0
```

## Repository state

- `main` is the only long-lived remote branch and the source of truth.
- Recent implementation PRs were squash-merged after exact-head CI validation.
- Fully absorbed agent and maintenance branches were removed after comparison with `main`.
- No temporary write, diagnostic or cleanup workflow remains in `main`.

## Pending for v0.9.6

The following environments still need real certification:

- Linux console / physical TTY.
- Linux GUI terminal emulator.
- SSH.
- tmux.
- GNU screen.
- WSL with Windows Terminal.
- Native Windows with `pywinpty` / ConPTY.

For each environment record startup, shutdown, bottom-taskbar geometry, keyboard, mouse, resize, Unicode, colors, File Manager, Notepad, Terminal and representative plugins in [TTY_TEST_MATRIX.md](TTY_TEST_MATRIX.md).

The embedded terminal should also be exercised with available tools such as `nano`, `vim`, `less`, `top`, `htop` and `mc`.

## Not currently in scope

Do not begin these until v0.9.6 certification is closed unless a certification blocker requires them:

- session restore;
- first-run wizard;
- full categorized Start Menu redesign beyond the current `Inicio` shell control;
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
- [STABILIZATION_PRE_0.9.6.md](STABILIZATION_PRE_0.9.6.md) — original completed stabilization record.
- [TTY_TEST_MATRIX.md](TTY_TEST_MATRIX.md) — live real-environment certification results.
- [CODEX_NEXT_STEPS.md](CODEX_NEXT_STEPS.md) — operational workflow for the active milestone.
- [RELEASE.md](RELEASE.md) — release gates and branch policy.
- [../CHANGELOG.md](../CHANGELOG.md) — historical and unreleased change record.

The July audit documents are historical evidence, not active task lists:

- [TECHNICAL_AUDIT_2026-07.md](TECHNICAL_AUDIT_2026-07.md)
- [CORE_AUDIT_2026-07.md](CORE_AUDIT_2026-07.md)

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    file_path = ROOT / path
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_before_once(path: str, marker: str, content: str) -> None:
    replace_once(path, marker, content + marker)


def update_readme() -> None:
    replace_once(
        "README.md",
        """```text
╔══════════════════════════════════════════════════════════════╗
║ ≡ File   Edit   Help                            12:30:45     ║
╠══════════════════════════════════════════════════════════════╣
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
╚══════════════════════════════════════════════════════════════╝
```""",
        """```text
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
```""",
    )
    replace_once(
        "README.md",
        "The pre-v0.9.6 core stabilization is complete: lifecycle ownership, redraw scheduling, terminal PTY service, dialog routing, drag-and-drop precedence, color-pair negotiation, scrollback ownership and the complete CI gate now have explicit contracts and regression coverage.\n",
        "The pre-v0.9.6 core stabilization is complete. Subsequent hardening added cooperative worker ownership, crash-recoverable file operations, a conservative embedded-terminal capability contract, Unicode-aware terminal cells and physical-column geometry across window chrome, menus, dialogs, desktop icons and list applications. The global shell now uses a classic bottom taskbar with an `Inicio` control, minimized-window buttons and the clock on one shared row.\n",
    )
    replace_once(
        "README.md",
        "- Window manager with focus, z-order, move, resize, maximize, minimize and taskbar behavior.\n",
        "- Window manager with focus, z-order, move, resize, maximize and minimize behavior.\n- Classic bottom shell bar with `Inicio`, global menus, minimized-window buttons and clock.\n- Unicode-aware physical-column clipping, centering and mouse hitboxes across shared UI surfaces.\n",
    )
    replace_once(
        "README.md",
        "- Terminal normal screen, alternate screen, cursor state, per-cell attributes and scrollback.\n",
        "- Terminal normal/alternate screens, Unicode-aware physical cells, DEC scrolling regions, tab stops, reports, cursor state, per-cell attributes and scrollback.\n- Honest child capability negotiation through the bundled conservative `retrotui` terminfo profile.\n",
    )
    replace_once(
        "README.md",
        "- `TerminalSession` owns PTY process state, bounded reads, queued writes and verified shutdown.\n",
        "- `TerminalSession` owns PTY process state, bounded reads, queued writes and verified shutdown.\n- `shell_geometry` owns the global bottom row and workspace bounds.\n- Shared `wcwidth`-backed helpers own physical-column clipping, padding and centering.\n- `WorkerScope` owns background worker cancellation, publication validity and bounded shutdown.\n",
    )


def update_project_status() -> None:
    path = ROOT / "docs/PROJECT_STATUS.md"
    path.write_text(
        """# RetroTUI — Current Project Status

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
""",
        encoding="utf-8",
    )


def update_changelog() -> None:
    insert_before_once(
        "CHANGELOG.md",
        "## [pre-v0.9.6] - 2026-07-21 (stabilization complete)\n",
        """## [Unreleased] - 2026-07-22

Hardening and visible-shell work completed after the original pre-v0.9.6 stabilization gate. The published package remains `0.9.5`; these changes are present on `main` and still require real-terminal certification before a v0.9.6 release.

### Core, workers and file operations

- Externalized circuit-breaker ownership from application windows while preserving legacy compatibility mirrors.
- Added typed payloads for destructive confirmations, transfers, process signals and configuration updates.
- Added configuration `schema_version = 1`, legacy migration and protection against overwriting unknown future schemas.
- Added `WorkerScope` ownership, cooperative cancellation, bounded shutdown and stale-result rejection for window and global workers.
- Added cooperative copy/move transfers with deterministic progress, block-level cancellation, transactional destination publication and no-clobber semantics.
- Added crash-recoverable Trash move, restore, permanent-delete and empty-trash journals with startup reconciliation.
- Hardened idle redraw behavior and Wi-Fi worker executable capture.

### Embedded terminal

- Gave focused terminal windows ownership of terminal-oriented keys and introduced `F12` as the explicit host-command prefix.
- Added DEC cursor visibility, application cursor keys, bracketed paste and effective autowrap state.
- Added a conservative child `TERM` contract, bundled `retrotui` terminfo source and installer command.
- Added Unicode-aware physical cells for CJK, emoji and combining sequences while preserving the legacy two-item cell tuple contract.
- Added DEC scrolling margins, origin mode, screen editing operations, alternate-screen cursor restoration and Unicode-safe wide-cell edits.
- Added IND, NEL, RI, tab stops, TBC/CHT/CBT, device-status reports and cursor-position reports.
- Hardened OSC termination, window close-hook isolation and the live-tail scrollback hot path.

### Shell and Unicode UI

- Added physical-column clipping and hitboxes for window titles and taskbar labels.
- Extended physical-column geometry to global/window menus, dialogs, progress dialogs and multiselect controls.
- Fixed Control Panel checkbox click ranges and immediate preference persistence.
- Moved the global shell to a classic bottom taskbar with `[ Inicio ]`, upward global dropdowns, minimized-window buttons and clock.
- Made desktop icons share one Unicode-aware geometry between rendering and mouse hit testing.
- Extended physical-column fitting to File Manager, Process Manager and App Manager rows, tabs and buttons.

### Validation and maintenance

- Every implementation cut passed the permanent Ubuntu/Windows matrix on Python 3.10, 3.12 and 3.14, including QA, Ruff F821, `unittest`, pytest and the module coverage floor.
- Implementation PRs were squash-merged after exact-head validation.
- Fully absorbed remote branches and temporary maintenance refs were removed; `main` is the only long-lived remote branch.

---

""",
    )


def update_roadmap() -> None:
    replace_once(
        "ROADMAP.md",
        "El trabajo activo pasa ahora a **v0.9.6 — certificación cross-terminal**. No se deben agregar features nuevas durante este milestone salvo que sean estrictamente necesarias para corregir un blocker encontrado en un entorno real.\n",
        "El trabajo activo continúa en **v0.9.6 — certificación cross-terminal**. Después del gate original se completó una campaña adicional de hardening: ownership de workers, operaciones de archivos recuperables, contrato `TERM` honesto, celdas Unicode, controles DEC, geometría por columnas físicas y barra global inferior. No se deben agregar features nuevas durante este milestone salvo que sean estrictamente necesarias para corregir un blocker encontrado en un entorno real.\n",
    )
    insert_before_once(
        "ROADMAP.md",
        "## v0.9.6 — Certificación cross-terminal\n",
        """## Hardening posterior al gate — completado

- [x] Ownership explícito de workers y shutdown global ordenado.
- [x] Transferencias cooperativas con progreso, cancelación y publicación transaccional.
- [x] Trash transaccional con journals de recuperación.
- [x] Contrato conservador `TERM=retrotui` / fallback `TERM=ansi` y terminfo instalable.
- [x] Ownership de teclado para Terminal y prefijo host `F12`.
- [x] Celdas Unicode físicas, autowrap, scroll regions y edición DEC.
- [x] IND/NEL/RI, tab stops y device/cursor reports.
- [x] Hardening de OSC, close hooks y scrollback live-tail.
- [x] Geometría Unicode para chrome, taskbar, menús, diálogos, iconos y listas.
- [x] Barra global inferior con `Inicio`, menús hacia arriba, ventanas minimizadas y reloj.
- [x] Hitboxes precisos de checkboxes en Control Panel.
- [x] Matriz permanente verde en cada corte y ramas absorbidas eliminadas.

Estos cambios amplían lo que debe verificarse en terminales reales; no sustituyen la certificación v0.9.6.

---

""",
    )
    replace_once(
        "ROADMAP.md",
        "- [ ] Teclado y atajos globales.\n",
        "- [ ] Teclado, ownership de Terminal y prefijo host `F12`.\n",
    )
    replace_once(
        "ROADMAP.md",
        "- [ ] Resize y terminales pequeñas.\n- [ ] Unicode y caracteres de ancho doble.\n",
        "- [ ] Resize, workspace desde fila cero y taskbar inferior en terminales pequeñas.\n- [ ] Unicode, combining marks, emoji y caracteres de ancho doble en chrome, menús, iconos, listas y Terminal.\n",
    )
    replace_once(
        "ROADMAP.md",
        "- [ ] `nano`, `vim`, `less`, `top`, `htop` y `mc` donde estén disponibles.\n",
        "- [ ] `nano`, `vim`, `less`, `top`, `htop` y `mc` usando el perfil terminfo conservador donde esté disponible.\n",
    )


def update_architecture() -> None:
    replace_once(
        "ARCHITECTURE.md",
        "│   ├── file_operations.py      # asynchronous file operations\n│   ├── terminal_session.py     # POSIX PTY and Windows ConPTY process layer\n│   ├── ansi.py                 # ANSI parser/state machine\n",
        "│   ├── file_operations.py      # asynchronous file-operation coordination\n│   ├── file_transfer.py        # cooperative copy/move and transactional publish\n│   ├── worker_scope.py         # worker ownership, cancellation and bounded join\n│   ├── shell_geometry.py       # bottom shell row and workspace bounds\n│   ├── terminal_session.py     # POSIX PTY and Windows ConPTY process layer\n│   ├── terminal_modes.py       # conservative DEC/capability state\n│   ├── ansi.py                 # ANSI parser/state machine\n",
    )
    replace_once(
        "ARCHITECTURE.md",
        "| PTY ownership | `TerminalSession` |\n| Logical color IDs | `color_pairs` negotiation |\n",
        "| PTY ownership | `TerminalSession` |\n| Terminal cell/screen invariants | `TerminalScreenBuffer` |\n| Global shell row and workspace bounds | `shell_geometry` |\n| Physical text width and fitting | shared `utils` column helpers |\n| Background worker lifetime | `WorkerScope` |\n| Cooperative filesystem transfer | `file_transfer` + `file_operations` |\n| Logical color IDs | `color_pairs` negotiation |\n",
    )
    replace_once(
        "ARCHITECTURE.md",
        "1. Desktop background.\n2. Desktop icons.\n3. Windows by z-order.\n4. Global menu and dropdown.\n5. Taskbar.\n6. Status bar.\n7. Modal dialog.\n8. Context menu.\n9. Notifications.\n",
        "1. Desktop background.\n2. Desktop icons.\n3. Windows by z-order.\n4. Global menu and upward dropdown.\n5. Unified bottom shell bar (`Inicio`, menu titles, minimized windows and clock).\n6. Modal dialog.\n7. Context menu.\n8. Notifications.\n",
    )
    insert_before_once(
        "ARCHITECTURE.md",
        "## Window lifecycle\n",
        """### Shell geometry and physical text columns

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

""",
    )
    replace_once(
        "ARCHITECTURE.md",
        "- `?7h` / `?7l` records autowrap mode for the upcoming cell-engine slice;\n",
        "- `?7h` / `?7l` enables or disables autowrap in the active Unicode-aware screen buffer;\n",
    )
    insert_before_once(
        "ARCHITECTURE.md",
        "### Scrollback\n",
        """### Unicode cell and DEC screen model

`TerminalScreenBuffer` stores physical terminal columns while preserving the public two-item `(text, attr)` cell tuple contract. A double-width glyph owns a leading cell plus an internal empty-text continuation cell. Combining marks, variation selectors and zero-width-joiner sequences merge into the preceding leading cell without advancing the cursor.

Screen editing expands operations that touch a wide continuation back to the leading cell, preventing orphan halves during insert, delete, erase and resize. Autowrap decides whether a glyph wraps before the final column or is clamped/replaced when wrapping is disabled.

Per-screen state includes DEC scrolling margins, origin mode, saved cursor coordinates and tab stops. Implemented controls include:

- `DECSTBM`, DECOM, CSI save/restore, ICH, DCH, ECH, IL and DL;
- IND, NEL and RI with active-region semantics;
- HTS, TBC, CHT and CBT;
- ANSI/DEC-private device-status and cursor-position reports;
- `?1049` alternate-screen save, clear, home and normal-cursor restore.

Protocol replies go directly to the existing PTY child and do not enter scrollback.

""",
    )
    replace_once(
        "ARCHITECTURE.md",
        "File operations may run outside the main thread. Their managers own operation state and publish progress/results back to the UI.\n\nImportant invariants:\n\n- metadata required for recovery must be written in a safe order;\n- UI updates are consumed on the main thread;\n- previews and operations should support cancellation or generation ownership where implemented;\n- stale worker output must not overwrite newer state.\n",
        "File operations may run outside the main thread. `WorkerScope` owns thread registration, cancellation, bounded joins and publication validity. Global filesystem operations additionally belong to `FileOperationManager`, which rejects new work during shutdown and suppresses late UI dispatch.\n\n`core/file_transfer.py` implements cooperative copy/move with pre-scan progress, block-level cancellation and transactional destination publication through sibling temporary paths. Same-filesystem moves prefer atomic no-replace rename; cross-filesystem moves publish the complete destination before removing the source.\n\nTrash operations write recovery journals before irreversible transitions. Move-to-trash, restore, permanent delete and empty trash reconcile incomplete state on startup and hide internal sidecars, staging paths and tombstones from the user view.\n\nImportant invariants:\n\n- metadata required for recovery is written before the transition it describes;\n- a final destination is not exposed until its payload is complete;\n- expected cancellation is not reported as an asynchronous error;\n- UI updates are consumed on the main thread;\n- previews and operations use cancellation or generation ownership;\n- stale worker output cannot overwrite newer state;\n- a shutdown that cannot physically join side-effecting work reports that limitation instead of declaring success.\n",
    )


def update_contributing() -> None:
    replace_once(
        "CONTRIBUTING.md",
        "git checkout -b feature/my-cool-feature\n",
        "git switch main\ngit pull --ff-only\ngit switch -c feature/my-cool-feature\n",
    )
    replace_once(
        "CONTRIBUTING.md",
        "Before submitting a PR, run the local QA tool. It checks encoding, syntax, and runs tests.\n\n```bash\npython tools/qa.py\n```\n\nIf you want to check test coverage:\n```bash\npython tools/qa.py --module-coverage\n```\n",
        "Before submitting a PR, run the same core checks used by the permanent gate.\n\n```bash\npython -m pip install -e \".[test]\"\npython tools/qa.py --skip-tests\npython -m ruff check --select F821 retrotui tests tools\npython -m unittest discover -s tests -v\npython -m pytest tests -q\n```\n\nFor the module coverage floor:\n\n```bash\npython tools/report_module_coverage.py --quiet-tests --top 20 --fail-under 75.0\n```\n",
    )
    replace_once(
        "CONTRIBUTING.md",
        "4.  Wait for review!\n",
        "4.  Keep the branch synchronized with `main` and address review feedback.\n5.  Prefer squash merge for branches containing operational/fixup commits.\n6.  After merge, compare the branch against `main` and delete it when no exclusive commits remain.\n",
    )
    replace_once(
        "CONTRIBUTING.md",
        "See [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system design before making major changes.\n",
        "See [ARCHITECTURE.md](ARCHITECTURE.md) before changing lifecycle, shell geometry, physical text width, workers, file operations or terminal behavior. Cross-cutting changes must preserve the documented authority map and add focused regression coverage.\n",
    )


def main() -> None:
    update_readme()
    update_project_status()
    update_changelog()
    update_roadmap()
    update_architecture()
    update_contributing()


if __name__ == "__main__":
    main()
